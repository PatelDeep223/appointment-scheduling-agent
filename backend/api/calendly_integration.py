"""
Calendly API Integration
Handles availability checking and appointment booking
Includes mock implementation for development
"""

import os
import json
import random
import string
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, time
from urllib.parse import urlencode, quote
import httpx


class CalendlyClient:
    """
    Calendly API client for managing appointments
    Supports both real Calendly API and mock implementation
    """
    
    def __init__(self):
        self.api_key = os.getenv("CALENDLY_API_KEY")
        self.user_url = os.getenv("CALENDLY_USER_URL")
        self.base_url = "https://api.calendly.com"
        
        # Appointment type configurations
        # Real Calendly event type UUIDs (fetched from your Calendly account)
        # 
        # To update these UUIDs with your actual Calendly event types:
        # 1. Run: python backend/scripts/get_calendly_event_types.py
        # 2. Or use the diagnostic endpoint: GET /api/calendly/test
        # 3. Copy the UUIDs from the output and update the "uuid" fields below
        # 4. Update "name" and "duration" to match your actual event types
        self.appointment_types = {
            "consultation": {
                "name": "General Consultation",
                "duration": 30,
                "uuid": "abd38296-0ecc-4834-8a9d-30f2764f6d36"  # Real UUID from Calendly
            },
            "followup": {
                "name": "Follow-up",
                "duration": 15,
                "uuid": "fbc6a86a-dd62-453f-8f3f-e67142d3c252"  # Real UUID from Calendly
            },
            "physical": {
                "name": "Physical Exam",
                "duration": 45,
                "uuid": "08bbf513-9bb8-4259-ac72-15c0babe9dbe"  # Real UUID from Calendly
            },
            "specialist": {
                "name": "Specialist Consultation",
                "duration": 60,
                "uuid": "4a1b7b7e-cae8-4ea1-9b6b-31ab96aa95d8"  # Real UUID from Calendly
            }
        }
        
        # Check if we should use mock:
        # 1. No API key provided
        # 2. UUIDs are placeholders (don't start with real Calendly format)
        # Real Calendly UUIDs are longer alphanumeric strings (not starting with "evt_")
        # Also check if UUIDs look like real Calendly UUIDs (typically 10+ chars, alphanumeric)
        def is_real_uuid(uuid: str) -> bool:
            """Check if UUID looks like a real Calendly UUID"""
            # Placeholder UUIDs start with "evt_" and are short
            # Real Calendly UUIDs are longer alphanumeric strings
            return (not uuid.startswith("evt_") and 
                    len(uuid) >= 10 and 
                    uuid.replace("-", "").replace("_", "").isalnum())
        
        has_real_uuids = all(
            is_real_uuid(apt["uuid"])
            for apt in self.appointment_types.values()
        )
        
        self.use_mock = not self.api_key or not has_real_uuids
        
        # Business hours
        self.business_hours = {
            "monday": {"start": "08:00", "end": "18:00"},
            "tuesday": {"start": "08:00", "end": "18:00"},
            "wednesday": {"start": "08:00", "end": "18:00"},
            "thursday": {"start": "08:00", "end": "18:00"},
            "friday": {"start": "08:00", "end": "18:00"},
            "saturday": {"start": "09:00", "end": "14:00"},
            "sunday": None  # Closed
        }
        
        # Mock bookings storage
        self.mock_bookings: Dict[str, Dict] = {}
        
        # Real bookings storage (persisted from webhooks)
        # Key: Calendly event URI or invitee URI, Value: booking data
        self.real_bookings: Dict[str, Dict] = {}
        
        # Pending bookings (before webhook confirmation)
        # Key: temporary booking ID, Value: booking data
        self.pending_bookings: Dict[str, Dict] = {}
        
        # Webhook event logs (for monitoring and debugging)
        # List of webhook event dictionaries
        self.webhook_logs: List[Dict[str, Any]] = []
        self.max_webhook_logs = 100  # Keep last 100 webhook events
        
        # Track if we should fallback to mock after API errors
        self.api_error_count = 0
        self.max_api_errors = 2  # Fallback to mock after 2 errors
        
        if self.use_mock:
            print("📝 Using mock Calendly implementation (no valid API key or placeholder UUIDs detected)")
        else:
            print("🔗 Using real Calendly API")
    
    def _normalize_appointment_type(self, appointment_type: Optional[str]) -> str:
        """
        Normalize appointment type to internal key format.
        Maps display names like "General Consultation" to keys like "consultation"
        Also handles aliases like "special" -> "specialist"
        """
        # Handle None or empty values
        if not appointment_type:
            return "consultation"
        
        # Ensure it's a string
        appointment_type = str(appointment_type)
        appointment_type_lower = appointment_type.lower()
        
        # Handle aliases
        aliases = {
            "special": "specialist"  # Map "special" to "specialist" (as shown in API spec)
        }
        if appointment_type_lower in aliases:
            appointment_type_lower = aliases[appointment_type_lower]
        
        # First, try direct key lookup
        if appointment_type_lower in self.appointment_types:
            return appointment_type_lower
        
        # Try to find by name (case-insensitive)
        for key, config in self.appointment_types.items():
            if config["name"].lower() == appointment_type_lower:
                return key
        
        # If not found, default to "consultation"
        print(f"⚠️  Unknown appointment type '{appointment_type}', defaulting to 'consultation'")
        return "consultation"
    
    async def fetch_event_types(self) -> List[Dict[str, Any]]:
        """
        Fetch event types from Calendly API
        
        Returns:
            List of event type dictionaries with name, uuid, duration, etc.
        """
        if not self.api_key:
            raise Exception("Calendly API key is required. Please set CALENDLY_API_KEY environment variable.")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # First, get current user info
            async with httpx.AsyncClient() as client:
                user_response = await client.get(
                    f"{self.base_url}/users/me",
                    headers=headers
                )
                user_response.raise_for_status()
                user_data = user_response.json()
                user_uri = user_data["resource"]["uri"]
                
                # Get event types
                event_types_response = await client.get(
                    f"{self.base_url}/event_types",
                    headers=headers,
                )
                event_types_response.raise_for_status()
                event_types_data = event_types_response.json()
                
                event_types = event_types_data.get("collection", [])
                
                # Transform to simpler format
                result = []
                for event_type in event_types:
                    # Handle both direct resource and nested resource structures
                    if isinstance(event_type, dict):
                        if "resource" in event_type:
                            resource = event_type["resource"]
                        else:
                            resource = event_type
                    else:
                        resource = event_type
                    
                    if isinstance(resource, dict):
                        uri = resource.get("uri", "")
                        uuid = uri.split("/")[-1] if uri else ""
                        
                        result.append({
                            "name": resource.get("name", "Unnamed"),
                            "uuid": uuid,
                            "duration": resource.get("duration", 0),
                            "kind": resource.get("kind", ""),
                            "active": resource.get("active", False),
                            "uri": uri
                        })
                
                return result
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception("Invalid Calendly API key (401 Unauthorized). Please check your CALENDLY_API_KEY.")
            elif e.response.status_code == 403:
                raise Exception("API key doesn't have required permissions (403 Forbidden).")
            else:
                raise Exception(f"Calendly API error: HTTP {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Error fetching event types: {str(e)}")
    
    async def get_availability(
        self,
        date: str,
        appointment_type: str = "Consultation"
    ) -> Dict[str, Any]:
        """
        Get available time slots for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            appointment_type: Type of appointment (can be display name or key)
        
        Returns:
            Dictionary with available slots
        """
        # Normalize appointment type to internal key
        normalized_type = self._normalize_appointment_type(appointment_type)
        
        # Only use real API if we have credentials and haven't exceeded error threshold
        if not self.use_mock and self.api_error_count < self.max_api_errors:
            try:
                result = await self._real_get_availability(date, normalized_type)
                self.api_error_count = 0  # Reset on success
                return result
            except Exception as e:
                # On API error, increment counter but don't fallback to mock
                # Instead, raise the error so the caller can handle it
                self.api_error_count += 1
                error_msg = f"Calendly API error: {str(e)}"
                print(f"❌ {error_msg}")
                
                # Only fallback to mock if we've exceeded max errors AND no API key
                if self.api_error_count >= self.max_api_errors and not self.api_key:
                    print(f"⚠️  Falling back to mock mode (no API key available).")
                    self.use_mock = True
                    return await self._mock_get_availability(date, normalized_type)
                else:
                    # Re-raise the error to be handled by the caller
                    raise Exception(error_msg)
        
        # Use mock only if explicitly set or no API key
        if self.use_mock or not self.api_key:
            return await self._mock_get_availability(date, normalized_type)
        
        # Should not reach here, but just in case
        raise Exception("Unable to get availability: API key required but not configured")
    
    async def create_booking(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Create a new appointment booking
        
        Args:
            appointment_type: Type of appointment (can be display name or key)
            date: Date in YYYY-MM-DD format
            start_time: Start time in HH:MM format
            patient_name: Patient's full name
            patient_email: Patient's email
            patient_phone: Patient's phone number
            reason: Reason for visit
        
        Returns:
            Booking confirmation details
        """
        # Normalize appointment type to internal key
        normalized_type = self._normalize_appointment_type(appointment_type)
        
        # Only use real API if we have credentials and haven't exceeded error threshold
        if not self.use_mock and self.api_error_count < self.max_api_errors:
            try:
                result = await self._real_create_booking(
                    normalized_type, date, start_time,
                    patient_name, patient_email, patient_phone, reason
                )
                self.api_error_count = 0  # Reset on success
                return result
            except Exception as e:
                # On API error, increment counter but don't fallback to mock
                self.api_error_count += 1
                error_msg = f"Calendly API error: {str(e)}"
                print(f"❌ {error_msg}")
                
                # Only fallback to mock if we've exceeded max errors AND no API key
                if self.api_error_count >= self.max_api_errors and not self.api_key:
                    print(f"⚠️  Falling back to mock mode (no API key available).")
                    self.use_mock = True
                    return await self._mock_create_booking(
                        normalized_type, date, start_time,
                        patient_name, patient_email, patient_phone, reason
                    )
                else:
                    # Re-raise the error to be handled by the caller
                    raise Exception(error_msg)
        
        # Use mock only if explicitly set or no API key
        if self.use_mock or not self.api_key:
            return await self._mock_create_booking(
                normalized_type, date, start_time,
                patient_name, patient_email, patient_phone, reason
            )
        
        # Should not reach here, but just in case
        raise Exception("Unable to create booking: API key required but not configured")
    
    async def cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """Cancel an existing booking"""
        # Only use real API if we have credentials and haven't exceeded error threshold
        if not self.use_mock and self.api_error_count < self.max_api_errors:
            try:
                result = await self._real_cancel_booking(booking_id)
                self.api_error_count = 0  # Reset on success
                return result
            except Exception as e:
                # On API error, increment counter but don't fallback to mock
                self.api_error_count += 1
                error_msg = f"Calendly API error: {str(e)}"
                print(f"❌ {error_msg}")
                
                # Only fallback to mock if we've exceeded max errors AND no API key
                if self.api_error_count >= self.max_api_errors and not self.api_key:
                    print(f"⚠️  Falling back to mock mode (no API key available).")
                    self.use_mock = True
                    return await self._mock_cancel_booking(booking_id)
                else:
                    # Re-raise the error to be handled by the caller
                    raise Exception(error_msg)
        
        # Use mock only if explicitly set or no API key
        if self.use_mock or not self.api_key:
            return await self._mock_cancel_booking(booking_id)
        
        # Should not reach here, but just in case
        raise Exception("Unable to cancel booking: API key required but not configured")
    
    # Mock Implementation Methods
    
    async def _mock_get_availability(
        self,
        date: str,
        appointment_type: str
    ) -> Dict[str, Any]:
        """Mock implementation of availability checking"""
        
        # Normalize appointment type to ensure we have a valid key
        normalized_type = self._normalize_appointment_type(appointment_type)
        
        # Parse date
        target_date = datetime.strptime(date, "%Y-%m-%d")
        day_name = target_date.strftime("%A").lower()
        
        # Check if clinic is open
        hours = self.business_hours.get(day_name)
        if not hours:
            return {
                "date": date,
                "appointment_type": self.appointment_types[normalized_type]["name"],
                "available_slots": [],
                "message": "Clinic is closed on this day"
            }
        
        # Generate time slots
        appt_duration = self.appointment_types[normalized_type]["duration"]
        start_time = datetime.strptime(hours["start"], "%H:%M").time()
        end_time = datetime.strptime(hours["end"], "%H:%M").time()
        
        slots = []
        current = datetime.combine(target_date.date(), start_time)
        end_datetime = datetime.combine(target_date.date(), end_time)
        
        while current + timedelta(minutes=appt_duration) <= end_datetime:
            slot_time = current.strftime("%I:%M %p")
            
            # Randomly mark some slots as unavailable (simulate bookings)
            is_available = random.random() > 0.3  # 70% availability
            
            # Check if slot conflicts with existing bookings
            booking_key = f"{date}_{current.strftime('%H:%M')}"
            if booking_key in self.mock_bookings:
                is_available = False
            
            slots.append({
                "start_time": slot_time,
                "end_time": (current + timedelta(minutes=appt_duration)).strftime("%I:%M %p"),
                "available": is_available,
                "raw_time": current.strftime("%H:%M")
            })
            
            current += timedelta(minutes=30)  # 30-minute intervals
        
        return {
            "date": date,
            "appointment_type": self.appointment_types[normalized_type]["name"],
            "available_slots": slots
        }
    
    async def _mock_create_booking(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str
    ) -> Dict[str, Any]:
        """Mock implementation of booking creation"""
        
        # Normalize appointment type to ensure we have a valid key
        normalized_type = self._normalize_appointment_type(appointment_type)
        
        # Generate booking ID and confirmation code
        booking_id = f"APPT-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.digits, k=3))}"
        confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Calculate end time
        duration = self.appointment_types[normalized_type]["duration"]
        start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_datetime = start_datetime + timedelta(minutes=duration)
        
        # Generate a mock Calendly scheduling link (for demo purposes)
        # In production, this would be a real Calendly link
        mock_calendly_username = self.user_url.replace("https://calendly.com/", "").replace("http://calendly.com/", "").split("/")[0] if self.user_url else "demo-clinic"
        event_slug = normalized_type  # Use appointment type as slug
        scheduling_link = f"https://calendly.com/{mock_calendly_username}/{event_slug}?name={quote(patient_name)}&email={quote(patient_email)}&a1={quote(patient_phone)}"
        
        # Store booking
        booking_key = f"{date}_{start_time}"
        booking = {
            "booking_id": booking_id,
            "confirmation_code": confirmation_code,
            "appointment_type": self.appointment_types[normalized_type]["name"],
            "date": date,
            "start_time": start_time,
            "end_time": end_datetime.strftime("%H:%M"),
            "duration": duration,
            "patient_name": patient_name,
            "patient_email": patient_email,
            "patient_phone": patient_phone,
            "reason": reason,
            "status": "confirmed",
            "scheduling_link": scheduling_link,  # Add scheduling link for mock bookings
            "created_at": datetime.now().isoformat(),
            "clinic_info": {
                "name": "HealthCare Plus Clinic",
                "address": "123 Health Street, Medical District, NY 10001",
                "phone": "+1-555-123-4567",
                "email": "info@healthcareplus.com"
            }
        }
        
        self.mock_bookings[booking_key] = booking
        
        print(f"✅ Mock booking created: {booking_id}")
        print(f"📅 Mock scheduling link: {scheduling_link}")
        
        return booking
    
    async def _mock_cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """Mock implementation of booking cancellation"""
        
        # Find and remove booking
        for key, booking in list(self.mock_bookings.items()):
            if booking["booking_id"] == booking_id:
                del self.mock_bookings[key]
                print(f"🗑️ Mock booking cancelled: {booking_id}")
                return {
                    "booking_id": booking_id,
                    "status": "cancelled",
                    "message": "Appointment cancelled successfully"
                }
        
        return {
            "error": "Booking not found",
            "booking_id": booking_id
        }
    
    # Real Calendly API Methods
    
    async def _real_get_availability(
        self,
        date: str,
        appointment_type: str
    ) -> Dict[str, Any]:
        """
        Real Calendly API implementation for getting availability
        
        Uses the Calendly API v2 endpoint: /event_type_available_times
        Documentation: https://developer.calendly.com/api-docs/ZG9jOjM2MzE2MDM4-event-type-available-times
        """
        
        if not self.api_key:
            raise Exception("Calendly API key is required but not configured. Please set CALENDLY_API_KEY environment variable.")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Normalize appointment type to ensure we have a valid key
        normalized_type = self._normalize_appointment_type(appointment_type)
        event_type_uuid = self.appointment_types[normalized_type]["uuid"]
        event_type_name = self.appointment_types[normalized_type]["name"]
        
        # Validate event type UUID format
        if not event_type_uuid or len(event_type_uuid) < 10:
            raise Exception(f"Invalid event type UUID for '{appointment_type}': {event_type_uuid}. Please verify your Calendly event type configuration.")
        
        # Calculate time range for the day
        # Calendly requires UTC timestamps
        target_date = datetime.strptime(date, "%Y-%m-%d")
        now = datetime.utcnow()  # Use UTC for API calls
        
        # If the date is today, start from current time + 1 hour
        # Otherwise, start from beginning of the day
        if target_date.date() == now.date():
            # Today - start from 1 hour from now (rounded to nearest hour)
            start_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            start_datetime = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            # Future date - start from beginning of day (00:00 UTC)
            start_datetime = f"{date}T00:00:00Z"
        
        # End of day (23:59:59 UTC)
        end_datetime = f"{date}T23:59:59Z"
        
        # Calendly API v2 endpoint: /event_type_available_times
        # Requires event_type as full URI, not just UUID
        url = f"{self.base_url}/event_type_available_times"
        params = {
            "event_type": f"https://api.calendly.com/event_types/{event_type_uuid}",
            "start_time": start_datetime,
            "end_time": end_datetime
        }
        
        # Debug logging
        print(f"\n🔍 Calendly API Availability Request:")
        print(f"   Endpoint: {url}")
        print(f"   Event Type: {event_type_name} (UUID: {event_type_uuid})")
        print(f"   Date: {date}")
        print(f"   Time Range: {start_datetime} to {end_datetime}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                
                # Log response status
                print(f"   Response Status: {response.status_code}")
                
                # Handle non-200 responses
                if response.status_code != 200:
                    error_text = response.text[:500] if response.text else "No error details"
                    print(f"   ❌ Error Response: {error_text}")
                    response.raise_for_status()
                
                data = response.json()
                
                # Debug logging for response structure
                print(f"   Response keys: {list(data.keys())}")
                
                # Transform Calendly response to our format
                slots = []
                # Calendly API returns availability in "collection" array
                time_slots = data.get("collection", [])
                
                print(f"   Found {len(time_slots)} time slot(s) in response")
                
                # Log sample structure for debugging
                if time_slots and len(time_slots) > 0:
                    sample = time_slots[0]
                    if isinstance(sample, dict):
                        print(f"   Sample slot keys: {list(sample.keys())}")
                        if "resource" in sample:
                            print(f"   Resource keys: {list(sample['resource'].keys())}")
                elif not time_slots:
                    print(f"   ⚠️  No time slots in collection")
                    print(f"   Full response structure: {json.dumps(data, indent=2)[:800]}")
                
                # Parse each time slot
                for idx, time_slot in enumerate(time_slots):
                    try:
                        # Handle different possible response structures
                        # Calendly API may return items directly or nested in "resource" objects
                        resource = time_slot
                        if isinstance(time_slot, dict) and "resource" in time_slot:
                            resource = time_slot["resource"]
                        
                        if not isinstance(resource, dict):
                            print(f"   ⚠️  Slot {idx}: Not a dictionary, skipping")
                            continue
                        
                        # Get start time - Calendly uses "start_time" field
                        start_time_str = resource.get("start_time")
                        if not start_time_str:
                            # Try alternative field names
                            start_time_str = resource.get("start") or resource.get("startTime") or ""
                            if not start_time_str and isinstance(time_slot, dict):
                                start_time_str = time_slot.get("start_time", "")
                        
                        if not start_time_str:
                            print(f"   ⚠️  Slot {idx}: No start_time found, skipping")
                            print(f"      Resource keys: {list(resource.keys())}")
                            continue
                        
                        # Parse start time (Calendly uses ISO 8601 format with Z suffix)
                        try:
                            # Handle both "Z" and "+00:00" timezone formats
                            if start_time_str.endswith("Z"):
                                start = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                            else:
                                start = datetime.fromisoformat(start_time_str)
                        except ValueError as e:
                            print(f"   ⚠️  Slot {idx}: Error parsing start_time '{start_time_str}': {e}")
                            continue
                        
                        # Get end time or calculate from duration
                        end_time_str = resource.get("end_time") or resource.get("end") or resource.get("endTime") or ""
                        if not end_time_str and isinstance(time_slot, dict):
                            end_time_str = time_slot.get("end_time", "")
                        
                        if end_time_str:
                            try:
                                if end_time_str.endswith("Z"):
                                    end = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                                else:
                                    end = datetime.fromisoformat(end_time_str)
                            except ValueError:
                                # Fallback to calculating from duration
                                duration = self.appointment_types[normalized_type]["duration"]
                                end = start + timedelta(minutes=duration)
                        else:
                            # Calculate end time from duration
                            duration = self.appointment_types[normalized_type]["duration"]
                            end = start + timedelta(minutes=duration)
                        
                        # Check availability
                        # Calendly uses "invitees_remaining" to indicate availability
                        is_available = True
                        if "invitees_remaining" in resource:
                            invitees_remaining = resource.get("invitees_remaining", 0)
                            is_available = invitees_remaining > 0
                        elif "invitees_remaining" in time_slot:
                            invitees_remaining = time_slot.get("invitees_remaining", 0)
                            is_available = invitees_remaining > 0
                        elif "status" in resource:
                            status = resource.get("status", "").lower()
                            is_available = status in ["available", "open"]
                        elif "status" in time_slot:
                            status = time_slot.get("status", "").lower()
                            is_available = status in ["available", "open"]
                        # If no availability indicator, assume available if slot exists
                        else:
                            is_available = True
                        
                        # Get event URI if available (for direct booking)
                        event_uri = resource.get("uri") or resource.get("event_uri") or ""
                        if not event_uri and isinstance(time_slot, dict):
                            event_uri = time_slot.get("uri") or time_slot.get("event_uri") or ""
                        
                        # Only include available slots
                        if is_available:
                            slot_data = {
                                "start_time": start.strftime("%I:%M %p"),
                                "end_time": end.strftime("%I:%M %p"),
                                "available": True,
                                "raw_time": start.strftime("%H:%M"),
                                "start_datetime_iso": start_time_str  # Store ISO datetime
                            }
                            
                            # Add event URI if available (for direct booking)
                            if event_uri:
                                slot_data["event_uri"] = event_uri
                            
                            slots.append(slot_data)
                    
                    except Exception as slot_error:
                        print(f"   ⚠️  Error processing slot {idx}: {slot_error}")
                        continue
                
                print(f"   ✅ Successfully parsed {len(slots)} available slot(s)")
                
                # Prepare response
                result = {
                    "date": date,
                    "appointment_type": event_type_name,
                    "available_slots": slots
                }
                
                if not slots:
                    result["message"] = (
                        "No available slots found for this date. Possible reasons:\n"
                        "1. Your Calendly availability schedule may not be configured for this date\n"
                        "2. The event type may not have availability set for this date\n"
                        "3. All slots for this date may already be booked\n"
                        "4. The date may be outside your availability window\n"
                        f"5. Verify the event type '{event_type_name}' (UUID: {event_type_uuid}) is active in your Calendly account"
                    )
                    print(f"   ⚠️  {result['message']}")
                
                return result
                
        except httpx.TimeoutException:
            error_msg = "Calendly API request timed out. Please try again later."
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except httpx.HTTPStatusError as e:
            # Provide detailed error information
            error_detail = f"HTTP {e.response.status_code}"
            try:
                error_body = e.response.json()
                error_message = error_body.get('message', error_body.get('title', error_body.get('detail', str(e))))
                error_detail += f": {error_message}"
                
                # Log full error for debugging
                print(f"   ❌ Full error response: {json.dumps(error_body, indent=2)[:500]}")
            except:
                error_detail += f": {e.response.text[:200] if e.response.text else str(e)}"
            
            if e.response.status_code in [401, 403]:
                error_msg = (
                    f"Calendly API authentication error ({e.response.status_code}). "
                    "Please check:\n"
                    "1. Your CALENDLY_API_KEY is correct\n"
                    "2. The API key has not expired\n"
                    "3. The API key has the required permissions"
                )
                print(f"⚠️  {error_msg}")
            elif e.response.status_code == 404:
                error_msg = (
                    f"Calendly event type not found (404). "
                    f"Please verify:\n"
                    f"1. Event type UUID '{event_type_uuid}' exists in your Calendly account\n"
                    f"2. The event type is active and accessible\n"
                    f"3. Use GET /api/calendly/test to fetch your actual event types"
                )
                print(f"⚠️  {error_msg}")
            elif e.response.status_code == 422:
                error_msg = (
                    f"Calendly API validation error (422). "
                    f"Please check:\n"
                    f"1. The date format is correct (YYYY-MM-DD)\n"
                    f"2. The date is not in the past\n"
                    f"3. The time range is valid\n"
                    f"Error details: {error_detail}"
                )
                print(f"⚠️  {error_msg}")
            else:
                error_msg = f"Calendly API error: {error_detail}"
                print(f"❌ {error_msg}")
            
            raise Exception(error_msg)
        except httpx.RequestError as e:
            error_msg = f"Network error connecting to Calendly API: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error getting availability: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    async def _real_create_booking(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Real Calendly API booking implementation
        
        First tries to create booking directly using POST /invitees endpoint.
        If that fails or the time slot is not available, falls back to generating
        a scheduling link for the user to complete manually.
        """
        
        # NOTE: Direct booking via POST /invitees requires an existing scheduled event URI.
        # Calendly's /event_type_available_times endpoint only returns available time slots,
        # not event URIs. Event URIs only exist for already-scheduled events.
        # Therefore, we use the scheduling link method, which is the standard Calendly workflow.
        # The scheduling link is pre-filled with patient information for a seamless experience.
        
        # Use scheduling link method (this is the correct approach for new bookings)
        return await self._real_create_booking_via_link(
            appointment_type, date, start_time,
            patient_name, patient_email, patient_phone, reason
        )
    
    async def _real_create_booking_direct(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Create booking directly using Calendly POST /invitees endpoint
        
        This method:
        1. Gets available time slots for the requested date
        2. Finds the matching time slot
        3. Creates an invitee using POST /invitees
        4. Returns the confirmed booking details
        """
        
        if not self.api_key:
            raise Exception("Calendly API key is required but not configured. Please set CALENDLY_API_KEY environment variable.")
        
        # Normalize appointment type
        normalized_type = self._normalize_appointment_type(appointment_type)
        event_type_uuid = self.appointment_types[normalized_type]["uuid"]
        event_type_uri = f"https://api.calendly.com/event_types/{event_type_uuid}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Step 1: Get available time slots for the date
        print(f"🔍 Step 1: Getting available slots for {date}...")
        availability = await self._real_get_availability(date, appointment_type)
        available_slots = availability.get("available_slots", [])
        
        if not available_slots:
            raise Exception(f"No available time slots found for {date}")
        
        # Step 2: Find the matching time slot
        print(f"🔍 Step 2: Looking for time slot matching {start_time}...")
        
        # Parse the requested time
        try:
            # Try to parse as HH:MM format
            if ":" in start_time:
                time_parts = start_time.split(":")
                requested_hour = int(time_parts[0])
                requested_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            else:
                # Try to parse as "12 PM" format
                from datetime import datetime as dt
                time_obj = dt.strptime(start_time.upper().strip(), "%I:%M %p")
                requested_hour = time_obj.hour
                requested_minute = time_obj.minute
        except:
            raise Exception(f"Invalid time format: {start_time}. Please use HH:MM format.")
        
        # Find matching slot
        matching_slot = None
        for slot in available_slots:
            if not slot.get("available", False):
                continue
            
            slot_time = slot.get("raw_time", slot.get("start_time", ""))
            if ":" in slot_time:
                slot_parts = slot_time.split(":")
                slot_hour = int(slot_parts[0])
                slot_minute = int(slot_parts[1]) if len(slot_parts) > 1 else 0
                
                if slot_hour == requested_hour and slot_minute == requested_minute:
                    matching_slot = slot
                    break
        
        if not matching_slot:
            raise Exception(f"Time slot {start_time} is not available for {date}. Available times: {[s.get('start_time') for s in available_slots if s.get('available')]}")
        
        # Step 3: Get event URI from matching slot
        # NOTE: Calendly's /event_type_available_times endpoint does NOT return event URIs
        # Event URIs only exist for already-scheduled events. Since we're trying to create
        # a new booking, there's no scheduled event yet. We need to use the scheduling link method.
        event_uri = matching_slot.get("event_uri")
        start_datetime_iso = matching_slot.get("start_datetime_iso")
        
        if not event_uri:
            # This is expected - Calendly doesn't provide event URIs in available times
            # because events don't exist until they're booked. We must use scheduling link method.
            print(f"ℹ️  Note: Calendly API doesn't provide event URIs in available time slots.")
            print(f"   Event URIs only exist for already-scheduled events.")
            print(f"   Using scheduling link method (this is the correct approach for new bookings).")
            raise Exception("Event URI not found in available slot. Using scheduling link method.")
        
        # Step 4: Create invitee using POST /invitees endpoint
        print(f"🔍 Step 4: Creating invitee for event {event_uri}...")
        
        # Build invitee payload
        invitee_payload = {
            "event": event_uri,
            "name": patient_name,
            "email": patient_email
        }
        
        # Add phone if provided
        if patient_phone:
            invitee_payload["text_reminder_number"] = patient_phone
        
        # Add custom questions if reason is provided
        # Note: Custom questions depend on event type configuration
        # We'll add them if the event type supports them
        
        async with httpx.AsyncClient() as client:
            # Create invitee
            invitee_response = await client.post(
                f"{self.base_url}/invitees",
                headers=headers,
                json=invitee_payload
            )
            
            if invitee_response.status_code not in [200, 201]:
                error_text = invitee_response.text[:500] if invitee_response.text else "No error details"
                print(f"❌ Error creating invitee: {error_text}")
                raise Exception(f"Failed to create invitee: {invitee_response.status_code} - {error_text}")
            
            invitee_data = invitee_response.json()
            invitee_resource = invitee_data.get("resource", {})
            
            # Extract invitee details
            invitee_uri = invitee_resource.get("uri", "")
            invitee_uuid = invitee_uri.split("/")[-1] if "/" in invitee_uri else ""
            
            # Get full event details
            event_response = await client.get(event_uri, headers=headers)
            event_data = event_response.json()
            event_resource = event_data.get("resource", {})
            
            # Extract event details
            event_start_time = event_resource.get("start_time", start_datetime_iso)
            event_end_time = event_resource.get("end_time", "")
            
            # Generate booking ID (use invitee UUID)
            booking_id = invitee_uuid if invitee_uuid else f"INV-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.digits, k=6))}"
            confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            # Parse dates for display
            try:
                if event_start_time.endswith("Z"):
                    start_dt = datetime.fromisoformat(event_start_time.replace("Z", "+00:00"))
                else:
                    start_dt = datetime.fromisoformat(event_start_time)
                
                if event_end_time:
                    if event_end_time.endswith("Z"):
                        end_dt = datetime.fromisoformat(event_end_time.replace("Z", "+00:00"))
                    else:
                        end_dt = datetime.fromisoformat(event_end_time)
                else:
                    duration = self.appointment_types[normalized_type]["duration"]
                    end_dt = start_dt + timedelta(minutes=duration)
            except:
                start_dt = datetime.now()
                end_dt = start_dt + timedelta(minutes=self.appointment_types[normalized_type]["duration"])
            
            # Build booking response
            booking = {
                "booking_id": booking_id,
                "confirmation_code": confirmation_code,
                "status": "confirmed",  # Direct booking is immediately confirmed
                "appointment_type": self.appointment_types[normalized_type]["name"],
                "date": start_dt.strftime("%Y-%m-%d"),
                "start_time": start_dt.strftime("%H:%M"),
                "end_time": end_dt.strftime("%H:%M"),
                "patient_name": patient_name,
                "patient_email": patient_email,
                "patient_phone": patient_phone,
                "reason": reason,
                "calendly_event_uri": event_uri,
                "calendly_invitee_uri": invitee_uri,
                "reschedule_url": invitee_resource.get("reschedule_url", ""),
                "cancel_url": invitee_resource.get("cancel_url", ""),
                "created_at": datetime.now().isoformat(),
                "clinic_info": {
                    "name": "HealthCare Plus Clinic",
                    "address": "123 Health Street, Medical District, NY 10001",
                    "phone": "+1-555-123-4567"
                }
            }
            
            # Store in real_bookings
            self.real_bookings[event_uri] = booking
            
            # Save to database
            try:
                # Try direct import first (when running from backend/ directory)
                try:
                    from database import get_db
                    from services.booking_service import BookingService
                    from models.booking import BookingStatus
                except ImportError:
                    # Fallback to relative import (when running as package)
                    try:
                        from ..database import get_db
                        from ..services.booking_service import BookingService
                        from ..models.booking import BookingStatus
                    except ImportError:
                        # Fallback to absolute import (when running from project root)
                        from backend.database import get_db
                        from backend.services.booking_service import BookingService
                        from backend.models.booking import BookingStatus
                
                db = next(get_db())
                booking_service = BookingService(db, self)
                
                # Update or create booking in database
                db_booking = booking_service.get_booking_by_calendly_event_uri(event_uri)
                if not db_booking:
                    # Create new booking
                    db_booking = booking_service.create_booking(
                        appointment_type=self.appointment_types[normalized_type]["name"],
                        date=start_dt.strftime("%Y-%m-%d"),
                        start_time=start_dt.strftime("%H:%M"),
                        patient_name=patient_name,
                        patient_email=patient_email,
                        patient_phone=patient_phone,
                        reason=reason,
                        scheduling_url="",  # Not needed for direct booking
                        event_type_uuid=event_type_uuid,
                        duration_minutes=self.appointment_types[normalized_type]["duration"],
                        extra_data=json.dumps({"created_via": "calendly_direct_api"})
                    )
                
                # Update with Calendly URIs and confirm
                booking_service.update_booking_from_webhook(
                    event_uri=event_uri,
                    invitee_uri=invitee_uri,
                    start_time=start_dt.strftime("%H:%M"),
                    end_time=end_dt.strftime("%H:%M"),
                    patient_name=patient_name,
                    patient_email=patient_email,
                    patient_phone=patient_phone
                )
                
                booking["db_booking_id"] = db_booking.id
                print(f"✅ Booking saved to database with ID: {db_booking.id}")
                db.close()
            except Exception as e:
                print(f"⚠️  Could not save booking to database: {e}")
            
            print(f"✅ Direct booking created successfully!")
            print(f"   Booking ID: {booking_id}")
            print(f"   Event URI: {event_uri}")
            print(f"   Invitee URI: {invitee_uri}")
            
            return booking
    
    async def _real_create_booking_via_link(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Create booking via scheduling link (fallback method)
        
        This is the original method that generates a pre-filled scheduling link.
        """
        
        if not self.api_key:
            raise Exception("Calendly API key is required but not configured. Please set CALENDLY_API_KEY environment variable.")
        
        # Normalize appointment type to ensure we have a valid key
        normalized_type = self._normalize_appointment_type(appointment_type)
        event_type_uuid = self.appointment_types[normalized_type]["uuid"]
        
        # Calendly API doesn't support direct booking creation
        # We need to use scheduling links instead
        # First, try to get the event type details to build a scheduling link
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Get event type details to build scheduling link
            async with httpx.AsyncClient() as client:
                # First, get user info to get the username/URI
                user_response = await client.get(
                    f"{self.base_url}/users/me",
                    headers=headers
                )
                user_response.raise_for_status()
                user_data = user_response.json()
                user_resource = user_data.get("resource", {})
                
                # Get event type details
                event_type_response = await client.get(
                    f"{self.base_url}/event_types/{event_type_uuid}",
                    headers=headers
                )
                event_type_response.raise_for_status()
                event_type_data = event_type_response.json()
                
                # Get the scheduling URL from event type
                event_type_resource = event_type_data.get("resource", {})
                scheduling_url = event_type_resource.get("scheduling_url", "")
                event_slug = event_type_resource.get("slug", "")
                
                # Extract username for pre-filled URL
                # Priority: 1) CALENDLY_USER_URL from .env, 2) scheduling_url from API, 3) user slug from API
                username = None
                
                # Method 1: Extract from CALENDLY_USER_URL (highest priority)
                if self.user_url:
                    # Handle formats: https://calendly.com/username, calendly.com/username, or just username
                    user_url_clean = self.user_url.strip().strip("/")
                    
                    # Debug: log the original user_url
                    print(f"🔍 CALENDLY_USER_URL from .env: {self.user_url}")
                    
                    if "calendly.com/" in user_url_clean.lower():
                        # Extract username from URL
                        if user_url_clean.startswith("http://"):
                            user_url_clean = user_url_clean.replace("http://", "")
                        if user_url_clean.startswith("https://"):
                            user_url_clean = user_url_clean.replace("https://", "")
                        if user_url_clean.startswith("calendly.com/"):
                            user_url_clean = user_url_clean.replace("calendly.com/", "")
                        # Get first part (username) before any slash
                        username = user_url_clean.split("/")[0].strip()
                    else:
                        # Assume it's just the username
                        username = user_url_clean
                    
                    # Validate username is not a placeholder
                    if username and username.lower() not in ["your-username", "username", ""]:
                        print(f"✅ Using username from CALENDLY_USER_URL: {username}")
                    else:
                        print(f"⚠️  CALENDLY_USER_URL appears to be a placeholder: {self.user_url}")
                        username = None  # Reset to try other methods
                
                # Method 2: Extract from scheduling_url if username not found
                if not username and scheduling_url:
                    # Extract from scheduling URL: https://calendly.com/username/event-slug
                    try:
                        url_parts = scheduling_url.replace("https://calendly.com/", "").replace("http://calendly.com/", "").split("/")
                        if url_parts and url_parts[0]:
                            username = url_parts[0].strip()
                            print(f"📝 Using username from scheduling_url: {username}")
                    except Exception as e:
                        print(f"⚠️  Could not extract username from scheduling_url: {e}")
                
                # Method 3: Try to get from user resource slug
                if not username and user_resource:
                    user_slug = user_resource.get("slug", "")
                    if user_slug:
                        username = user_slug
                        print(f"📝 Using username from user resource slug: {username}")
                
                # Validate username (should not be placeholder)
                # Only reject obvious placeholders, not valid usernames like "meeting-scheduler2025"
                placeholder_usernames = ["your-username", "username", "example", "test"]
                if not username or username.lower() in placeholder_usernames:
                    # If it's a placeholder, try to get from user resource
                    if user_resource:
                        # Check if there's a slug in the user resource
                        user_slug = user_resource.get("slug", "")
                        if user_slug and user_slug.lower() not in placeholder_usernames:
                            username = user_slug
                            print(f"📝 Using username from user resource slug: {username}")
                        else:
                            # Try to extract from scheduling_url as last resort
                            if scheduling_url:
                                try:
                                    url_parts = scheduling_url.replace("https://calendly.com/", "").replace("http://calendly.com/", "").split("/")
                                    if url_parts and url_parts[0] and url_parts[0].lower() not in placeholder_usernames:
                                        username = url_parts[0].strip()
                                        print(f"📝 Using username from scheduling_url (fallback): {username}")
                                except:
                                    pass
                
                # Build base scheduling link
                if not username:
                    # Last resort: use scheduling_url directly if available
                    if scheduling_url:
                        base_link = scheduling_url
                        print(f"⚠️  Username not found, using full scheduling_url from API")
                    else:
                        base_link = f"https://calendly.com/event_types/{event_type_uuid}"
                        print(f"⚠️  Could not determine Calendly username. Using generic link with event type UUID.")
                elif event_slug:
                    # Use username + event slug (preferred format)
                    base_link = f"https://calendly.com/{username}/{event_slug}"
                    print(f"✅ Built scheduling link: {base_link}")
                else:
                    # Fallback to username + UUID
                    base_link = f"https://calendly.com/{username}/{event_type_uuid}"
                    print(f"⚠️  Event slug not found, using UUID: {base_link}")
                
                # Generate pre-filled scheduling URL with invitee information
                # Calendly supports pre-filling: name, email, and custom questions via URL params
                # Note: The 'name' parameter should be the patient's name, not appointment type
                prefill_params = {
                    "name": patient_name,  # Patient's actual name
                    "email": patient_email,
                }
                
                # Add phone if event type supports it (some event types have phone as a question)
                if patient_phone:
                    prefill_params["a1"] = patient_phone  # Custom field format
                
                # Add reason as a custom question if supported
                if reason:
                    prefill_params["a2"] = reason
                
                # Build pre-filled URL
                prefill_query = urlencode(prefill_params)
                prefilled_link = f"{base_link}?{prefill_query}"
                
                # Generate a temporary booking ID for tracking (before webhook confirmation)
                temp_booking_id = f"TEMP-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.digits, k=6))}"
                confirmation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                # Store pending booking data (will be updated when webhook is received)
                pending_booking = {
                    "temp_booking_id": temp_booking_id,
                    "confirmation_code": confirmation_code,
                    "status": "pending",
                    "appointment_type": self.appointment_types[normalized_type]["name"],
                    "event_type_uuid": event_type_uuid,
                    "date": date,
                    "start_time": start_time,
                    "patient_name": patient_name,
                    "patient_email": patient_email,
                    "patient_phone": patient_phone,
                    "reason": reason,
                    "scheduling_link": prefilled_link,
                    "created_at": datetime.now().isoformat(),
                    "calendly_event_uri": None,  # Will be set by webhook
                    "calendly_invitee_uri": None  # Will be set by webhook
                }
                
                # Store in memory (for quick lookup)
                self.pending_bookings[temp_booking_id] = pending_booking
                
                # Also save to database if available
                try:
                    # Try direct import first (when running from backend/ directory)
                    try:
                        from database import get_db
                        from services.booking_service import BookingService
                        from models.booking import BookingStatus
                    except ImportError:
                        # Fallback to relative import (when running as package)
                        try:
                            from ..database import get_db
                            from ..services.booking_service import BookingService
                            from ..models.booking import BookingStatus
                        except ImportError:
                            # Fallback to absolute import (when running from project root)
                            from backend.database import get_db
                            from backend.services.booking_service import BookingService
                            from backend.models.booking import BookingStatus
                    
                    db = next(get_db())
                    booking_service = BookingService(db, self)
                    
                    # Create booking in database
                    import json
                    extra_data = {
                        "temp_booking_id": temp_booking_id,
                        "created_via": "calendly_scheduling_link"
                    }
                    
                    db_booking = booking_service.create_booking(
                        appointment_type=self.appointment_types[normalized_type]["name"],
                        date=date,
                        start_time=start_time,
                        patient_name=patient_name,
                        patient_email=patient_email,
                        patient_phone=patient_phone,
                        reason=reason,
                        scheduling_url=prefilled_link,
                        event_type_uuid=event_type_uuid,
                        duration_minutes=self.appointment_types[normalized_type]["duration"],
                        extra_data=json.dumps(extra_data)
                    )
                    
                    # Store mapping from temp_booking_id to database ID
                    pending_booking["db_booking_id"] = db_booking.id
                    pending_booking["db_confirmation_code"] = db_booking.confirmation_code
                    
                    print(f"✅ Booking saved to database with ID: {db_booking.id} (TEMP ID: {temp_booking_id})")
                    db.close()
                except Exception as e:
                    print(f"⚠️  Could not save booking to database: {e}")
                    # Continue with in-memory storage
                
                print(f"📅 Pre-filled Calendly booking link generated: {prefilled_link}")
                print(f"   Temporary booking ID: {temp_booking_id}")
                print(f"   Waiting for webhook confirmation...")
                
                # Return booking details with pre-filled scheduling link
                return {
                    "booking_id": temp_booking_id,
                    "confirmation_code": confirmation_code,
                    "status": "pending",  # Pending until webhook confirms booking
                    "appointment_type": self.appointment_types[normalized_type]["name"],
                    "date": date,
                    "start_time": start_time,
                    "patient_name": patient_name,
                    "patient_email": patient_email,
                    "scheduling_link": prefilled_link,
                    "message": "Please complete your booking by clicking the scheduling link. Your information is pre-filled. The appointment will be confirmed once you complete the booking in Calendly.",
                    "clinic_info": {
                        "name": "HealthCare Plus Clinic",
                        "address": "123 Health Street, Medical District, NY 10001",
                        "phone": "+1-555-123-4567"
                    }
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                error_msg = f"Calendly event type not found (UUID: {event_type_uuid}). Please verify the event type UUID is correct."
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
            else:
                error_msg = f"Calendly API error: HTTP {e.response.status_code} - {e.response.text}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error creating Calendly booking: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    async def _real_cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """Real Calendly API cancellation"""
        
        if not self.api_key:
            raise Exception("Calendly API key is required but not configured. Please set CALENDLY_API_KEY environment variable.")
        
        # First, try to find the booking in our stored bookings
        booking = self.get_booking_by_id(booking_id)
        
        if not booking:
            raise Exception(f"Booking not found: {booking_id}")
        
        # Get the Calendly invitee URI or event URI
        invitee_uri = booking.get("calendly_invitee_uri")
        event_uri = booking.get("calendly_event_uri")
        cancel_url = booking.get("cancel_url")
        
        if not event_uri and not invitee_uri:
            # If it's a pending booking, just mark it as canceled
            if booking_id in self.pending_bookings:
                self.pending_bookings[booking_id]["status"] = "canceled"
                self.pending_bookings[booking_id]["canceled_at"] = datetime.now().isoformat()
                return {
                    "booking_id": booking_id,
                    "status": "cancelled",
                    "message": "Pending booking cancelled (booking was not yet confirmed in Calendly)"
                }
            else:
                raise Exception(f"Cannot cancel: Booking {booking_id} does not have a Calendly event or invitee URI")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Prefer using cancel_url if available (simpler and more direct)
        if cancel_url:
            # Extract token from cancel URL (format: calendly.com/cancellations/[TOKEN])
            # Or use the full URL if it's an API endpoint
            if "api.calendly.com" in cancel_url:
                url = cancel_url
            else:
                # Extract token and use API endpoint
                if "/cancellations/" in cancel_url:
                    token = cancel_url.split("/cancellations/")[-1].split("?")[0]
                    url = f"{self.base_url}/invitees/{token}/cancellation"
                else:
                    # Fallback to event cancellation
                    event_uuid = event_uri.split("/")[-1] if "/" in event_uri else booking_id
                    url = f"{self.base_url}/scheduled_events/{event_uuid}/cancellation"
        elif invitee_uri:
            # Use invitee URI for cancellation (preferred method)
            invitee_uuid = invitee_uri.split("/")[-1] if "/" in invitee_uri else ""
            url = f"{self.base_url}/invitees/{invitee_uuid}/cancellation"
        else:
            # Fallback to event cancellation
            event_uuid = event_uri.split("/")[-1] if "/" in event_uri else booking_id
            url = f"{self.base_url}/scheduled_events/{event_uuid}/cancellation"
        payload = {
            "reason": "Cancelled by patient"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                # Update local booking status
                if event_uri in self.real_bookings:
                    self.real_bookings[event_uri]["status"] = "canceled"
                    self.real_bookings[event_uri]["canceled_at"] = datetime.now().isoformat()
                
                print(f"✅ Booking canceled via Calendly API: {event_uuid}")
                
                return {
                    "booking_id": booking_id,
                    "calendly_event_uri": event_uri,
                    "status": "cancelled",
                    "message": "Appointment cancelled successfully"
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                error_msg = f"Calendly event not found: {event_uuid}. It may have already been canceled."
                print(f"⚠️  {error_msg}")
                # Update local status anyway
                if event_uri in self.real_bookings:
                    self.real_bookings[event_uri]["status"] = "canceled"
                    self.real_bookings[event_uri]["canceled_at"] = datetime.now().isoformat()
                raise Exception(error_msg)
            else:
                error_msg = f"Calendly cancellation error: HTTP {e.response.status_code} - {e.response.text}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
        except Exception as e:
            print(f"❌ Calendly cancellation error: {str(e)}")
            raise
    
    # Webhook Handling Methods
    
    async def process_webhook_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a Calendly webhook event
        
        Supported events:
        - invitee.created: When a booking is created
        - invitee.canceled: When a booking is canceled
        
        Args:
            event_data: Webhook payload from Calendly
        
        Returns:
            Processing result
        """
        event_type = event_data.get("event", "")
        event_time = event_data.get("time", datetime.now().isoformat())
        payload = event_data.get("payload", {})
        
        # Log webhook event
        log_entry = {
            "event_type": event_type,
            "timestamp": event_time,
            "received_at": datetime.now().isoformat(),
            "payload": payload,
            "full_event_data": event_data,
            "processed": False,
            "result": None,
            "error": None
        }
        
        try:
            if event_type == "invitee.created":
                result = await self._handle_invitee_created(payload)
            elif event_type == "invitee.canceled":
                result = self._handle_invitee_canceled(payload)
            else:
                print(f"⚠️  Unhandled webhook event type: {event_type}")
                result = {
                    "processed": False,
                    "event_type": event_type,
                    "message": f"Event type '{event_type}' is not handled"
                }
            
            # Update log entry with result
            log_entry["processed"] = result.get("processed", False)
            log_entry["result"] = result
            
        except Exception as e:
            print(f"❌ Error processing webhook event: {str(e)}")
            log_entry["error"] = str(e)
            result = {
                "processed": False,
                "error": str(e)
            }
        
        # Store log entry
        self.webhook_logs.append(log_entry)
        
        # Keep only last N logs
        if len(self.webhook_logs) > self.max_webhook_logs:
            self.webhook_logs = self.webhook_logs[-self.max_webhook_logs:]
        
        return result
    
    async def _handle_invitee_created(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle invitee.created webhook event - booking confirmed"""
        try:
            # Extract event and invitee information
            event_uri = payload.get("event", "")
            invitee_uri = payload.get("invitee", "")
            
            if not event_uri or not invitee_uri:
                print(f"⚠️  Missing event or invitee URI in webhook payload")
                return {"processed": False, "error": "Missing required fields"}
            
            # Check if this is a test URI (for testing purposes)
            is_test_uri = "TEST" in event_uri.upper() or "TEST" in invitee_uri.upper()
            
            if is_test_uri:
                print(f"📝 Test webhook received (test URIs detected)")
                return {
                    "processed": True,
                    "test_mode": True,
                    "message": "Test webhook received successfully. Webhook endpoint is working correctly! For real bookings, Calendly will send real URIs.",
                    "event_uri": event_uri,
                    "invitee_uri": invitee_uri
                }
            
            # Fetch full event and invitee details from Calendly API
            if not self.api_key:
                print(f"⚠️  Cannot fetch booking details: API key not configured")
                return {"processed": False, "error": "API key not configured"}
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            try:
                async with httpx.AsyncClient() as client:
                    # Fetch event details
                    event_response = await client.get(event_uri, headers=headers)
                    event_response.raise_for_status()
                    event_data = event_response.json()
                    event_resource = event_data.get("resource", {})
                    
                    # Fetch invitee details
                    invitee_response = await client.get(invitee_uri, headers=headers)
                    invitee_response.raise_for_status()
                    invitee_data = invitee_response.json()
                    invitee_resource = invitee_data.get("resource", {})
                    
                    # Extract booking information
                    start_time = event_resource.get("start_time", "")
                    end_time = event_resource.get("end_time", "")
                    event_type_uri = event_resource.get("event_type", "")
                    event_type_uuid = event_type_uri.split("/")[-1] if event_type_uri else ""
                    
                    # Parse dates
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00")) if start_time else None
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00")) if end_time else None
                    
                    booking_data = {
                        "calendly_event_uri": event_uri,
                        "calendly_invitee_uri": invitee_uri,
                        "event_type_uuid": event_type_uuid,
                        "start_time": start_time,
                        "end_time": end_time,
                        "date": start_dt.strftime("%Y-%m-%d") if start_dt else "",
                        "start_time_formatted": start_dt.strftime("%H:%M") if start_dt else "",
                        "patient_name": invitee_resource.get("name", ""),
                        "patient_email": invitee_resource.get("email", ""),
                        "patient_phone": invitee_resource.get("phone_number", ""),
                        "status": "confirmed",
                        "confirmed_at": datetime.now().isoformat(),
                        "questions_and_answers": invitee_resource.get("questions_and_answers", [])
                    }
                    
                    # Try to match with pending booking by email or confirmation code
                    # This helps match webhook events to pending bookings
                    matched_pending = None
                    matched_temp_id = None
                    
                    # First, try to match by email in pending bookings (in-memory)
                    for temp_id, pending in list(self.pending_bookings.items()):
                        # Match by email (case-insensitive)
                        pending_email = pending.get("patient_email", "").lower().strip()
                        webhook_email = booking_data.get("patient_email", "").lower().strip()
                        
                        if pending_email and webhook_email and pending_email == webhook_email:
                            matched_pending = pending
                            matched_temp_id = temp_id
                            print(f"✅ Matched webhook to pending booking {temp_id} by email: {webhook_email}")
                            break
                    
                    # If not found in memory, try database
                    if not matched_pending:
                        try:
                            # Try direct import first (when running from backend/ directory)
                            try:
                                from database import get_db
                                from services.booking_service import BookingService
                                from models.booking import BookingStatus
                            except ImportError:
                                # Fallback to relative import (when running as package)
                                try:
                                    from ..database import get_db
                                    from ..services.booking_service import BookingService
                                    from ..models.booking import BookingStatus
                                except ImportError:
                                    # Fallback to absolute import (when running from project root)
                                    from backend.database import get_db
                                    from backend.services.booking_service import BookingService
                                    from backend.models.booking import BookingStatus
                            
                            db = next(get_db())
                            booking_service = BookingService(db, self)
                            
                            # Find pending booking by email
                            pending_db_bookings = booking_service.get_booking_by_email(
                                booking_data.get("patient_email", ""),
                                status=BookingStatus.PENDING
                            )
                            
                            if pending_db_bookings:
                                # Use most recent pending booking
                                db_booking = pending_db_bookings[0]
                                
                                # Create matched_pending structure from database booking
                                matched_pending = {
                                    "db_booking_id": db_booking.id,
                                    "confirmation_code": db_booking.confirmation_code,
                                    "appointment_type": db_booking.appointment_type,
                                    "event_type_uuid": db_booking.event_type_uuid,
                                    "date": db_booking.date,
                                    "start_time": db_booking.start_time,
                                    "patient_name": db_booking.patient_name,
                                    "patient_email": db_booking.patient_email,
                                    "patient_phone": db_booking.patient_phone,
                                    "reason": db_booking.reason,
                                    "scheduling_link": db_booking.scheduling_url,
                                    "created_at": db_booking.created_at.isoformat() if db_booking.created_at else None
                                }
                                
                                # Try to find temp_id from pending_bookings by email
                                for temp_id, pending in self.pending_bookings.items():
                                    if pending.get("patient_email", "").lower() == booking_data.get("patient_email", "").lower():
                                        matched_temp_id = temp_id
                                        break
                                
                                # If no temp_id found, use database ID
                                if not matched_temp_id:
                                    matched_temp_id = db_booking.id
                                
                                print(f"✅ Matched webhook to database booking {db_booking.id} by email: {booking_data.get('patient_email')}")
                            
                            db.close()
                        except Exception as e:
                            print(f"⚠️  Error matching webhook in database: {e}")
                    
                    if matched_pending and matched_temp_id:
                        # Update with Calendly data
                        booking_data.update({
                            "booking_id": matched_temp_id,  # Keep temp booking ID
                            "temp_booking_id": matched_temp_id,
                            "confirmation_code": matched_pending.get("confirmation_code", ""),
                            "appointment_type": matched_pending.get("appointment_type", ""),
                            "reason": matched_pending.get("reason", ""),
                            "scheduling_link": matched_pending.get("scheduling_link", "")
                        })
                        
                        # Update database if booking was saved there
                        db_booking_id = matched_pending.get("db_booking_id")
                        if db_booking_id:
                            try:
                                # Try direct import first (when running from backend/ directory)
                                try:
                                    from database import get_db
                                    from services.booking_service import BookingService
                                except ImportError:
                                    # Fallback to relative import (when running as package)
                                    try:
                                        from ..database import get_db
                                        from ..services.booking_service import BookingService
                                    except ImportError:
                                        # Fallback to absolute import (when running from project root)
                                        from backend.database import get_db
                                        from backend.services.booking_service import BookingService
                                
                                db = next(get_db())
                                booking_service = BookingService(db, self)
                                
                                # Update booking in database
                                updated_booking = booking_service.update_booking_from_webhook(
                                    event_uri=event_uri,
                                    invitee_uri=invitee_uri,
                                    start_time=start_time,
                                    end_time=end_time,
                                    patient_name=booking_data.get("patient_name", ""),
                                    patient_email=booking_data.get("patient_email", ""),
                                    patient_phone=booking_data.get("patient_phone", "")
                                )
                                
                                if updated_booking:
                                    # Update booking_data with database ID
                                    booking_data["db_booking_id"] = updated_booking.id
                                    booking_data["booking_id"] = matched_temp_id  # Keep temp ID for frontend compatibility
                                    booking_data["temp_booking_id"] = matched_temp_id  # Keep temp ID for reference
                                    booking_data["confirmation_code"] = updated_booking.confirmation_code
                                    booking_data["appointment_type"] = updated_booking.appointment_type
                                    booking_data["date"] = updated_booking.date
                                    booking_data["time"] = updated_booking.start_time
                                    booking_data["status"] = "confirmed"  # Ensure status is set
                                    print(f"✅ Database booking {updated_booking.id} confirmed via webhook (TEMP ID: {matched_temp_id})")
                                    print(f"   Status updated to: confirmed")
                                    print(f"   Event URI: {event_uri}")
                                    print(f"   Invitee URI: {invitee_uri}")
                                
                                db.close()
                            except Exception as e:
                                print(f"⚠️  Could not update database booking: {e}")
                        
                        # Remove from pending (keep in database)
                        del self.pending_bookings[matched_temp_id]
                        print(f"✅ Moved booking {matched_temp_id} from pending to confirmed")
                    else:
                        print(f"⚠️  Webhook received but no pending booking found for email: {booking_data.get('patient_email')}")
                        print(f"   Pending bookings: {list(self.pending_bookings.keys())}")
                        
                        # Try to find in database by email (might be confirmed already)
                        try:
                            # Try direct import first (when running from backend/ directory)
                            try:
                                from database import get_db
                                from services.booking_service import BookingService
                            except ImportError:
                                # Fallback to relative import (when running as package)
                                try:
                                    from ..database import get_db
                                    from ..services.booking_service import BookingService
                                except ImportError:
                                    # Fallback to absolute import (when running from project root)
                                    from backend.database import get_db
                                    from backend.services.booking_service import BookingService
                            
                            db = next(get_db())
                            booking_service = BookingService(db, self)
                            
                            # Try to update existing booking or create new one
                            updated_booking = booking_service.update_booking_from_webhook(
                                event_uri=event_uri,
                                invitee_uri=invitee_uri,
                                start_time=start_time,
                                end_time=end_time,
                                patient_name=booking_data.get("patient_name", ""),
                                patient_email=booking_data.get("patient_email", ""),
                                patient_phone=booking_data.get("patient_phone", "")
                            )
                            
                            if updated_booking:
                                booking_data["db_booking_id"] = updated_booking.id
                                booking_data["booking_id"] = updated_booking.id
                                booking_data["confirmation_code"] = updated_booking.confirmation_code
                                booking_data["appointment_type"] = updated_booking.appointment_type
                                print(f"✅ Found and updated database booking {updated_booking.id} via webhook")
                            else:
                                # No booking found, create a new one from webhook
                                booking_data["booking_id"] = f"WEBHOOK-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                                print(f"⚠️  No matching booking found, created webhook-only record")
                            
                            db.close()
                        except Exception as e:
                            print(f"⚠️  Error checking database for webhook: {e}")
                            # Still store the booking even if not matched
                            booking_data["booking_id"] = f"WEBHOOK-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    
                    # Store in real bookings (use event URI as key)
                    self.real_bookings[event_uri] = booking_data
                    
                    # Ensure database is updated (if not already done above)
                    if not booking_data.get("db_booking_id"):
                        try:
                            # Try direct import first (when running from backend/ directory)
                            try:
                                from database import get_db
                                from services.booking_service import BookingService
                            except ImportError:
                                # Fallback to relative import (when running as package)
                                try:
                                    from ..database import get_db
                                    from ..services.booking_service import BookingService
                                except ImportError:
                                    # Fallback to absolute import (when running from project root)
                                    from backend.database import get_db
                                    from backend.services.booking_service import BookingService
                            
                            db = next(get_db())
                            booking_service = BookingService(db, self)
                            
                            # Try to update or find booking in database
                            updated_booking = booking_service.update_booking_from_webhook(
                                event_uri=event_uri,
                                invitee_uri=invitee_uri,
                                start_time=start_time,
                                end_time=end_time,
                                patient_name=booking_data.get("patient_name", ""),
                                patient_email=booking_data.get("patient_email", ""),
                                patient_phone=booking_data.get("patient_phone", "")
                            )
                            
                            if updated_booking:
                                booking_data["db_booking_id"] = updated_booking.id
                                if not booking_data.get("booking_id") or booking_data.get("booking_id", "").startswith("WEBHOOK-"):
                                    booking_data["booking_id"] = updated_booking.id
                                booking_data["confirmation_code"] = updated_booking.confirmation_code
                                print(f"✅ Database booking {updated_booking.id} confirmed via webhook")
                            
                            db.close()
                        except Exception as e:
                            print(f"⚠️  Could not update database from webhook: {e}")
                    
                    print(f"✅ Booking confirmed via webhook:")
                    print(f"   Event URI: {event_uri}")
                    print(f"   Patient: {booking_data['patient_name']} ({booking_data['patient_email']})")
                    print(f"   Date: {booking_data.get('date')} at {booking_data.get('start_time_formatted')}")
                    if booking_data.get("db_booking_id"):
                        print(f"   Database ID: {booking_data['db_booking_id']}")
                    if booking_data.get("temp_booking_id"):
                        print(f"   Temp ID: {booking_data['temp_booking_id']}")
                    
                    return {"processed": True, "booking": booking_data}
                
            except Exception as e:
                print(f"❌ Error fetching booking details from Calendly: {str(e)}")
                return {"processed": False, "error": str(e)}
                
        except Exception as e:
            print(f"❌ Error processing invitee.created webhook: {str(e)}")
            return {"processed": False, "error": str(e)}
    
    def _handle_invitee_canceled(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle invitee.canceled webhook event - booking canceled"""
        try:
            event_uri = payload.get("event", "")
            invitee_uri = payload.get("invitee", "")
            
            if not event_uri:
                return {"processed": False, "error": "Missing event URI"}
            
            # Update booking status to canceled
            booking_id = None
            patient_info = {}
            
            # Check in-memory bookings first
            if event_uri in self.real_bookings:
                self.real_bookings[event_uri]["status"] = "canceled"
                self.real_bookings[event_uri]["canceled_at"] = datetime.now().isoformat()
                
                booking = self.real_bookings[event_uri]
                booking_id = booking.get("temp_booking_id") or booking.get("booking_id") or booking.get("db_booking_id")
                patient_info = {
                    "patient_name": booking.get("patient_name"),
                    "patient_email": booking.get("patient_email")
                }
            
            # Also update database
            try:
                # Try direct import first (when running from backend/ directory)
                try:
                    from database import get_db
                    from services.booking_service import BookingService
                except ImportError:
                    # Fallback to relative import (when running as package)
                    try:
                        from ..database import get_db
                        from ..services.booking_service import BookingService
                    except ImportError:
                        # Fallback to absolute import (when running from project root)
                        from backend.database import get_db
                        from backend.services.booking_service import BookingService
                
                db = next(get_db())
                booking_service = BookingService(db, self)
                
                # Find booking by event URI
                db_booking = booking_service.get_booking_by_calendly_event_uri(event_uri)
                
                if db_booking:
                    # Cancel in database
                    canceled_booking = booking_service.cancel_booking(db_booking.id, reason="Canceled via Calendly")
                    if canceled_booking:
                        booking_id = canceled_booking.id
                        patient_info = {
                            "patient_name": canceled_booking.patient_name,
                            "patient_email": canceled_booking.patient_email
                        }
                        print(f"✅ Database booking {canceled_booking.id} canceled via webhook")
                
                db.close()
            except Exception as e:
                print(f"⚠️  Could not update database for cancellation: {e}")
            
            if booking_id or event_uri in self.real_bookings:
                print(f"✅ Booking canceled via webhook:")
                print(f"   Event URI: {event_uri}")
                if patient_info.get("patient_name"):
                    print(f"   Patient: {patient_info.get('patient_name')} ({patient_info.get('patient_email')})")
                
                return {
                    "processed": True,
                    "booking_id": booking_id or event_uri,
                    "status": "canceled"
                }
            else:
                print(f"⚠️  Booking not found for event URI: {event_uri}")
                return {"processed": False, "error": "Booking not found"}
                
        except Exception as e:
            print(f"❌ Error processing invitee.canceled webhook: {str(e)}")
            return {"processed": False, "error": str(e)}
    
    def get_booking_by_id(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """
        Get booking by temporary booking ID or Calendly event URI
        
        Searches in this order:
        1. mock_bookings (if in mock mode)
        2. pending_bookings dictionary (by booking_id key)
        3. real_bookings by temp_booking_id field
        4. real_bookings by booking_id field
        5. real_bookings by event URI (if booking_id is an event URI)
        """
        # Debug logging
        print(f"🔍 Looking up booking: {booking_id}")
        print(f"   Using mock: {self.use_mock}")
        print(f"   Mock bookings: {len(self.mock_bookings)}")
        print(f"   Pending bookings: {len(self.pending_bookings)}")
        print(f"   Real bookings: {len(self.real_bookings)}")
        
        # Check mock bookings first (if in mock mode)
        if self.use_mock:
            for key, booking in self.mock_bookings.items():
                if booking.get("booking_id") == booking_id:
                    print(f"   ✅ Found in mock_bookings")
                    return booking
        
        # Check database FIRST for TEMP bookings or regular bookings (before checking in-memory)
        # This ensures persistence across server restarts and gets the most up-to-date status
        if booking_id.startswith("TEMP-") or len(booking_id) == 36:  # UUID format
            try:
                # Try direct import first (when running from backend/ directory)
                try:
                    from database import get_db
                    from services.booking_service import BookingService
                    from models.booking import BookingStatus
                except ImportError:
                    # Fallback to relative import (when running as package)
                    try:
                        from ..database import get_db
                        from ..services.booking_service import BookingService
                        from ..models.booking import BookingStatus
                    except ImportError:
                        # Fallback to absolute import (when running from project root)
                        from backend.database import get_db
                        from backend.services.booking_service import BookingService
                        from backend.models.booking import BookingStatus
                
                db = next(get_db())
                booking_service = BookingService(db, self)
                
                # Try to find by ID (UUID) first
                db_booking = booking_service.get_booking_by_id(booking_id)
                
                # If not found and it's a TEMP ID, try multiple lookup strategies
                if not db_booking and booking_id.startswith("TEMP-"):
                    # Strategy 1: Search by TEMP ID in extra_data
                    db_booking = booking_service.get_booking_by_temp_id(booking_id)
                    
                    # Strategy 2: Extract confirmation code from pending booking if available
                    if not db_booking and booking_id in self.pending_bookings:
                        pending = self.pending_bookings[booking_id]
                        conf_code = pending.get("db_confirmation_code") or pending.get("confirmation_code")
                        if conf_code:
                            db_booking = booking_service.get_booking_by_confirmation_code(conf_code)
                    
                    # Strategy 3: Find by email and date/time match
                    if not db_booking and booking_id in self.pending_bookings:
                        pending = self.pending_bookings[booking_id]
                        email = pending.get("patient_email")
                        if email:
                            # Get pending bookings by email
                            pending_db_bookings = booking_service.get_booking_by_email(email, status=BookingStatus.PENDING)
                            if pending_db_bookings:
                                # Find the one that matches our temp booking by date/time
                                for pdb in pending_db_bookings:
                                    # Check if it matches by date/time
                                    if (pdb.date == pending.get("date") and 
                                        pdb.start_time == pending.get("start_time")):
                                        db_booking = pdb
                                        break
                
                if db_booking:
                    booking_dict = db_booking.to_dict()
                    # Add temp_booking_id if it was a TEMP booking
                    if booking_id.startswith("TEMP-"):
                        booking_dict["temp_booking_id"] = booking_id
                        booking_dict["booking_id"] = booking_id  # Keep original ID for compatibility
                    
                    # Ensure status is properly set
                    booking_dict["status"] = db_booking.status
                    
                    # Add time field for frontend compatibility
                    if db_booking.start_time:
                        booking_dict["time"] = db_booking.start_time
                    
                    print(f"   ✅ Found in database (ID: {db_booking.id}, Status: {db_booking.status})")
                    if booking_id.startswith("TEMP-"):
                        print(f"   📝 Returning with TEMP ID: {booking_id} for frontend compatibility")
                    db.close()
                    return booking_dict
                
                db.close()
            except Exception as e:
                print(f"   ⚠️  Database lookup error: {e}")
                import traceback
                traceback.print_exc()
        
        # Check pending bookings (for real Calendly API - bookings waiting for webhook)
        # This is checked AFTER database to ensure we get the most up-to-date status from DB first
        if booking_id in self.pending_bookings:
            booking = self.pending_bookings[booking_id].copy()
            print(f"   ✅ Found in pending_bookings")
            # Add helpful status information
            booking["status_note"] = (
                "This booking is pending confirmation. "
                "Please complete your booking by clicking the scheduling link. "
                "Once completed in Calendly, it will be automatically confirmed via webhook."
            )
            return booking
        
        # Check real bookings by temp_booking_id field
        for event_uri, booking in self.real_bookings.items():
            temp_id = booking.get("temp_booking_id") or booking.get("booking_id")
            if temp_id == booking_id:
                print(f"   ✅ Found in real_bookings by temp_booking_id: {event_uri}")
                return booking
        
        # Check real bookings by booking_id field
        for event_uri, booking in self.real_bookings.items():
            if booking.get("booking_id") == booking_id:
                print(f"   ✅ Found in real_bookings by booking_id: {event_uri}")
                return booking
        
        # Check by event URI (if booking_id is a Calendly event URI)
        if booking_id in self.real_bookings:
            print(f"   ✅ Found in real_bookings by event URI")
            return self.real_bookings[booking_id]
        
        # Log what we searched for debugging
        print(f"   ❌ Booking not found")
        if self.mock_bookings:
            sample_mock_ids = [b.get("booking_id") for b in list(self.mock_bookings.values())[:3]]
            print(f"   Sample mock booking IDs: {sample_mock_ids}")
        if self.pending_bookings:
            print(f"   Available pending booking IDs: {list(self.pending_bookings.keys())[:5]}")
        if self.real_bookings:
            sample_temp_ids = [
                booking.get("temp_booking_id") or booking.get("booking_id", "N/A")
                for booking in list(self.real_bookings.values())[:5]
            ]
            print(f"   Sample real booking temp IDs: {sample_temp_ids}")
        
        return None
    
    async def get_booking_by_invitee_id(self, invitee_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch booking details from Calendly API using invitee ID
        This is useful when webhook wasn't received but booking exists in Calendly
        """
        if not self.api_key:
            print("⚠️  Cannot fetch booking: API key not configured")
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # First, get user's scheduled events
            async with httpx.AsyncClient() as client:
                # Get current user
                user_response = await client.get(
                    "https://api.calendly.com/users/me",
                    headers=headers
                )
                user_response.raise_for_status()
                user_data = user_response.json()
                user_uri = user_data["resource"]["uri"]
                
                # Get recent scheduled events (last 7 days)
                from datetime import timedelta
                start_time = (datetime.now() - timedelta(days=7)).isoformat() + "Z"
                
                events_response = await client.get(
                    "https://api.calendly.com/scheduled_events",
                    headers=headers,
                    params={
                        "user": user_uri,
                        "min_start_time": start_time,
                        "count": 50
                    }
                )
                events_response.raise_for_status()
                events_data = events_response.json()
                
                # Search for invitee in events
                for event in events_data.get("collection", []):
                    event_uri = event["uri"]
                    
                    # Get invitees for this event
                    invitees_response = await client.get(
                        f"{event_uri}/invitees",
                        headers=headers
                    )
                    
                    if invitees_response.status_code == 200:
                        invitees_data = invitees_response.json()
                        for invitee in invitees_data.get("collection", []):
                            invitee_uri = invitee["uri"]
                            # Check if invitee URI ends with our invitee ID
                            if invitee_uri.endswith(invitee_id) or invitee_id in invitee_uri:
                                # Found it! Build booking data similar to webhook handler
                                event_resource = event
                                invitee_resource = invitee
                                
                                start_time = event_resource.get("start_time", "")
                                end_time = event_resource.get("end_time", "")
                                event_type_uri = event_resource.get("event_type", "")
                                event_type_uuid = event_type_uri.split("/")[-1] if event_type_uri else ""
                                
                                # Parse dates
                                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00")) if start_time else None
                                
                                booking_data = {
                                    "booking_id": invitee_id,  # Use invitee ID as booking ID
                                    "calendly_event_uri": event_uri,
                                    "calendly_invitee_uri": invitee_uri,
                                    "event_type_uuid": event_type_uuid,
                                    "start_time": start_time,
                                    "end_time": end_time,
                                    "date": start_dt.strftime("%Y-%m-%d") if start_dt else "",
                                    "time": start_dt.strftime("%H:%M") if start_dt else "",
                                    "start_time_formatted": start_dt.strftime("%H:%M") if start_dt else "",
                                    "patient_name": invitee_resource.get("name", ""),
                                    "patient_email": invitee_resource.get("email", ""),
                                    "patient_phone": invitee_resource.get("phone_number", ""),
                                    "status": "confirmed",
                                    "confirmed_at": invitee_resource.get("created_at", datetime.now().isoformat()),
                                    "questions_and_answers": invitee_resource.get("questions_and_answers", []),
                                    "synced_from_calendly": True  # Mark as manually synced
                                }
                                
                                # Try to match with pending booking by email
                                patient_email = booking_data["patient_email"].lower().strip()
                                for temp_id, pending in list(self.pending_bookings.items()):
                                    pending_email = pending.get("patient_email", "").lower().strip()
                                    if pending_email == patient_email:
                                        booking_data.update({
                                            "temp_booking_id": temp_id,
                                            "confirmation_code": pending.get("confirmation_code", ""),
                                            "appointment_type": pending.get("appointment_type", ""),
                                            "reason": pending.get("reason", "")
                                        })
                                        # Move from pending to confirmed
                                        del self.pending_bookings[temp_id]
                                        print(f"✅ Matched and moved booking {temp_id} from pending to confirmed")
                                        break
                                
                                # Store in real bookings
                                self.real_bookings[event_uri] = booking_data
                                
                                print(f"✅ Fetched booking from Calendly API:")
                                print(f"   Invitee ID: {invitee_id}")
                                print(f"   Patient: {booking_data['patient_name']} ({booking_data['patient_email']})")
                                print(f"   Date: {booking_data.get('date')} at {booking_data.get('time')}")
                                
                                return booking_data
                
                print(f"⚠️  Invitee {invitee_id} not found in recent events")
                return None
                
        except httpx.HTTPStatusError as e:
            print(f"❌ Error fetching booking from Calendly: HTTP {e.response.status_code}")
            print(f"   Response: {e.response.text[:200]}")
            return None
        except Exception as e:
            print(f"❌ Error fetching booking by invitee ID: {str(e)}")
            return None
    
    def get_webhook_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent webhook event logs"""
        return self.webhook_logs[-limit:] if limit and limit < len(self.webhook_logs) else self.webhook_logs
    
    def get_webhook_status(self) -> Dict[str, Any]:
        """Get webhook configuration and statistics"""
        total_events = len(self.webhook_logs)
        processed_events = sum(1 for log in self.webhook_logs if log.get("processed", False))
        failed_events = total_events - processed_events
        
        event_types = {}
        for log in self.webhook_logs:
            event_type = log.get("event_type", "unknown")
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        recent_errors = [
            {
                "timestamp": log.get("received_at"),
                "event_type": log.get("event_type"),
                "error": log.get("error")
            }
            for log in self.webhook_logs[-10:]
            if log.get("error")
        ]
        
        return {
            "webhook_endpoint_configured": True,
            "webhook_endpoint_url": "/api/calendly/webhook",
            "total_events_received": total_events,
            "processed_events": processed_events,
            "failed_events": failed_events,
            "success_rate": round((processed_events / total_events * 100), 2) if total_events > 0 else 0,
            "event_types": event_types,
            "pending_bookings_count": len(self.pending_bookings),
            "confirmed_bookings_count": len(self.real_bookings),
            "last_event_received": self.webhook_logs[-1].get("received_at") if self.webhook_logs else None,
            "recent_errors": recent_errors
        }
    
    def get_webhook_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent webhook event logs"""
        return self.webhook_logs[-limit:] if limit else self.webhook_logs
    
    def get_webhook_status(self) -> Dict[str, Any]:
        """Get webhook configuration and statistics"""
        total_events = len(self.webhook_logs)
        processed_events = sum(1 for log in self.webhook_logs if log.get("processed", False))
        failed_events = total_events - processed_events
        
        event_types = {}
        for log in self.webhook_logs:
            event_type = log.get("event_type", "unknown")
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        return {
            "webhook_endpoint_configured": True,
            "webhook_endpoint_url": "/api/calendly/webhook",
            "total_events_received": total_events,
            "processed_events": processed_events,
            "failed_events": failed_events,
            "success_rate": (processed_events / total_events * 100) if total_events > 0 else 0,
            "event_types": event_types,
            "pending_bookings_count": len(self.pending_bookings),
            "confirmed_bookings_count": len(self.real_bookings),
            "last_event_received": self.webhook_logs[-1].get("received_at") if self.webhook_logs else None
        }