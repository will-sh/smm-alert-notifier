"""
Unified SMM Alert Receiver
Receives and displays alerts from Streams Messaging Manager via:
- HTTP Notifier (REST API)
- Email Notifier (SMTP)
"""

from flask import Flask, request, jsonify, render_template
from datetime import datetime
import json
import logging
from collections import deque
import os
import asyncio
import threading
from email import message_from_bytes
from email.header import decode_header
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

# Configure logging for easier debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================================
# HTTP ALERTS STORAGE (Separate from emails)
# ============================================================================

# Store HTTP alerts in memory (max 1000 alerts, FIFO)
alerts_store = deque(maxlen=1000)

# HTTP Alert statistics tracking
alert_stats = {
    'total_received': 0,
    'by_severity': {},
    'by_type': {}
}

# ============================================================================
# EMAIL STORAGE (Separate from HTTP alerts)
# ============================================================================

# Store emails in memory (max 1000 emails, FIFO)
emails_store = deque(maxlen=1000)

# Email statistics tracking
email_stats = {
    'total_received': 0,
    'by_sender': {},
    'by_subject': {}
}

# ============================================================================
# SMTP SERVER HANDLER
# ============================================================================

class CustomSMTPHandler:
    """
    Custom SMTP handler to receive and process emails from SMM
    """
    
    async def handle_DATA(self, server, session, envelope):
        """
        Handle incoming email data
        """
        try:
            logger.info(f"=== Incoming Email ===")
            logger.info(f"From: {envelope.mail_from}")
            logger.info(f"To: {envelope.rcpt_tos}")
            logger.info(f"Peer: {session.peer}")
            logger.debug(f"Content length: {len(envelope.content)} bytes")
            
            # Parse email message
            message = message_from_bytes(envelope.content)
            
            # Decode subject
            subject_header = message.get('Subject', 'No Subject')
            subject = self._decode_header(subject_header)
            
            # Get sender
            from_header = message.get('From', envelope.mail_from)
            sender = self._decode_header(from_header)
            
            # Get email body
            body = self._get_email_body(message)
            
            # Update statistics first (before storing)
            email_stats['total_received'] += 1
            
            # Store email with unique ID based on total_received
            email_data = {
                'id': email_stats['total_received'],
                'timestamp': datetime.now().isoformat(),
                'from': sender,
                'to': envelope.rcpt_tos,
                'subject': subject,
                'body': body,
                'raw_headers': dict(message.items()),
                'received_from_ip': session.peer[0] if session.peer else 'unknown'
            }
            
            emails_store.append(email_data)
            
            # Update sender and subject statistics
            email_stats['by_sender'][sender] = email_stats['by_sender'].get(sender, 0) + 1
            email_stats['by_subject'][subject] = email_stats['by_subject'].get(subject, 0) + 1
            
            logger.info(f"✅ Email stored successfully!")
            logger.info(f"   ID: {email_data['id']}")
            logger.info(f"   Subject: {subject}")
            logger.info(f"   Total emails: {email_stats['total_received']}")
            logger.info(f"   Store size: {len(emails_store)}")
            
            return '250 Message accepted for delivery'
            
        except Exception as e:
            logger.error(f"❌ Error processing email: {str(e)}", exc_info=True)
            logger.error(f"   From: {envelope.mail_from if 'envelope' in locals() else 'unknown'}")
            logger.error(f"   Error type: {type(e).__name__}")
            return '550 Error processing message'
    
    def _decode_header(self, header_value):
        """Decode email header (handles various encodings)"""
        if not header_value:
            return ''
        
        decoded_parts = decode_header(header_value)
        decoded_string = ''
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8', errors='replace')
            else:
                decoded_string += part
        
        return decoded_string
    
    def _get_email_body(self, message):
        """Extract email body (handles multipart messages)"""
        body = ''
        
        if message.is_multipart():
            # Handle multipart messages (HTML + plain text)
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', ''))
                
                # Skip attachments
                if 'attachment' in content_disposition:
                    continue
                
                # Get plain text or HTML body
                if content_type in ['text/plain', 'text/html']:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            body += payload.decode(charset, errors='replace')
                    except Exception as e:
                        logger.warning(f"Error decoding email part: {e}")
        else:
            # Handle single-part messages
            try:
                payload = message.get_payload(decode=True)
                if payload:
                    charset = message.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='replace')
            except Exception as e:
                logger.warning(f"Error decoding email body: {e}")
        
        return body.strip()


