"""
Booking service - handles all booking operations with database
Replaces in-memory storage with proper database persistence
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import random
import string

try:
    # Try relative imports first (when running from backend directory)
    from ..models.booking import Booking, BookingStatus
    from ..api.calendly_integration import CalendlyClient
except ImportError:
    # Fallback to absolute imports (when running from project root)
    from backend.models.booking import Booking, BookingStatus
    from backend.api.calendly_integration import CalendlyClient


class BookingService:
    """
    Service for managing bookings with database persistence
    """
    
    def __init__(self, db: Session, calendly_client: CalendlyClient):
        self.db = db
        self.calendly_client = calendly_client
    
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
    ) -> Booking:
        """
        Create a new booking in the database
        
        Returns:
            Booking object with UUID (not TEMP ID)
        """
        # Generate unique confirmation code
        confirmation_code = self.generate_confirmation_code()
        
        # Ensure confirmation code is unique
        while self.db.query(Booking).filter(Booking.confirmation_code == confirmation_code).first():
            confirmation_code = self.generate_confirmation_code()
        
        # Create booking
        booking = Booking(
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
            status=BookingStatus.PENDING.value,  # Store as string value
            confirmation_code=confirmation_code
        )
        
        try:
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)
            
            print(f"✅ Booking created with ID: {booking.id} (not TEMP)")
            return booking
        except Exception as e:
            self.db.rollback()
            print(f"❌ Error creating booking: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def get_booking_by_id(self, booking_id: str) -> Optional[Booking]:
        """Get booking by UUID"""
        return self.db.query(Booking).filter(Booking.id == booking_id).first()
    
    def get_booking_by_confirmation_code(self, confirmation_code: str) -> Optional[Booking]:
        """Get booking by confirmation code"""
        return self.db.query(Booking).filter(Booking.confirmation_code == confirmation_code).first()
    
    def get_booking_by_calendly_event_uri(self, event_uri: str) -> Optional[Booking]:
        """Get booking by Calendly event URI"""
        return self.db.query(Booking).filter(Booking.calendly_event_uri == event_uri).first()
    
    def get_booking_by_email(
        self,
        email: str,
        status: Optional[BookingStatus] = None
    ) -> List[Booking]:
        """Get bookings by patient email"""
        query = self.db.query(Booking).filter(Booking.patient_email == email)
        if status:
            query = query.filter(Booking.status == status.value)
        return query.order_by(Booking.created_at.desc()).all()
    
    def update_booking_from_webhook(
        self,
        event_uri: str,
        invitee_uri: str,
        start_time: str,
        end_time: str,
        patient_name: str,
        patient_email: str,
        patient_phone: Optional[str] = None
    ) -> Optional[Booking]:
        """
        Update booking when webhook confirms it
        
        Tries to match by:
        1. Calendly event URI (if already set)
        2. Patient email (if pending booking exists)
        """
        # First, try to find by event URI
        booking = self.get_booking_by_calendly_event_uri(event_uri)
        
        # If not found, try to match by email (for pending bookings)
        if not booking:
            pending_bookings = self.get_booking_by_email(
                patient_email,
                status=BookingStatus.PENDING
            )
            if pending_bookings:
                # Use the most recent pending booking
                booking = pending_bookings[0]
        
        if booking:
            # Update booking with Calendly data
            booking.calendly_event_uri = event_uri
            booking.calendly_invitee_uri = invitee_uri
            booking.status = BookingStatus.CONFIRMED.value
            booking.confirmed_at = datetime.utcnow()
            
            # Update times if provided
            if start_time:
                # Parse ISO format to extract date and time
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
            
            # Update patient info if different
            if patient_name and booking.patient_name != patient_name:
                booking.patient_name = patient_name
            if patient_phone and booking.patient_phone != patient_phone:
                booking.patient_phone = patient_phone
            
            self.db.commit()
            self.db.refresh(booking)
            
            print(f"✅ Booking {booking.id} confirmed via webhook")
            return booking
        
        print(f"⚠️  No booking found to match webhook (event_uri: {event_uri}, email: {patient_email})")
        return None
    
    def cancel_booking(self, booking_id: str, reason: Optional[str] = None) -> Optional[Booking]:
        """Cancel a booking"""
        booking = self.get_booking_by_id(booking_id)
        if not booking:
            return None
        
        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.utcnow()
        if reason:
            booking.cancel_reason = reason
        
        self.db.commit()
        self.db.refresh(booking)
        
        return booking
    
    def list_bookings(
        self,
        status: Optional[BookingStatus] = None,
        email: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Booking]:
        """List bookings with filters"""
        query = self.db.query(Booking)
        
        if status:
            query = query.filter(Booking.status == status.value)
        
        if email:
            query = query.filter(Booking.patient_email == email)
        
        if date_from:
            query = query.filter(Booking.date >= date_from)
        
        if date_to:
            query = query.filter(Booking.date <= date_to)
        
        return query.order_by(Booking.created_at.desc()).limit(limit).offset(offset).all()
    
    def get_pending_bookings_count(self) -> int:
        """Get count of pending bookings"""
        return self.db.query(Booking).filter(Booking.status == BookingStatus.PENDING.value).count()
    
    def get_confirmed_bookings_count(self) -> int:
        """Get count of confirmed bookings"""
        return self.db.query(Booking).filter(Booking.status == BookingStatus.CONFIRMED.value).count()

