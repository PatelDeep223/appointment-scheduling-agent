"""
Availability Tool
Provides functions to check and filter available appointment slots
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from api.calendly_integration import CalendlyClient


class AvailabilityTool:
    """
    Tool for checking appointment availability
    """
    
    def __init__(self, calendly_client: CalendlyClient):
        self.calendly_client = calendly_client
    
    async def get_available_slots(
        self,
        date: str,
        appointment_type: str = "consultation",
        time_preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get available slots for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            appointment_type: Type of appointment
            time_preference: Optional time preference ("morning", "afternoon", "evening")
            
        Returns:
            Dictionary with available slots
        """
        availability = await self.calendly_client.get_availability(
            date=date,
            appointment_type=appointment_type
        )
        
        if time_preference:
            availability = self._filter_by_time_preference(
                availability,
                time_preference
            )
        
        return availability
    
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
            appointment_type: Type of appointment
            max_slots: Maximum number of slots to return
            time_preference: Optional time preference
            
        Returns:
            List of available slots with date information
        """
        all_slots = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current_date <= end and len(all_slots) < max_slots:
            date_str = current_date.strftime("%Y-%m-%d")
            
            availability = await self.get_available_slots(
                date=date_str,
                appointment_type=appointment_type,
                time_preference=time_preference
            )
            
            for slot in availability.get("available_slots", []):
                if slot["available"]:
                    slot_with_date = {
                        **slot,
                        "date": current_date.strftime("%Y-%m-%d"),
                        "day_name": current_date.strftime("%A"),
                        "formatted_date": current_date.strftime("%A, %B %d")
                    }
                    all_slots.append(slot_with_date)
                    
                    if len(all_slots) >= max_slots:
                        break
            
            current_date += timedelta(days=1)
        
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
            start_time: Start time in HH:MM format
            appointment_type: Type of appointment
            
        Returns:
            True if slot is available, False otherwise
        """
        availability = await self.get_available_slots(
            date=date,
            appointment_type=appointment_type
        )
        
        for slot in availability.get("available_slots", []):
            if slot["available"] and slot.get("raw_time") == start_time:
                return True
        
        return False

