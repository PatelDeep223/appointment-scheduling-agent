#!/usr/bin/env python3
"""
Test script to simulate Calendly webhook events
Useful for testing webhook endpoint without actual Calendly events
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import asyncio


async def test_webhook_endpoint(base_url: str = "http://localhost:8000"):
    """
    Test webhook endpoint with sample payloads
    
    Args:
        base_url: Base URL of the backend server
    """
    webhook_url = f"{base_url}/api/calendly/webhook"
    
    print("🧪 Testing Calendly Webhook Endpoint")
    print("=" * 60)
    
    # Test 1: invitee.created event
    print("\n1️⃣ Testing invitee.created webhook event...")
    
    sample_created_payload = {
        "event": "invitee.created",
        "time": datetime.now().isoformat() + "Z",
        "payload": {
            "event": "https://api.calendly.com/scheduled_events/TEST_EVENT_123",
            "invitee": "https://api.calendly.com/scheduled_events/TEST_EVENT_123/invitees/TEST_INVITEE_456",
            "created_at": datetime.now().isoformat() + "Z"
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=sample_created_payload,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                print("   ✅ Webhook received successfully")
            else:
                print(f"   ❌ Webhook failed with status {response.status_code}")
                
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Test 2: invitee.canceled event
    print("\n2️⃣ Testing invitee.canceled webhook event...")
    
    sample_canceled_payload = {
        "event": "invitee.canceled",
        "time": datetime.now().isoformat() + "Z",
        "payload": {
            "event": "https://api.calendly.com/scheduled_events/TEST_EVENT_123",
            "invitee": "https://api.calendly.com/scheduled_events/TEST_EVENT_123/invitees/TEST_INVITEE_456",
            "canceled_at": datetime.now().isoformat() + "Z"
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=sample_canceled_payload,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                print("   ✅ Webhook received successfully")
            else:
                print(f"   ❌ Webhook failed with status {response.status_code}")
                
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Test 3: Unknown event type
    print("\n3️⃣ Testing unknown event type...")
    
    sample_unknown_payload = {
        "event": "invitee.updated",
        "time": datetime.now().isoformat() + "Z",
        "payload": {}
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=sample_unknown_payload,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                print("   ✅ Webhook received (expected to not process unknown event)")
            else:
                print(f"   ⚠️  Webhook returned status {response.status_code}")
                
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Test 4: Check webhook status
    print("\n4️⃣ Checking webhook status...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/calendly/webhook/status")
            
            print(f"   Status Code: {response.status_code}")
            if response.status_code == 200:
                status = response.json()
                print(f"   Total Events: {status.get('total_events_received', 0)}")
                print(f"   Processed: {status.get('processed_events', 0)}")
                print(f"   Failed: {status.get('failed_events', 0)}")
                print(f"   Success Rate: {status.get('success_rate', 0)}%")
                print("   ✅ Status retrieved successfully")
            else:
                print(f"   ❌ Failed to get status: {response.status_code}")
                
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Test 5: Check webhook logs
    print("\n5️⃣ Checking webhook logs...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/calendly/webhook/logs?limit=10")
            
            print(f"   Status Code: {response.status_code}")
            if response.status_code == 200:
                logs_data = response.json()
                logs_count = logs_data.get('count', 0)
                print(f"   Logs Retrieved: {logs_count}")
                print("   ✅ Logs retrieved successfully")
                
                if logs_count > 0:
                    print(f"\n   Recent Events:")
                    for i, log in enumerate(logs_data.get('logs', [])[-5:], 1):
                        event_type = log.get('event_type', 'unknown')
                        processed = "✅" if log.get('processed') else "❌"
                        timestamp = log.get('received_at', 'N/A')
                        print(f"   {i}. {processed} {event_type} at {timestamp}")
            else:
                print(f"   ❌ Failed to get logs: {response.status_code}")
                
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ Webhook testing completed!")
    print("\n💡 Tips:")
    print("   - Check server logs for detailed webhook processing information")
    print("   - Use /api/calendly/webhook/status to monitor webhook health")
    print("   - Use /api/calendly/webhook/logs to view recent events")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Calendly webhook endpoint")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the backend server (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    print(f"🌐 Testing webhook endpoint at: {args.url}")
    asyncio.run(test_webhook_endpoint(args.url))

