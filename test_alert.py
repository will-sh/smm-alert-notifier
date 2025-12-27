#!/usr/bin/env python3
"""
Test script to send sample alerts to the SMM Alert Receiver
Useful for testing the server without configuring SMM
"""

import requests
import json
import time
from datetime import datetime

# Server configuration
SERVER_URL = "http://localhost:18123/api/alerts"

# Sample test alerts with different severities
TEST_ALERTS = [
    {
        "severity": "CRITICAL",
        "alertType": "BROKER_DOWN",
        "message": "Kafka broker is down",
        "timestamp": datetime.now().isoformat(),
        "details": {
            "broker_id": 1,
            "host": "kafka-broker-1.example.com",
            "port": 9092
        }
    },
    {
        "severity": "HIGH",
        "alertType": "TOPIC_UNDER_REPLICATED",
        "message": "Topic 'user-events' is under-replicated",
        "timestamp": datetime.now().isoformat(),
        "details": {
            "topic": "user-events",
            "partitions_affected": 5,
            "min_isr": 2,
            "current_isr": 1
        }
    },
    {
        "severity": "MEDIUM",
        "alertType": "DISK_USAGE_HIGH",
        "message": "Disk usage above 80% on broker",
        "timestamp": datetime.now().isoformat(),
        "details": {
            "broker_id": 2,
            "disk_usage_percent": 85,
            "available_space_gb": 50
        }
    },
    {
        "severity": "LOW",
        "alertType": "CONSUMER_LAG_INCREASED",
        "message": "Consumer lag increased for group 'analytics-consumer'",
        "timestamp": datetime.now().isoformat(),
        "details": {
            "consumer_group": "analytics-consumer",
            "topic": "user-events",
            "current_lag": 15000,
            "threshold": 10000
        }
    }
]


def send_alert(alert_data):
    """
    Send a single alert to the server
    """
    try:
        print(f"\n{'='*60}")
        print(f"Sending {alert_data['severity']} alert: {alert_data['alertType']}")
        print(f"{'='*60}")
        
        response = requests.post(
            SERVER_URL,
            json=alert_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success! Alert ID: {result.get('alert_id')}")
            print(f"   Message: {alert_data['message']}")
        else:
            print(f"❌ Failed! Status: {response.status_code}")
            print(f"   Response: {response.text}")
            
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Cannot reach server at {SERVER_URL}")
        print(f"   Make sure the server is running (python app.py)")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_health_check():
    """
    Test the health check endpoint
    """
    try:
        print("\n" + "="*60)
        print("Testing Health Check Endpoint")
        print("="*60)
        
        response = requests.get(
            SERVER_URL.replace('/api/alerts', '/health'),
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is healthy")
            print(f"   Status: {data['status']}")
            # Handle both old and new health check formats
            if 'services' in data:
                http_alerts = data['services']['http']['alerts_stored']
                smtp_emails = data['services']['smtp']['emails_stored']
                print(f"   HTTP Alerts stored: {http_alerts}")
                print(f"   SMTP Emails stored: {smtp_emails}")
            elif 'alerts_stored' in data:
                print(f"   Alerts stored: {data['alerts_stored']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False


def main():
    """
    Main test function
    """
    print("\n" + "="*60)
    print("SMM Alert Receiver - Test Script")
    print("="*60)
    print(f"Target Server: {SERVER_URL}")
    print(f"Test Alerts: {len(TEST_ALERTS)}")
    print("="*60)
    
    # Test health check first
    if not test_health_check():
        print("\n⚠️  Server health check failed. Is the server running?")
        print("   Start the server with: python app.py")
        return
    
    # Send test alerts
    print("\nSending test alerts...")
    success_count = 0
    
    for i, alert in enumerate(TEST_ALERTS, 1):
        # Update timestamp to current time
        alert['timestamp'] = datetime.now().isoformat()
        
        if send_alert(alert):
            success_count += 1
        
        # Wait between alerts
        if i < len(TEST_ALERTS):
            time.sleep(1)
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Total Alerts Sent: {len(TEST_ALERTS)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(TEST_ALERTS) - success_count}")
    print("="*60)
    
    if success_count == len(TEST_ALERTS):
        print("\n✅ All tests passed!")
        print(f"\nView the alerts in your browser:")
        print(f"   {SERVER_URL.replace('/api/alerts', '')}")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")


if __name__ == "__main__":
    main()

