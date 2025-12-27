#!/usr/bin/env python3
"""
Test script to send sample emails to the SMM SMTP Receiver
Useful for testing the SMTP server without configuring SMM
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import time
import os

# Server configuration
SMTP_HOST = os.environ.get('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 1025))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', 'admin')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'admin')

# Email configuration
FROM_EMAIL = 'smm-alerts@example.com'
TO_EMAIL = 'admin@example.com'

# Sample test emails with different alert types
TEST_EMAILS = [
    {
        'subject': '[CRITICAL] Kafka Broker Down',
        'body': '''Alert: Kafka broker has stopped responding

Severity: CRITICAL
Timestamp: {timestamp}
Broker ID: 1
Host: kafka-broker-1.example.com
Port: 9092

Action Required: Immediate investigation needed.
''',
        'severity': 'CRITICAL'
    },
    {
        'subject': '[HIGH] Topic Under-Replicated',
        'body': '''Alert: Topic replication issue detected

Severity: HIGH
Timestamp: {timestamp}
Topic: user-events
Partitions Affected: 5
Min ISR: 2
Current ISR: 1

Action Required: Check broker status and replication.
''',
        'severity': 'HIGH'
    },
    {
        'subject': '[MEDIUM] Disk Usage Warning',
        'body': '''Alert: Disk usage exceeded threshold

Severity: MEDIUM
Timestamp: {timestamp}
Broker ID: 2
Disk Usage: 85%
Available Space: 50 GB

Action Required: Monitor disk usage and plan cleanup.
''',
        'severity': 'MEDIUM'
    },
    {
        'subject': '[LOW] Consumer Lag Increased',
        'body': '''Alert: Consumer lag above threshold

Severity: LOW
Timestamp: {timestamp}
Consumer Group: analytics-consumer
Topic: user-events
Current Lag: 15,000 messages
Threshold: 10,000 messages

Action Required: Review consumer performance.
''',
        'severity': 'LOW'
    }
]


def send_email(subject, body, html_body=None):
    """
    Send a single email to the SMTP server
    
    Args:
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create message
        if html_body:
            msg = MIMEMultipart('alternative')
            part1 = MIMEText(body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
        else:
            msg = MIMEText(body, 'plain')
        
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL
        msg['Subject'] = subject
        msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        
        # Connect to SMTP server
        print(f"Connecting to SMTP server {SMTP_HOST}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        
        # Enable debug output (optional)
        # server.set_debuglevel(1)
        
        # Say hello
        server.ehlo()
        
        # Login with credentials (optional - server accepts without auth too)
        try:
            print(f"Authenticating as {SMTP_USERNAME}...")
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            print(f"✅ Authenticated successfully")
        except smtplib.SMTPException as e:
            print(f"⚠️  Auth not required or failed: {e}")
            print(f"   Continuing without authentication...")
        
        # Send email
        print(f"Sending email: {subject}")
        server.send_message(msg)
        
        # Close connection
        server.quit()
        
        print(f"✅ Email sent successfully!")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print(f"❌ Authentication failed!")
        print(f"   Check username ({SMTP_USERNAME}) and password")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {str(e)}")
        return False
    except ConnectionRefusedError:
        print(f"❌ Connection refused to {SMTP_HOST}:{SMTP_PORT}")
        print(f"   Make sure the SMTP server is running")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_health_check():
    """
    Test if SMTP server is reachable
    """
    try:
        print("\n" + "="*60)
        print("Testing SMTP Server Connection")
        print("="*60)
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        response = server.ehlo()
        print(f"EHLO response: {response}")
        server.quit()
        
        print(f"✅ SMTP server is reachable at {SMTP_HOST}:{SMTP_PORT}")
        return True
    except Exception as e:
        print(f"❌ Cannot reach SMTP server: {str(e)}")
        return False


def main():
    """
    Main test function
    """
    print("\n" + "="*60)
    print("SMM SMTP Server - Test Script")
    print("="*60)
    print(f"SMTP Server: {SMTP_HOST}:{SMTP_PORT}")
    print(f"Username: {SMTP_USERNAME}")
    print(f"Password: {'*' * len(SMTP_PASSWORD)}")
    print(f"Test Emails: {len(TEST_EMAILS)}")
    print("="*60)
    
    # Test server connection first
    if not test_health_check():
        print("\n⚠️  SMTP server health check failed. Is the server running?")
        print("   Start the server with: ./start_servers.sh")
        return
    
    # Send test emails
    print("\nSending test emails...")
    success_count = 0
    
    for i, email_data in enumerate(TEST_EMAILS, 1):
        print("\n" + "="*60)
        print(f"Email {i}/{len(TEST_EMAILS)}: {email_data['severity']}")
        print("="*60)
        
        # Format body with current timestamp
        body = email_data['body'].format(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Send email
        if send_email(email_data['subject'], body):
            success_count += 1
        
        # Wait between emails
        if i < len(TEST_EMAILS):
            time.sleep(1)
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Total Emails Sent: {len(TEST_EMAILS)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(TEST_EMAILS) - success_count}")
    print("="*60)
    
    if success_count == len(TEST_EMAILS):
        print("\n✅ All tests passed!")
        print(f"\nView the emails in your browser:")
        print(f"   http://{SMTP_HOST if SMTP_HOST != '0.0.0.0' else 'localhost'}:18124")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")


if __name__ == "__main__":
    main()

