#!/usr/bin/env python3
"""
Verify webhook setup and connectivity
Tests if webhook endpoint is accessible and working correctly
"""

import sys
import os
import json
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx


async def verify_webhook_setup(base_url: str):
    """
    Verify webhook endpoint is accessible and working
    
    Args:
        base_url: Base URL of the backend server (e.g., https://susy-cany-alida.ngrok-free.dev)
    """
    # Remove /docs if present
    base_url = base_url.rstrip('/docs').rstrip('/')
    
    webhook_url = f"{base_url}/api/calendly/webhook"
    status_url = f"{base_url}/api/calendly/webhook/status"
    health_url = f"{base_url}/"
    
    print("🔍 Verifying Webhook Setup")
    print("=" * 70)
    print(f"🌐 Base URL: {base_url}")
    print(f"📡 Webhook URL: {webhook_url}")
    print("=" * 70)
    
    results = {
        "health_check": False,
        "webhook_endpoint": False,
        "status_endpoint": False,
        "webhook_functionality": False
    }
    
    # Test 1: Health Check
    print("\n1️⃣ Testing server health...")
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(health_url)
            if response.status_code == 200:
                print(f"   ✅ Server is running (Status: {response.status_code})")
                results["health_check"] = True
            else:
                print(f"   ⚠️  Server responded with status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error connecting to server: {str(e)}")
        print(f"   💡 Make sure your backend is running and ngrok URL is correct")
        return results
    
    # Test 2: Webhook endpoint exists
    print("\n2️⃣ Testing webhook endpoint accessibility...")
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Send a test webhook payload
            test_payload = {
                "event": "invitee.created",
                "time": datetime.now().isoformat() + "Z",
                "payload": {
                    "event": "https://api.calendly.com/scheduled_events/TEST123",
                    "invitee": "https://api.calendly.com/scheduled_events/TEST123/invitees/TEST456"
                }
            }
            
            response = await client.post(
                webhook_url,
                json=test_payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"   ✅ Webhook endpoint is accessible (Status: {response.status_code})")
                response_data = response.json()
                print(f"   📦 Response: {json.dumps(response_data, indent=6)}")
                results["webhook_endpoint"] = True
                results["webhook_functionality"] = response_data.get("processed", False)
            else:
                print(f"   ❌ Webhook endpoint returned status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
    except httpx.ConnectError as e:
        print(f"   ❌ Cannot connect to webhook endpoint")
        print(f"   Error: {str(e)}")
        print(f"   💡 Check if ngrok URL is correct and backend is running")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Test 3: Status endpoint
    print("\n3️⃣ Testing webhook status endpoint...")
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(status_url)
            if response.status_code == 200:
                status_data = response.json()
                print(f"   ✅ Status endpoint is accessible")
                print(f"   📊 Webhook Statistics:")
                print(f"      • Total Events Received: {status_data.get('total_events_received', 0)}")
                print(f"      • Processed Events: {status_data.get('processed_events', 0)}")
                print(f"      • Failed Events: {status_data.get('failed_events', 0)}")
                print(f"      • Success Rate: {status_data.get('success_rate', 0)}%")
                print(f"      • Pending Bookings: {status_data.get('pending_bookings_count', 0)}")
                print(f"      • Confirmed Bookings: {status_data.get('confirmed_bookings_count', 0)}")
                
                if status_data.get('last_event_received'):
                    print(f"      • Last Event: {status_data.get('last_event_received')}")
                
                results["status_endpoint"] = True
            else:
                print(f"   ❌ Status endpoint returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 Verification Summary")
    print("=" * 70)
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} - {test_name.replace('_', ' ').title()}")
    
    print("=" * 70)
    
    if all_passed:
        print("\n🎉 All tests passed! Webhook is ready to use.")
        print(f"\n📝 Next Steps:")
        print(f"   1. Configure webhook in Calendly:")
        print(f"      URL: {webhook_url}")
        print(f"      Events: invitee.created, invitee.canceled")
        print(f"   2. Create a test booking in Calendly")
        print(f"   3. Check status: {status_url}")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print(f"\n💡 Tips:")
        print(f"   • Make sure backend is running")
        print(f"   • Verify ngrok URL is correct")
        print(f"   • Check if ngrok tunnel is active")
        print(f"   • Visit {base_url}/docs to see API documentation")
    
    return results


async def check_webhook_logs(base_url: str, limit: int = 10):
    """Check recent webhook logs"""
    base_url = base_url.rstrip('/docs').rstrip('/')
    logs_url = f"{base_url}/api/calendly/webhook/logs?limit={limit}"
    
    print(f"\n📜 Recent Webhook Logs (last {limit} events)")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(logs_url)
            if response.status_code == 200:
                logs_data = response.json()
                logs = logs_data.get('logs', [])
                
                if not logs:
                    print("   📭 No webhook events received yet")
                    print("   💡 Create a test booking in Calendly to generate events")
                else:
                    for i, log in enumerate(logs, 1):
                        event_type = log.get('event_type', 'unknown')
                        processed = "✅" if log.get('processed') else "❌"
                        timestamp = log.get('received_at', 'N/A')
                        error = log.get('error')
                        
                        print(f"   {i}. {processed} {event_type}")
                        print(f"      Received: {timestamp}")
                        if error:
                            print(f"      Error: {error}")
                        print()
            else:
                print(f"   ❌ Failed to get logs: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Verify webhook setup and connectivity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify webhook with ngrok URL
  python backend/scripts/verify_webhook.py --url https://susy-cany-alida.ngrok-free.dev

  # Verify and show logs
  python backend/scripts/verify_webhook.py --url https://susy-cany-alida.ngrok-free.dev --logs

  # Check logs only
  python backend/scripts/verify_webhook.py --url https://susy-cany-alida.ngrok-free.dev --logs-only
        """
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the backend server (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="Show webhook logs after verification"
    )
    parser.add_argument(
        "--logs-only",
        action="store_true",
        help="Only show webhook logs (skip verification)"
    )
    
    args = parser.parse_args()
    
    if args.logs_only:
        asyncio.run(check_webhook_logs(args.url))
    else:
        results = asyncio.run(verify_webhook_setup(args.url))
        if args.logs:
            asyncio.run(check_webhook_logs(args.url))

