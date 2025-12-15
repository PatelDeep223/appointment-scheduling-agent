"""
Availability Tool
Provides functions to check and filter available appointment slots
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from api.calendly_integration import CalendlyClient
import asyncio


class AvailabilityTool:
    """
    Tool for checking appointment availability
    
    Provides a high-level interface for checking and filtering
    available appointment slots from Calendly.
    """
    
    def __init__(self, calendly_client: CalendlyClient):
        self.calendly_client = calendly_client
    
    async def get_available_slots(
        self,
        date: str,
        appointment_type: str = "consultation",
        time_preference: Optional[str] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Get available slots for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            appointment_type: Type of appointment (can be key or display name)
            time_preference: Optional time preference ("morning", "afternoon", "evening")
            max_retries: Maximum number of retry attempts on failure (default: 2)
            
        Returns:
            Dictionary with available slots:
            {
                "date": "YYYY-MM-DD",
                "appointment_type": "Appointment Type Name",
                "available_slots": [
                    {
                        "start_time": "09:00 AM",
                        "end_time": "09:30 AM",
                        "available": True,
                        "raw_time": "09:00"
                    },
                    ...
                ],
                "message": "Optional message" (if no slots found)
            }
            
        Raises:
            Exception: If unable to fetch availability after retries
        """
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD format.")
        
        # Validate date is not in the past
        today = datetime.now().date()
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        if target_date < today:
            raise ValueError(f"Date {date} is in the past. Please provide a future date.")
        
        # Retry logic for transient errors
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                availability = await self.calendly_client.get_availability(
                    date=date,
                    appointment_type=appointment_type
                )
                
                # Apply time preference filter if specified
                if time_preference:
                    availability = self._filter_by_time_preference(
                        availability,
                        time_preference
                    )
                
                return availability
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # Don't retry on certain errors (authentication, invalid date, etc.)
                non_retryable_errors = [
                    "authentication error",
                    "Invalid date format",
                    "is in the past",
                    "not found",
                    "404"
                ]
                
                if any(err in error_msg for err in non_retryable_errors):
                    raise e
                
                # Retry on transient errors
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 1  # Exponential backoff: 1s, 2s
                    print(f"⚠️  Availability check failed (attempt {attempt + 1}/{max_retries + 1}). Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    # Final attempt failed
                    print(f"❌ Availability check failed after {max_retries + 1} attempts")
                    raise Exception(f"Failed to get availability after {max_retries + 1} attempts: {str(e)}")
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise Exception("Unknown error getting availability")
    
    def _filter_by_time_preference(
        self,
        availability: Dict[str, Any],
        time_preference: str
    ) -> Dict[str, Any]:
        """
        Filter slots by time preference
        
        Args:
            availability: Availability response from Calendly
            time_preference: "morning", "afternoon", or "evening"
            
        Returns:
            Filtered availability
        """
        filtered_slots = []
        time_pref_lower = time_preference.lower()
        
        for slot in availability.get("available_slots", []):
            if not slot["available"]:
                continue
            
            # Parse time from slot
            time_str = slot.get("start_time", "")
            hour = self._extract_hour(time_str)
            
            if time_pref_lower == "morning" and hour < 12:
                filtered_slots.append(slot)
            elif time_pref_lower == "afternoon" and 12 <= hour < 17:
                filtered_slots.append(slot)
            elif time_pref_lower == "evening" and hour >= 17:
                filtered_slots.append(slot)
        
        availability["available_slots"] = filtered_slots
        return availability
    
    def _extract_hour(self, time_str: str) -> int:
        """
        Extract hour from time string (handles various formats)
        
        Args:
            time_str: Time string (e.g., "09:00 AM", "14:30", "2:00 PM")
            
        Returns:
            Hour as integer (0-23)
        """
        try:
            # Try parsing as 12-hour format with AM/PM
            if "AM" in time_str.upper() or "PM" in time_str.upper():
                time_obj = datetime.strptime(time_str.upper().strip(), "%I:%M %p")
                return time_obj.hour
            else:
                # Try 24-hour format
                time_obj = datetime.strptime(time_str.strip(), "%H:%M")
                return time_obj.hour
        except:
            # Fallback: extract first number
            import re
            match = re.search(r'(\d{1,2})', time_str)
            if match:
                hour = int(match.group(1))
                if "PM" in time_str.upper() and hour != 12:
                    hour += 12
                return hour % 24
            return 0
    
    async def get_slots_for_date_range(
        self,
        start_date: str,
        end_date: str,
        appointment_type: str = "consultation",
        max_slots: int = 5,
        time_preference: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available slots across a date range
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            appointment_type: Type of appointment (can be key or display name)
            max_slots: Maximum number of slots to return (default: 5)
            time_preference: Optional time preference ("morning", "afternoon", "evening")
            
        Returns:
            List of available slots with date information:
            [
                {
                    "start_time": "09:00 AM",
                    "end_time": "09:30 AM",
                    "available": True,
                    "raw_time": "09:00",
                    "date": "2024-01-15",
                    "day_name": "Monday",
                    "formatted_date": "Monday, January 15"
                },
                ...
            ]
        """
        # Validate date range
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD. Error: {str(e)}")
        
        if start > end:
            raise ValueError(f"Start date ({start_date}) must be before or equal to end date ({end_date})")
        
        # Limit date range to prevent excessive API calls
        max_days = 30
        days_diff = (end - start).days
        if days_diff > max_days:
            raise ValueError(f"Date range too large ({days_diff} days). Maximum allowed: {max_days} days")
        
        all_slots = []
        current_date = start
        errors = []
        
        while current_date <= end and len(all_slots) < max_slots:
            date_str = current_date.strftime("%Y-%m-%d")
            
            try:
                availability = await self.get_available_slots(
                    date=date_str,
                    appointment_type=appointment_type,
                    time_preference=time_preference
                )
                
                for slot in availability.get("available_slots", []):
                    if slot.get("available", False):
                        slot_with_date = {
                            **slot,
                            "date": date_str,
                            "day_name": current_date.strftime("%A"),
                            "formatted_date": current_date.strftime("%A, %B %d")
                        }
                        all_slots.append(slot_with_date)
                        
                        if len(all_slots) >= max_slots:
                            break
                            
            except Exception as e:
                # Log error but continue checking other dates
                error_msg = f"Error getting availability for {date_str}: {str(e)}"
                errors.append(error_msg)
                print(f"⚠️  {error_msg}")
                # Continue to next date instead of failing completely
            
            current_date += timedelta(days=1)
        
        # Log summary
        if errors:
            print(f"⚠️  Encountered {len(errors)} error(s) while checking date range, but found {len(all_slots)} slot(s)")
        
        return all_slots
    
    def format_slots_for_display(self, slots: List[Dict[str, Any]]) -> str:
        """
        Format slots as a human-readable string
        
        Args:
            slots: List of slot dictionaries
            
        Returns:
            Formatted string
        """
        if not slots:
            return "No available slots found."
        
        formatted_lines = []
        for slot in slots:
            date_str = slot.get("formatted_date", slot.get("date", ""))
            time_str = slot.get("start_time", "")
            formatted_lines.append(f"• {date_str} at {time_str}")
        
        return "\n".join(formatted_lines)
    
    async def check_slot_availability(
        self,
        date: str,
        start_time: str,
        appointment_type: str = "consultation"
    ) -> bool:
        """
        Check if a specific slot is available
        
        Args:
            date: Date in YYYY-MM-DD format
            start_time: Start time in HH:MM format (e.g., "09:00" or "14:30")
            appointment_type: Type of appointment (can be key or display name)
            
        Returns:
            True if slot is available, False otherwise
            
        Raises:
            ValueError: If date or time format is invalid
        """
        # Validate time format
        try:
            # Try parsing as HH:MM
            time_parts = start_time.split(":")
            if len(time_parts) != 2:
                raise ValueError("Invalid time format")
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("Invalid time values")
        except (ValueError, IndexError):
            raise ValueError(f"Invalid time format: {start_time}. Expected HH:MM format (e.g., '09:00', '14:30')")
        
        try:
            availability = await self.get_available_slots(
                date=date,
                appointment_type=appointment_type
            )
            
            # Normalize start_time for comparison (handle leading zeros)
            normalized_time = f"{int(time_parts[0]):02d}:{int(time_parts[1]):02d}"
            
            for slot in availability.get("available_slots", []):
                if slot.get("available", False):
                    slot_raw_time = slot.get("raw_time", "")
                    # Compare normalized times
                    if slot_raw_time == normalized_time:
                        return True
            
            return False
            
        except Exception as e:
            # If we can't check availability, assume not available
            print(f"⚠️  Error checking slot availability: {str(e)}")
            return False

