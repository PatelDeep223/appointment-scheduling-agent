"""
Booking Tool
Provides functions to create, modify, and cancel appointments
"""

from typing import Dict, Any, Optional
from datetime import datetime
from api.calendly_integration import CalendlyClient


class BookingTool:
    """
    Tool for managing appointment bookings
    """
    
    def __init__(self, calendly_client: CalendlyClient):
        self.calendly_client = calendly_client
    
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
            appointment_type: Type of appointment
            date: Date in YYYY-MM-DD format
            start_time: Start time in HH:MM format
            patient_name: Patient's full name
            patient_email: Patient's email address
            patient_phone: Patient's phone number
            reason: Reason for visit
            
        Returns:
            Booking confirmation details
        """
        try:
            booking = await self.calendly_client.create_booking(
                appointment_type=appointment_type,
                date=date,
                start_time=start_time,
                patient_name=patient_name,
                patient_email=patient_email,
                patient_phone=patient_phone,
                reason=reason
            )
            
            return {
                "success": True,
                "booking": booking,
                "message": "Appointment booked successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to book appointment"
            }
    
    async def cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """
        Cancel an existing booking
        
        Args:
            booking_id: Booking ID to cancel
            
        Returns:
            Cancellation result
        """
        try:
            result = await self.calendly_client.cancel_booking(booking_id)
            
            return {
                "success": True,
                "result": result,
                "message": "Appointment cancelled successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to cancel appointment"
            }
    
    def validate_booking_request(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: Optional[str] = None,
        patient_email: Optional[str] = None,
        patient_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate booking request before creating
        
        Args:
            appointment_type: Type of appointment
            date: Date in YYYY-MM-DD format
            start_time: Start time in HH:MM format
            patient_name: Patient's name (optional for validation)
            patient_email: Patient's email (optional for validation)
            patient_phone: Patient's phone (optional for validation)
            
        Returns:
            Validation result with any errors
        """
        errors = []
        
        # Validate appointment type
        valid_types = ["consultation", "followup", "physical", "specialist"]
        if appointment_type not in valid_types:
            errors.append(f"Invalid appointment type. Must be one of: {', '.join(valid_types)}")
        
        # Validate date format
        try:
            booking_date = datetime.strptime(date, "%Y-%m-%d")
            if booking_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                errors.append("Appointment date must be in the future")
        except ValueError:
            errors.append("Invalid date format. Use YYYY-MM-DD")
        
        # Validate time format
        try:
            datetime.strptime(start_time, "%H:%M")
        except ValueError:
            errors.append("Invalid time format. Use HH:MM (24-hour format)")
        
        # Validate patient info if provided
        if patient_name and len(patient_name.strip()) < 2:
            errors.append("Patient name must be at least 2 characters")
        
        if patient_email:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, patient_email):
                errors.append("Invalid email address format")
        
        if patient_phone:
            import re
            phone_pattern = r'^\+?1?\d{9,15}$'
            if not re.match(phone_pattern, patient_phone.replace("-", "").replace(" ", "")):
                errors.append("Invalid phone number format")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def format_booking_confirmation(self, booking: Dict[str, Any]) -> str:
        """
        Format booking confirmation as a readable message
        
        Args:
            booking: Booking details dictionary
            
        Returns:
            Formatted confirmation message
        """
        lines = [
            "✅ Appointment Confirmed!",
            "",
            f"📅 Date: {booking.get('date', 'N/A')}",
            f"🕐 Time: {booking.get('start_time', 'N/A')}",
            f"📋 Type: {booking.get('appointment_type', 'N/A')}",
            f"🔖 Confirmation Code: {booking.get('confirmation_code', 'N/A')}",
            "",
            f"You'll receive a confirmation email at {booking.get('patient_email', 'N/A')}",
        ]
        
        clinic_info = booking.get("clinic_info", {})
        if clinic_info:
            lines.extend([
                "",
                "Clinic Information:",
                f"📍 {clinic_info.get('address', 'N/A')}",
                f"📞 {clinic_info.get('phone', 'N/A')}"
            ])
        
        return "\n".join(lines)
    
    async def reschedule_booking(
        self,
        booking_id: str,
        new_date: str,
        new_start_time: str
    ) -> Dict[str, Any]:
        """
        Reschedule an existing booking (cancel old, create new)
        
        Args:
            booking_id: Existing booking ID
            new_date: New date in YYYY-MM-DD format
            new_start_time: New start time in HH:MM format
            
        Returns:
            Rescheduling result
        """
        # This is a simplified version - in real Calendly API, you'd use their reschedule endpoint
        # For now, we'll cancel and ask user to create a new booking
        
        cancel_result = await self.cancel_booking(booking_id)
        
        if not cancel_result["success"]:
            return {
                "success": False,
                "error": "Failed to cancel existing booking",
                "message": "Could not reschedule appointment. Please cancel and book again."
            }
        
        return {
            "success": True,
            "message": "Booking cancelled. Please book a new appointment with the desired time.",
            "cancelled_booking_id": booking_id,
            "new_date": new_date,
            "new_start_time": new_start_time
        }