def smtp_authenticator(server, session, envelope, mechanism, auth_data):
    """
    SMTP authentication callback
    Validates username and password for email reception
    """
    # Get valid credentials from environment
    valid_username = os.environ.get('SMTP_USERNAME', 'admin')
    valid_password = os.environ.get('SMTP_PASSWORD', 'admin')
    
    fail_nothandled = AuthResult(success=False, handled=False)
    
    # Only support LOGIN and PLAIN mechanisms
    if mechanism not in ("LOGIN", "PLAIN"):
        logger.warning(f"Unsupported auth mechanism: {mechanism}")
        return fail_nothandled
    
    # Validate auth_data type
    if not isinstance(auth_data, LoginPassword):
        logger.warning(f"Invalid auth_data type: {type(auth_data)}")
        return fail_nothandled
    
    try:
        # Decode credentials
        username = auth_data.login.decode('utf-8') if isinstance(auth_data.login, bytes) else auth_data.login
        password = auth_data.password.decode('utf-8') if isinstance(auth_data.password, bytes) else auth_data.password
        
        logger.debug(f"Auth attempt: user={username}, mechanism={mechanism}")
        
        # Validate credentials
        if username == valid_username and password == valid_password:
            logger.info(f"✅ SMTP authentication successful: {username}")
            return AuthResult(success=True)
        else:
            logger.warning(f"❌ SMTP authentication failed for user: {username}")
            return fail_nothandled
            
    except Exception as e:
        logger.error(f"SMTP auth error: {e}", exc_info=True)
        return fail_nothandled


async def run_smtp_server(host, port):
    """
    Start the SMTP server with authentication
    """
    # Get credentials from environment
    smtp_username = os.environ.get('SMTP_USERNAME', 'admin')
    smtp_password = os.environ.get('SMTP_PASSWORD', 'admin')
    
    handler = CustomSMTPHandler()
    
    # Create controller with authentication enabled
    controller = Controller(
        handler,
        hostname=host,
        port=port,
        authenticator=smtp_authenticator,
        auth_required=True,  # Require authentication
        auth_require_tls=False  # Allow auth without TLS for internal network
    )
    
    logger.info(f"Starting SMTP server on {host}:{port}")
    logger.info(f"SMTP Authentication: ENABLED (required)")
    logger.info(f"Valid credentials: {smtp_username} / {'*' * len(smtp_password)}")
    logger.info(f"SMTP server ready to receive authenticated emails from SMM")
    
    controller.start()
    
    # Keep the server running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down SMTP server...")
        controller.stop()


def start_smtp_server_thread(host, port):
    """
    Start SMTP server in a background thread
    """
    def run_smtp():
        try:
            # Python 3.7+
            asyncio.run(run_smtp_server(host, port))
        except AttributeError:
            # Python 3.6 fallback
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_smtp_server(host, port))
            finally:
                loop.close()
    
    # Start SMTP server in daemon thread
    smtp_thread = threading.Thread(target=run_smtp, daemon=True)
    smtp_thread.start()
    logger.info("SMTP server thread started")


