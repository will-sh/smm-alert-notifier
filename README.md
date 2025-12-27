# SMM Alert Receiver

A unified web server to receive and display alerts from Streams Messaging Manager via HTTP and SMTP.

## Features

- **Dual Protocol Support**: HTTP REST API and SMTP Email
- **Tabbed Dashboard**: View HTTP alerts and emails in separate tabs
- **Real-time Updates**: Auto-refresh and filtering capabilities
- **Separate Storage**: Independent stores for HTTP alerts and emails
- **Statistics Tracking**: Separate stats for each alert type

## Quick Start

### Deploy from Docker Hub
```bash
docker run -d \
  -p 18123:18123 \
  -p 1025:1025 \
  --name smm-alert-receiver \
  wxiao695/smm-alert-receiver:latest
```
Access the dashboard at: `http://localhost:18123`

## Configure SMM Notifiers

### HTTP Notifier

1. Navigate to **Alerts** → **NOTIFIERS** → **ADD NEW**
2. Select **Provider**: HTTP
3. Set **URL**: `http://<your-server-ip>:18123/api/alerts`
4. Save and create an Alert Policy

### Email Notifier

1. Navigate to **Alerts** → **NOTIFIERS** → **ADD NEW**
2. Select **Provider**: Email
3. Configure:
   - **SMTP Hostname**: `<your-server-ip>`
   - **SMTP Port**: `1025`
   - **Username**: `admin`
   - **Password**: `admin`
   - **Enable Auth**: Yes
   - **To Address**: any@example.com
4. Save and create an Alert Policy

## Ports

- **18123** - HTTP API + Web Dashboard
- **1025** - SMTP Server

## API Endpoints

### HTTP Alerts

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts` | POST | Receive HTTP alerts from SMM |
| `/api/alerts` | GET | Retrieve stored HTTP alerts |
| `/api/alerts/stats` | GET | Get HTTP alert statistics |
| `/api/alerts/clear` | POST | Clear all HTTP alerts |

### Email Alerts

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/emails` | GET | Retrieve stored emails |
| `/api/emails/stats` | GET | Get email statistics |
| `/api/emails/clear` | POST | Clear all emails |

### General

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Unified dashboard with tabs |
| `/health` | GET | Health check (both services) |

## Testing

### Test HTTP Alerts

```bash
python test_alert.py
```

### Test SMTP Emails

```bash
python test_email.py
```

## Environment Variables

- `HTTP_PORT` - HTTP server port (default: 18123)
- `SMTP_PORT` - SMTP server port (default: 1025)
- `SMTP_HOST` - SMTP bind address (default: 0.0.0.0)
- `SMTP_USERNAME` - SMTP authentication username (default: admin)
- `SMTP_PASSWORD` - SMTP authentication password (default: admin)

## Requirements

- Docker 19.03+ (for multi-platform builds)
- Python 3.7+ (for local development)

## License

MIT License
