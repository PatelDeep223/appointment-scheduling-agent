"""
Booking database model
Stores appointment bookings with proper UUIDs instead of TEMP IDs
"""

from sqlalchemy import Column, String, DateTime, Integer, Enum, Text, Index
from sqlalchemy.sql import func
import uuid
from enum import Enum as PyEnum
from datetime import datetime
import os

# Import Base - try multiple strategies
try:
    # Strategy 1: Direct import (when running from backend/ directory)
    from database import Base
except ImportError:
    try:
        # Strategy 2: Relative import (when running as package)
        from ..database import Base
    except ImportError:
        # Strategy 3: Absolute import (when running from project root)
        from backend.database import Base

# Note: UUIDs are stored as String(36) which works for both MySQL and SQLite
# MySQL will use utf8mb4_bin collation from connection string charset=utf8mb4


class BookingStatus(PyEnum):
    """Booking status enumeration"""
    PENDING = "pending"  # Booking link created, waiting for user to complete
    CONFIRMED = "confirmed"  # User completed booking in Calendly
    CANCELLED = "cancelled"  # Booking was cancelled
    NO_SHOW = "no_show"  # User didn't show up


class Booking(Base):
    """
    Booking model - stores appointment bookings
    
    Uses UUID as primary key instead of TEMP IDs
    Optimized for MySQL with CHAR(36) for UUID storage
    """
    __tablename__ = "bookings"
    
    # Primary key - Use String(36) for UUID storage (works for both MySQL and SQLite)
    # MySQL will use utf8mb4_bin collation from connection string charset=utf8mb4
    # SQLite doesn't support collation parameter, so we omit it for compatibility
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    
    # Calendly integration fields
    calendly_event_uri = Column(String(500), unique=True, nullable=True, index=True)
    calendly_invitee_uri = Column(String(500), nullable=True, index=True)
    event_type_uuid = Column(String(100), nullable=False)
    scheduling_url = Column(Text, nullable=False)  # Pre-filled Calendly link
    
    # Appointment details
    appointment_type = Column(String(100), nullable=False)  # e.g., "General Consultation"
    date = Column(String(10), nullable=False)  # YYYY-MM-DD format
    start_time = Column(String(10), nullable=False)  # HH:MM format
    end_time = Column(String(10), nullable=True)  # HH:MM format
    duration_minutes = Column(Integer, nullable=False)
    
    # Patient information
    patient_name = Column(String(200), nullable=False)
    patient_email = Column(String(200), nullable=False, index=True)
    patient_phone = Column(String(50), nullable=True)
    reason = Column(Text, nullable=True)
    
    # Status and tracking
    # Use String for MySQL compatibility (Enum requires CREATE TYPE in MySQL)
    status = Column(
        String(20),  # String type for better MySQL compatibility
        nullable=False,
        default=BookingStatus.PENDING.value,
        index=True
    )
    confirmation_code = Column(String(20), unique=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Cancellation details
    cancel_reason = Column(Text, nullable=True)
    canceler_type = Column(String(50), nullable=True)  # "invitee" or "host"
    
    # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    extra_data = Column(Text, nullable=True)  # JSON string for extra data
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_booking_email_status', 'patient_email', 'status'),
        Index('idx_booking_date_status', 'date', 'status'),
        Index('idx_booking_created', 'created_at'),
    )
    
    def to_dict(self) -> dict:
        """Convert booking to dictionary"""
        # Handle status - it's stored as string, but we can validate it
        status_value = self.status
        if isinstance(status_value, BookingStatus):
            status_value = status_value.value
        elif status_value not in [s.value for s in BookingStatus]:
            status_value = BookingStatus.PENDING.value  # Default if invalid
        
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
            "status": status_value,
            "confirmation_code": self.confirmation_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "cancel_reason": self.cancel_reason,
            "canceler_type": self.canceler_type,
            "extra_data": self.extra_data,  # Renamed from 'metadata' to avoid SQLAlchemy conflict
        }
    
    def __repr__(self):
        status_str = self.status if isinstance(self.status, str) else self.status.value
        return f"<Booking(id={self.id}, status={status_str}, patient={self.patient_email})>"