# ============================================================================
# FLASK WEB APPLICATION - HTTP ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """
    Main page - displays the unified alerts dashboard with tabs
    """
    logger.debug("Serving main dashboard page")
    return render_template('index.html')


# ============================================================================
# HTTP ALERT ENDPOINTS
# ============================================================================

@app.route('/api/alerts', methods=['POST'])
def receive_alert():
    """
    Endpoint to receive HTTP alerts from SMM HTTP Notifier
    """
    try:
        # Log the incoming request for debugging
        logger.info(f"Received HTTP alert from {request.remote_addr}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        
        # Parse alert data
        alert_data = request.get_json(force=True)
        logger.debug(f"Alert data: {json.dumps(alert_data, indent=2)}")
        
        # Update statistics first
        alert_stats['total_received'] += 1
        
        # Enrich alert with metadata using total_received as unique ID
        enriched_alert = {
            'id': alert_stats['total_received'],
            'timestamp': datetime.now().isoformat(),
            'received_from': request.remote_addr,
            'data': alert_data
        }
        
        # Store the alert
        alerts_store.append(enriched_alert)
        
        # Extract severity if available
        severity = alert_data.get('severity', 'UNKNOWN')
        alert_stats['by_severity'][severity] = alert_stats['by_severity'].get(severity, 0) + 1
        
        # Extract alert type if available
        alert_type = alert_data.get('alertType', alert_data.get('type', 'UNKNOWN'))
        alert_stats['by_type'][alert_type] = alert_stats['by_type'].get(alert_type, 0) + 1
        
        logger.info(f"Alert stored successfully. Total alerts: {alert_stats['total_received']}")
        
        return jsonify({
            'status': 'success',
            'message': 'Alert received and stored',
            'alert_id': enriched_alert['id']
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing alert: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to process alert: {str(e)}'
        }), 500


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """
    API endpoint to retrieve stored HTTP alerts
    """
    try:
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        severity_filter = request.args.get('severity', None)
        
        # Convert deque to list for slicing
        alerts_list = list(alerts_store)
        
        # Apply severity filter if specified
        if severity_filter:
            alerts_list = [
                alert for alert in alerts_list 
                if alert['data'].get('severity') == severity_filter
            ]
        
        # Reverse to show newest first
        alerts_list.reverse()
        
        # Apply pagination
        paginated_alerts = alerts_list[offset:offset + limit]
        
        logger.debug(f"Returning {len(paginated_alerts)} HTTP alerts")
        
        return jsonify({
            'alerts': paginated_alerts,
            'total': len(alerts_list),
            'offset': offset,
            'limit': limit
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving alerts: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve alerts: {str(e)}'
        }), 500


@app.route('/api/alerts/stats', methods=['GET'])
def get_alert_stats():
    """
    API endpoint to retrieve HTTP alert statistics
    """
    try:
        logger.debug("Retrieving HTTP alert statistics")
        return jsonify(alert_stats), 200
    except Exception as e:
        logger.error(f"Error retrieving alert stats: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve alert stats: {str(e)}'
        }), 500


@app.route('/api/alerts/clear', methods=['POST'])
def clear_alerts():
    """
    API endpoint to clear all stored HTTP alerts
    """
    try:
        logger.warning("Clearing all HTTP alerts")
        alerts_store.clear()
        
        # Reset statistics
        alert_stats['total_received'] = 0
        alert_stats['by_severity'].clear()
        alert_stats['by_type'].clear()
        
        return jsonify({
            'status': 'success',
            'message': 'All HTTP alerts cleared'
        }), 200
    except Exception as e:
        logger.error(f"Error clearing alerts: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear alerts: {str(e)}'
        }), 500


# ============================================================================
# EMAIL ENDPOINTS
# ============================================================================

@app.route('/api/emails', methods=['GET'])
def get_emails():
    """
    API endpoint to retrieve stored emails
    """
    try:
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        sender_filter = request.args.get('sender', None)
        
        # Get all emails
        emails_list = list(emails_store)
        
        # Apply sender filter if specified
        if sender_filter:
            emails_list = [
                email for email in emails_list
                if sender_filter.lower() in email['from'].lower()
            ]
        
        # Reverse to show newest first
        emails_list.reverse()
        
        # Apply pagination
        paginated_emails = emails_list[offset:offset + limit]
        
        logger.debug(f"Returning {len(paginated_emails)} emails")
        
        return jsonify({
            'emails': paginated_emails,
            'total': len(emails_list),
            'offset': offset,
            'limit': limit
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving emails: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve emails: {str(e)}'
        }), 500


@app.route('/api/emails/stats', methods=['GET'])
def get_email_stats():
    """
    API endpoint to retrieve email statistics
    """
    try:
        logger.debug("Retrieving email statistics")
        return jsonify(email_stats), 200
    except Exception as e:
        logger.error(f"Error retrieving email stats: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve email stats: {str(e)}'
        }), 500


@app.route('/api/emails/clear', methods=['POST'])
def clear_emails():
    """
    API endpoint to clear all stored emails
    """
    try:
        logger.warning("Clearing all emails")
        emails_store.clear()
        
        # Reset email statistics
        email_stats['total_received'] = 0
        email_stats['by_sender'].clear()
        email_stats['by_subject'].clear()
        
        return jsonify({
            'status': 'success',
            'message': 'All emails cleared'
        }), 200
    except Exception as e:
        logger.error(f"Error clearing emails: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear emails: {str(e)}'
        }), 500


# ============================================================================
# UNIFIED ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for both services
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'http': {
                'status': 'running',
                'alerts_stored': len(alerts_store)
            },
            'smtp': {
                'status': 'running',
                'emails_stored': len(emails_store)
            }
        }
    }), 200


# ============================================================================
# MAIN APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    # Get configuration from environment
    http_port = int(os.environ.get('HTTP_PORT', 18123))
    smtp_host = os.environ.get('SMTP_HOST', '0.0.0.0')
    smtp_port = int(os.environ.get('SMTP_PORT', 1025))
    smtp_username = os.environ.get('SMTP_USERNAME', 'admin')
    smtp_password = os.environ.get('SMTP_PASSWORD', 'admin')
    
    logger.info("="*60)
    logger.info("Unified SMM Alert Receiver")
    logger.info("="*60)
    logger.info(f"HTTP Server: Port {http_port}")
    logger.info(f"SMTP Server: Port {smtp_port}")
    logger.info(f"SMTP Auth: {smtp_username} / {'*' * len(smtp_password)}")
    logger.info("="*60)
    
    # Start SMTP server in background thread
    logger.info("Starting SMTP server with authentication...")
    start_smtp_server_thread(smtp_host, smtp_port)
    
    # Small delay to let SMTP server initialize
    import time
    time.sleep(1)
    
    logger.info(f"Starting HTTP/Web server on port {http_port}...")
    logger.info(f"")
    logger.info(f"Dashboard: http://localhost:{http_port}")
    logger.info(f"")
    logger.info(f"Configure SMM HTTP Notifier:")
    logger.info(f"  URL: http://<your-server-ip>:{http_port}/api/alerts")
    logger.info(f"")
    logger.info(f"Configure SMM Email Notifier:")
    logger.info(f"  SMTP Hostname: <your-server-ip>")
    logger.info(f"  SMTP Port: {smtp_port}")
    logger.info(f"  Username: {smtp_username}")
    logger.info(f"  Password: {smtp_password}")
    logger.info(f"  Enable Auth: Yes")
    logger.info("="*60)
    
    # Run the Flask app
    # In production, use a proper WSGI server like gunicorn
    app.run(host='0.0.0.0', port=http_port, debug=True, use_reloader=False)

