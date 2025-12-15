#!/usr/bin/env python3
"""
Manually sync a booking from Calendly using invitee URI
Useful when webhook is not received but booking exists in Calendly
"""

import sys
import os
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx

# Get invitee URI from Calendly URL
# Example: https://calendly.com/meeting-scheduler2025/medical-appointment/invitees/bb24473a-300d-4754-85ad-e421d9361118
# Invitee URI: https://api.calendly.com/scheduled_events/{event_uri}/invitees/bb24473a-300d-4754-85ad-e421d9361118

async def sync_booking_from_invitee_id(invitee_id: str, days_back: int = 30, max_events: int = 100):
    """Sync booking from Calendly using invitee ID
    
    Args:
        invitee_id: The invitee ID or UUID
        days_back: Number of days to search back (default: 30)
        max_events: Maximum number of events to search (default: 100)
    """
    
    api_key = os.getenv("CALENDLY_API_KEY")
    if not api_key:
        print("❌ CALENDLY_API_KEY not set in environment variables")
        print("   Please set it in your .env file")
        return False
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print(f"🔍 Searching for invitee: {invitee_id}")
    print(f"   Searching events from the last {days_back} days (max {max_events} events)")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get current user
            user_response = await client.get(
                "https://api.calendly.com/users/me",
                headers=headers
            )
            user_response.raise_for_status()
            user_data = user_response.json()
            user_uri = user_data["resource"]["uri"]
            print(f"✅ Found user: {user_data['resource']['name']}")
            
            # Get scheduled events for this user
            from datetime import datetime, timedelta
            start_time = (datetime.now() - timedelta(days=days_back)).isoformat() + "Z"
            
            # Search through events with pagination if needed
            events_searched = 0
            page_token = None
            
            while events_searched < max_events:
                params = {
                    "user": user_uri,
                    "min_start_time": start_time,
                    "count": min(100, max_events - events_searched)  # Calendly max is 100
                }
                if page_token:
                    params["page_token"] = page_token
                
                events_response = await client.get(
                    "https://api.calendly.com/scheduled_events",
                    headers=headers,
                    params=params
                )
                events_response.raise_for_status()
                events_data = events_response.json()
                events = events_data.get('collection', [])
                
                if not events:
                    break
                
                print(f"📅 Searching {len(events)} events (total searched: {events_searched})...")
                
                # Search for invitee in events
                for event in events:
                    event_uri = event["uri"]
                    
                    # Get invitees for this event
                    try:
                        invitees_response = await client.get(
                            f"{event_uri}/invitees",
                            headers=headers,
                            timeout=10.0
                        )
                        
                        if invitees_response.status_code == 200:
                            invitees_data = invitees_response.json()
                            for invitee in invitees_data.get("collection", []):
                                invitee_uri = invitee.get("uri", "")
                                # Match by UUID (last part of URI) or full URI
                                if invitee_id in invitee_uri or invitee_uri.endswith(invitee_id):
                                    print(f"\n✅ Found booking!")
                                    print(f"   Event URI: {event_uri}")
                                    print(f"   Invitee URI: {invitee_uri}")
                                    print(f"   Name: {invitee.get('name', 'N/A')}")
                                    print(f"   Email: {invitee.get('email', 'N/A')}")
                                    
                                    # Now manually trigger webhook processing
                                    webhook_payload = {
                                        "event": "invitee.created",
                                        "time": invitee.get("created_at", datetime.now().isoformat() + "Z"),
                                        "payload": {
                                            "event": event_uri,
                                            "invitee": invitee_uri
                                        }
                                    }
                                    
                                    # Send to webhook endpoint
                                    webhook_url = os.getenv("WEBHOOK_URL", "http://localhost:8000/api/calendly/webhook")
                                    try:
                                        webhook_response = await client.post(
                                            webhook_url,
                                            json=webhook_payload,
                                            headers={"Content-Type": "application/json"},
                                            timeout=30.0
                                        )
                                        
                                        if webhook_response.status_code == 200:
                                            print(f"\n✅ Successfully synced booking to webhook endpoint")
                                            try:
                                                response_data = webhook_response.json()
                                                print(f"   Response: {response_data}")
                                            except:
                                                print(f"   Response: {webhook_response.text}")
                                            return True
                                        else:
                                            print(f"\n❌ Failed to sync: HTTP {webhook_response.status_code}")
                                            print(f"   Response: {webhook_response.text}")
                                            return False
                                    except Exception as webhook_error:
                                        print(f"\n❌ Error sending to webhook: {str(webhook_error)}")
                                        return False
                    except httpx.HTTPStatusError as e:
                        # Skip events where we can't get invitees (might be deleted/cancelled)
                        if e.response.status_code != 404:
                            print(f"   ⚠️  Could not get invitees for event: {e.response.status_code}")
                        continue
                    except Exception as e:
                        print(f"   ⚠️  Error checking event invitees: {str(e)}")
                        continue
                
                events_searched += len(events)
                
                # Check for pagination
                pagination = events_data.get("pagination", {})
                page_token = pagination.get("next_page_token")
                if not page_token:
                    break
            
            print(f"\n❌ Invitee {invitee_id} not found in {events_searched} events from the last {days_back} days")
            print(f"💡 Suggestions:")
            print(f"   - Verify the invitee ID is correct")
            print(f"   - Try searching older events (increase --days)")
            print(f"   - Check if the booking was cancelled or deleted")
            return False
            
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Sync booking from Calendly invitee ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/sync_booking.py bb24473a-300d-4754-85ad-e421d9361118
  python scripts/sync_booking.py https://calendly.com/.../invitees/bb24473a-300d-4754-85ad-e421d9361118
  python scripts/sync_booking.py bb24473a-300d-4754-85ad-e421d9361118 --days 60
        """
    )
    parser.add_argument("invitee_id", help="Calendly invitee ID or full URL with invitee ID")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to search back (default: 30, max recommended: 365)"
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=100,
        help="Maximum number of events to search (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Extract invitee ID from URL if full URL provided
    invitee_id = args.invitee_id
    if "/invitees/" in invitee_id:
        invitee_id = invitee_id.split("/invitees/")[-1].split("/")[0].split("?")[0]
    
    # Validate invitee ID format (should be UUID-like)
    if len(invitee_id) < 10:
        print(f"❌ Invalid invitee ID format: {invitee_id}")
        print("   Expected UUID format like: bb24473a-300d-4754-85ad-e421d9361118")
        sys.exit(1)
    
    print(f"🔄 Syncing booking for invitee: {invitee_id}")
    success = asyncio.run(sync_booking_from_invitee_id(invitee_id, args.days, args.max_events))
    sys.exit(0 if success else 1)

