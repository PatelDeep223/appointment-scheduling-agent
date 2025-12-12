#!/usr/bin/env python3
"""
Helper script to fetch Calendly event type UUIDs
Run this to get your real event type UUIDs for configuration
"""

import os
import sys
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def get_event_types():
    """Fetch event types from Calendly API"""
    
    api_key = os.getenv("CALENDLY_API_KEY")
    if not api_key:
        print("❌ Error: CALENDLY_API_KEY not found in environment variables")
        print("   Please set it in your .env file")
        return
    
    print("🔍 Fetching your Calendly event types...\n")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        # First, get current user info
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                "https://api.calendly.com/users/me",
                headers=headers
            )
            user_response.raise_for_status()
            user_data = user_response.json()
            user_uri = user_data["resource"]["uri"]
            print(f"✅ Connected as: {user_data['resource']['name']}")
            print(f"   User URI: {user_uri}\n")
            
            # Get event types
            event_types_response = await client.get(
                f"https://api.calendly.com/event_types",
                headers=headers,
                params={"user": user_uri}
            )
            event_types_response.raise_for_status()
            event_types_data = event_types_response.json()
            
            event_types = event_types_data.get("collection", [])
            
            if not event_types:
                print("❌ No event types found in your Calendly account")
                print("   Please create event types in your Calendly account first")
                return
            
            print(f"✅ Found {len(event_types)} event type(s):\n")
            print("=" * 80)
            
            for i, event_type in enumerate(event_types, 1):
                # Handle both direct resource and nested resource structures
                if isinstance(event_type, dict):
                    if "resource" in event_type:
                        resource = event_type["resource"]
                    else:
                        resource = event_type
                else:
                    resource = event_type
                
                name = resource.get("name", "Unnamed") if isinstance(resource, dict) else "Unnamed"
                uri = resource.get("uri", "") if isinstance(resource, dict) else ""
                uuid = uri.split("/")[-1] if uri else "N/A"
                duration = resource.get("duration", 0) if isinstance(resource, dict) else 0
                kind = resource.get("kind", "") if isinstance(resource, dict) else ""
                active = resource.get("active", False) if isinstance(resource, dict) else False
                
                print(f"\n{i}. {name}")
                print(f"   UUID: {uuid}")
                print(f"   Duration: {duration} minutes")
                print(f"   Type: {kind}")
                print(f"   Status: {'Active' if active else 'Inactive'}")
                print(f"   URI: {uri}")
            
            print("\n" + "=" * 80)
            print("\n📝 Configuration Suggestion:")
            print("\nUpdate your backend/api/calendly_integration.py with these UUIDs:")
            print("\nappointment_types = {")
            
            # Suggest mappings based on duration
            for event_type in event_types:
                # Handle both direct resource and nested resource structures
                if isinstance(event_type, dict):
                    if "resource" in event_type:
                        resource = event_type["resource"]
                    else:
                        resource = event_type
                else:
                    resource = event_type
                
                name = resource.get("name", "") if isinstance(resource, dict) else "Unnamed"
                uri = resource.get("uri", "") if isinstance(resource, dict) else ""
                uuid = uri.split("/")[-1] if uri else "N/A"
                duration = resource.get("duration", 0) if isinstance(resource, dict) else 0
                
                # Map based on duration
                if duration <= 20:
                    appt_type = "followup"
                elif duration <= 35:
                    appt_type = "consultation"
                elif duration <= 50:
                    appt_type = "physical"
                else:
                    appt_type = "specialist"
                
                print(f'    "{appt_type}": {{')
                print(f'        "name": "{name}",')
                print(f'        "duration": {duration},')
                print(f'        "uuid": "{uuid}"')
                print('    },')
            
            print("}")
            print("\n✅ Done!")
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print("❌ Error: Invalid API key (401 Unauthorized)")
            print("   Please check your CALENDLY_API_KEY in .env file")
        elif e.response.status_code == 403:
            print("❌ Error: API key doesn't have required permissions (403 Forbidden)")
        else:
            print(f"❌ HTTP Error {e.response.status_code}: {e.response.text}")
    except KeyError as e:
        print(f"❌ Error: Missing key in API response - {str(e)}")
        print("   This might be due to unexpected API response format.")
        print("   Debug info: Check if event_types response structure is correct")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(get_event_types())

