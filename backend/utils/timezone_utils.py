"""
Timezone utility functions for converting times between timezones
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import pytz


# Default clinic timezone (from doctor_schedule.json)
DEFAULT_CLINIC_TIMEZONE = "America/New_York"


def get_timezone(timezone_str: Optional[str] = None) -> pytz.BaseTzInfo:
    """
    Get timezone object from string
    
    Args:
        timezone_str: Timezone string (e.g., 'America/New_York', 'UTC')
                    If None, uses default clinic timezone
    
    Returns:
        pytz timezone object
    """
    if not timezone_str:
        timezone_str = DEFAULT_CLINIC_TIMEZONE
    
    try:
        return pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        # Fallback to UTC if invalid timezone
        print(f"⚠️ Unknown timezone '{timezone_str}', using UTC")
        return pytz.UTC


def convert_time_to_timezone(
    date_str: str,
    time_str: str,
    from_tz: str = DEFAULT_CLINIC_TIMEZONE,
    to_tz: Optional[str] = None
) -> Dict[str, str]:
    """
    Convert a time from one timezone to another
    
    Args:
        date_str: Date in YYYY-MM-DD format
        time_str: Time string (can be "09:00 AM", "09:00", "HH:MM" format)
        from_tz: Source timezone (default: clinic timezone)
        to_tz: Target timezone (if None, uses from_tz - no conversion)
    
    Returns:
        Dictionary with converted time information:
        {
            "start_time": "09:00 AM",
            "end_time": "09:30 AM",
            "raw_time": "09:00",
            "timezone": "America/New_York",
            "original_time": "14:00" (if converted)
        }
    """
    if not to_tz or to_tz == from_tz:
        # No conversion needed
        return {
            "start_time": time_str,
            "raw_time": _extract_raw_time(time_str),
            "timezone": from_tz
        }
    
    # Parse time string
    time_obj = _parse_time_string(time_str)
    if not time_obj:
        # If parsing fails, return original
        return {
            "start_time": time_str,
            "raw_time": _extract_raw_time(time_str),
            "timezone": from_tz
        }
    
    # Create datetime in source timezone
    from_tz_obj = get_timezone(from_tz)
    to_tz_obj = get_timezone(to_tz)
    
    # Combine date and time
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    dt = datetime.combine(date_obj.date(), time_obj)
    dt = from_tz_obj.localize(dt)
    
    # Convert to target timezone
    dt_converted = dt.astimezone(to_tz_obj)
    
    # Format converted time
    converted_time_12h = dt_converted.strftime("%I:%M %p").lstrip("0")
    converted_time_24h = dt_converted.strftime("%H:%M")
    
    return {
        "start_time": converted_time_12h,
        "raw_time": converted_time_24h,
        "timezone": to_tz,
        "original_time": time_str,
        "original_timezone": from_tz
    }


def convert_slot_to_timezone(
    slot: Dict[str, Any],
    date_str: str,
    from_tz: str = DEFAULT_CLINIC_TIMEZONE,
    to_tz: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convert a time slot to user's timezone
    
    Args:
        slot: Slot dictionary with start_time, end_time, etc.
        date_str: Date in YYYY-MM-DD format
        from_tz: Source timezone (default: clinic timezone)
        to_tz: Target timezone (if None, uses from_tz - no conversion)
    
    Returns:
        Converted slot dictionary
    """
    # Validate date format
    if not date_str or not date_str.startswith("202"):
        # Try to extract date from slot if invalid
        date_str = slot.get("full_date")
        if not date_str or not date_str.startswith("202"):
            # Use today as fallback
            from datetime import datetime
            date_str = datetime.now().strftime("%Y-%m-%d")
    
    if not to_tz or to_tz == from_tz:
        # Add timezone info but no conversion
        slot["timezone"] = from_tz
        return slot
    
    # Convert start time
    start_converted = convert_time_to_timezone(
        date_str,
        slot.get("start_time", ""),
        from_tz,
        to_tz
    )
    
    # Convert end time (calculate from start + duration or use end_time)
    end_time = slot.get("end_time", "")
    if end_time:
        end_converted = convert_time_to_timezone(
            date_str,
            end_time,
            from_tz,
            to_tz
        )
    else:
        # Calculate end time from start + duration
        start_dt = _parse_time_string(slot.get("start_time", ""))
        if start_dt:
            duration = slot.get("duration_minutes", 30)
            # This is approximate - better to have end_time
            end_converted = {"start_time": "N/A", "raw_time": "N/A"}
    
    # Create converted slot
    converted_slot = slot.copy()
    converted_slot["start_time"] = start_converted["start_time"]
    converted_slot["raw_time"] = start_converted.get("raw_time", slot.get("raw_time"))
    if end_converted.get("start_time"):
        converted_slot["end_time"] = end_converted["start_time"]
    converted_slot["timezone"] = to_tz
    converted_slot["display_timezone"] = _format_timezone_name(to_tz)
    
    return converted_slot


