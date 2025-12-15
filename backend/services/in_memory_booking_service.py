"""
In-memory booking service for demo mode when database is unavailable
Provides same interface as BookingService but stores data in memory
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import random
import string
import uuid

try:
    from ..models.booking import BookingStatus
    from ..api.calendly_integration import CalendlyClient
except ImportError:
    from backend.models.booking import BookingStatus
    from backend.api.calendly_integration import CalendlyClient


class InMemoryBooking:
    """In-memory booking representation"""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', str(uuid.uuid4()))
        self.calendly_event_uri = kwargs.get('calendly_event_uri')
        self.calendly_invitee_uri = kwargs.get('calendly_invitee_uri')
        self.event_type_uuid = kwargs.get('event_type_uuid')
        self.scheduling_url = kwargs.get('scheduling_url')
        self.appointment_type = kwargs.get('appointment_type')
        self.date = kwargs.get('date')
        self.start_time = kwargs.get('start_time')
        self.end_time = kwargs.get('end_time')
        self.duration_minutes = kwargs.get('duration_minutes')
        self.patient_name = kwargs.get('patient_name')
        self.patient_email = kwargs.get('patient_email')
        self.patient_phone = kwargs.get('patient_phone')
        self.reason = kwargs.get('reason')
        self.status = kwargs.get('status', BookingStatus.PENDING.value)
        self.confirmation_code = kwargs.get('confirmation_code')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
        self.confirmed_at = kwargs.get('confirmed_at')
        self.cancelled_at = kwargs.get('cancelled_at')
        self.cancel_reason = kwargs.get('cancel_reason')
        self.canceler_type = kwargs.get('canceler_type')
        self.extra_data = kwargs.get('extra_data')
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "calendly_event_uri": self.calendly_event_uri,
            "calendly_invitee_uri": self.calendly_invitee_uri,
            "event_type_uuid": self.event_type_uuid,
            "scheduling_url": self.scheduling_url,
            "appointment_type": self.appointment_type,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "patient_name": self.patient_name,
            "patient_email": self.patient_email,
            "patient_phone": self.patient_phone,
            "reason": self.reason,
            "status": self.status,
            "confirmation_code": self.confirmation_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "cancel_reason": self.cancel_reason,
            "canceler_type": self.canceler_type,
            "extra_data": self.extra_data,
        }


class InMemoryBookingService:
    """
    In-memory booking service for demo mode
    Provides same interface as BookingService but without database
    """
    
    def __init__(self, calendly_client: CalendlyClient):
        self.calendly_client = calendly_client
        self._bookings: Dict[str, InMemoryBooking] = {}
        self._by_confirmation_code: Dict[str, str] = {}  # code -> booking_id
        self._by_event_uri: Dict[str, str] = {}  # event_uri -> booking_id
    
    def generate_confirmation_code(self) -> str:
        """Generate a unique confirmation code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    def create_booking(
        self,
        appointment_type: str,
        date: str,
        start_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        reason: str,
        scheduling_url: str,
        event_type_uuid: str,
        duration_minutes: int
    ) -> InMemoryBooking:
        """Create a new booking in memory"""
        # Generate unique confirmation code
        confirmation_code = self.generate_confirmation_code()
        while confirmation_code in self._by_confirmation_code:
            confirmation_code = self.generate_confirmation_code()
        
        booking = InMemoryBooking(
            event_type_uuid=event_type_uuid,
            scheduling_url=scheduling_url,
            appointment_type=appointment_type,
            date=date,
            start_time=start_time,
            duration_minutes=duration_minutes,
            patient_name=patient_name,
            patient_email=patient_email,
            patient_phone=patient_phone,
            reason=reason,
            status=BookingStatus.PENDING.value,
            confirmation_code=confirmation_code
        )
        
        self._bookings[booking.id] = booking
        self._by_confirmation_code[confirmation_code] = booking.id
        
        print(f"✅ Booking created in memory with ID: {booking.id}")
        return booking
    
    def get_booking_by_id(self, booking_id: str) -> Optional[InMemoryBooking]:
        """Get booking by UUID"""
        return self._bookings.get(booking_id)
    
    def get_booking_by_confirmation_code(self, confirmation_code: str) -> Optional[InMemoryBooking]:
        """Get booking by confirmation code"""
        booking_id = self._by_confirmation_code.get(confirmation_code)
        return self._bookings.get(booking_id) if booking_id else None
    
    def get_booking_by_calendly_event_uri(self, event_uri: str) -> Optional[InMemoryBooking]:
        """Get booking by Calendly event URI"""
        booking_id = self._by_event_uri.get(event_uri)
        return self._bookings.get(booking_id) if booking_id else None
    
    def get_booking_by_email(
        self,
        email: str,
        status: Optional[BookingStatus] = None
    ) -> List[InMemoryBooking]:
        """Get bookings by patient email"""
        bookings = [
            b for b in self._bookings.values()
            if b.patient_email == email
        ]
        if status:
            bookings = [b for b in bookings if b.status == status.value]
        return sorted(bookings, key=lambda x: x.created_at, reverse=True)
    
    def update_booking_from_webhook(
        self,
        event_uri: str,
        invitee_uri: str,
        start_time: str,
        end_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: Optional[str] = None
    ) -> Optional[InMemoryBooking]:
        """Update booking when webhook confirms it"""
        booking = self.get_booking_by_calendly_event_uri(event_uri)
        
        if not booking:
            pending_bookings = self.get_booking_by_email(
                patient_email,
                status=BookingStatus.PENDING
            )
            if pending_bookings:
                booking = pending_bookings[0]
        
        if booking:
            booking.calendly_event_uri = event_uri
            booking.calendly_invitee_uri = invitee_uri
            booking.status = BookingStatus.CONFIRMED.value
            booking.confirmed_at = datetime.utcnow()
            booking.updated_at = datetime.utcnow()
            
            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    booking.date = dt.strftime("%Y-%m-%d")
                    booking.start_time = dt.strftime("%H:%M")
                except:
                    pass
            
            if end_time:
                try:
                    dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    booking.end_time = dt.strftime("%H:%M")
                except:
                    pass
            
            if patient_name:
                booking.patient_name = patient_name
            if patient_phone:
                booking.patient_phone = patient_phone
            
            self._by_event_uri[event_uri] = booking.id
            
            print(f"✅ Booking {booking.id} confirmed via webhook (in-memory)")
            return booking
        
        return None
    
    def cancel_booking(self, booking_id: str, reason: Optional[str] = None) -> Optional[InMemoryBooking]:
        """Cancel a booking"""
        booking = self.get_booking_by_id(booking_id)
        if not booking:
            return None
        
        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.utcnow()
        booking.updated_at = datetime.utcnow()
        if reason:
            booking.cancel_reason = reason
        
        print(f"✅ Booking {booking_id} cancelled (in-memory)")
        return booking
    
    def list_bookings(
        self,
        status: Optional[BookingStatus] = None,
        email: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[InMemoryBooking]:
        """List bookings with filters"""
        bookings = list(self._bookings.values())
        
        if status:
            bookings = [b for b in bookings if b.status == status.value]
        
        if email:
            bookings = [b for b in bookings if b.patient_email == email]
        
        if date_from:
            bookings = [b for b in bookings if b.date >= date_from]
        
        if date_to:
            bookings = [b for b in bookings if b.date <= date_to]
        
        bookings = sorted(bookings, key=lambda x: x.created_at, reverse=True)
        return bookings[offset:offset + limit]
    
    def get_pending_bookings_count(self) -> int:
        """Get count of pending bookings"""
        return len([b for b in self._bookings.values() if b.status == BookingStatus.PENDING.value])
    
    def get_confirmed_bookings_count(self) -> int:
        """Get count of confirmed bookings"""
        return len([b for b in self._bookings.values() if b.status == BookingStatus.CONFIRMED.value])