def convert_slots_to_timezone(
    slots: List[Dict[str, Any]],
    date_str: str,
    from_tz: str = DEFAULT_CLINIC_TIMEZONE,
    to_tz: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Convert a list of slots to user's timezone
    
    Args:
        slots: List of slot dictionaries
        date_str: Date in YYYY-MM-DD format
        from_tz: Source timezone (default: clinic timezone)
        to_tz: Target timezone (if None, uses from_tz - no conversion)
    
    Returns:
        List of converted slot dictionaries
    """
    if not to_tz or to_tz == from_tz:
        # Add timezone info but no conversion
        for slot in slots:
            slot["timezone"] = from_tz
        return slots
    
    return [
        convert_slot_to_timezone(slot, date_str, from_tz, to_tz)
        for slot in slots
    ]


def _parse_time_string(time_str: str) -> Optional[datetime.time]:
    """
    Parse time string to time object
    
    Supports formats:
    - "09:00 AM"
    - "09:00"
    - "9:00 AM"
    - "14:30"
    """
    time_str = time_str.strip()
    
    # Try 12-hour format with AM/PM
    for fmt in ["%I:%M %p", "%I:%M%p", "%I %p", "%I%p"]:
        try:
            dt = datetime.strptime(time_str.upper(), fmt)
            return dt.time()
        except ValueError:
            continue
    
    # Try 24-hour format
    for fmt in ["%H:%M", "%H:%M:%S"]:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.time()
        except ValueError:
            continue
    
    return None


def _extract_raw_time(time_str: str) -> str:
    """
    Extract raw time (HH:MM) from time string
    """
    time_obj = _parse_time_string(time_str)
    if time_obj:
        return time_obj.strftime("%H:%M")
    return time_str


def _format_timezone_name(tz_str: str) -> str:
    """
    Format timezone name for display
    
    Examples:
    - "America/New_York" -> "Eastern Time"
    - "America/Los_Angeles" -> "Pacific Time"
    - "UTC" -> "UTC"
    """
    tz_mapping = {
        "America/New_York": "Eastern Time",
        "America/Chicago": "Central Time",
        "America/Denver": "Mountain Time",
        "America/Los_Angeles": "Pacific Time",
        "America/Phoenix": "Mountain Time (Arizona)",
        "America/Anchorage": "Alaska Time",
        "Pacific/Honolulu": "Hawaii Time",
        "UTC": "UTC",
    }
    
    return tz_mapping.get(tz_str, tz_str.replace("_", " "))


def get_user_timezone_from_browser(tz_str: Optional[str] = None) -> str:
    """
    Get user timezone from browser string (e.g., "America/New_York" or IANA format)
    
    Args:
        tz_str: Timezone string from browser (Intl.DateTimeFormat().resolvedOptions().timeZone)
    
    Returns:
        Validated timezone string or default
    """
    if not tz_str:
        return DEFAULT_CLINIC_TIMEZONE
    
    try:
        # Validate timezone
        pytz.timezone(tz_str)
        return tz_str
    except pytz.exceptions.UnknownTimeZoneError:
        print(f"⚠️ Invalid timezone from browser: '{tz_str}', using default")
        return DEFAULT_CLINIC_TIMEZONE

