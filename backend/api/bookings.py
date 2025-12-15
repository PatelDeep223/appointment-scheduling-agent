"""
Booking API endpoints
Uses proper database-backed booking system with UUIDs
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

try:
    # Try relative imports first (when running from backend directory)
    from ..database import get_db
    from ..services.booking_service import BookingService
    from ..models.booking import BookingStatus
    from ..api.calendly_integration import CalendlyClient
    from ..models.schemas import AppointmentRequest
except ImportError:
    # Fallback to absolute imports (when running from project root)
    from backend.database import get_db
    from backend.services.booking_service import BookingService
    from backend.models.booking import BookingStatus
    from backend.api.calendly_integration import CalendlyClient
    from backend.models.schemas import AppointmentRequest

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


def get_booking_service(
    db: Session = Depends(get_db),
    calendly_client: CalendlyClient = None
):
    """Dependency to get BookingService or InMemoryBookingService"""
    if calendly_client is None:
        try:
            from backend.main import calendly_client
        except ImportError:
            try:
                from main import calendly_client
            except ImportError:
                # Fallback: create a new client
                calendly_client = CalendlyClient()
    
    # Check if database connection is working
    try:
        from ..database import check_db_connection
    except ImportError:
        try:
            from backend.database import check_db_connection
        except ImportError:
            check_db_connection = lambda: False
    
    # Use in-memory service if database is not available
    if not check_db_connection():
        try:
            from ..services.in_memory_booking_service import InMemoryBookingService
        except ImportError:
            from backend.services.in_memory_booking_service import InMemoryBookingService
        return InMemoryBookingService(calendly_client)
    
    # Use database service
    return BookingService(db, calendly_client)


@router.post("")
async def create_booking(
    request: AppointmentRequest,
    booking_service: BookingService = Depends(get_booking_service)
):
    """
    Create a new booking
    
    Returns booking with UUID (not TEMP ID)
    """
    try:
        # Get Calendly client
        from backend.main import calendly_client
        
        # Create Calendly scheduling link
        calendly_result = await calendly_client.create_booking(
            appointment_type=request.appointment_type,
            date=request.date,
            start_time=request.start_time,
            patient_name=request.patient_name,
            patient_email=request.patient_email,
            patient_phone=request.patient_phone,
            reason=request.reason
        )
        
        # Get appointment type config
        normalized_type = calendly_client._normalize_appointment_type(request.appointment_type)
        appt_config = calendly_client.appointment_types[normalized_type]
        
        # Create booking in database
        booking = booking_service.create_booking(
            appointment_type=appt_config["name"],
            date=request.date,
            start_time=request.start_time,
            patient_name=request.patient_name,
            patient_email=request.patient_email,
            patient_phone=request.patient_phone,
            reason=request.reason,
            scheduling_url=calendly_result.get("scheduling_link", ""),
            event_type_uuid=appt_config["uuid"],
            duration_minutes=appt_config["duration"]
        )
        
        return {
            "id": booking.id,  # UUID, not TEMP
            "status": booking.status.value,
            "confirmation_code": booking.confirmation_code,
            "scheduling_url": booking.scheduling_url,
            "appointment_type": booking.appointment_type,
            "date": booking.date,
            "start_time": booking.start_time,
            "patient_name": booking.patient_name,
            "patient_email": booking.patient_email,
            "message": calendly_result.get("message", "Please complete your booking using the scheduling link.")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{booking_id}")
async def get_booking(
    booking_id: str,
    booking_service: BookingService = Depends(get_booking_service)
):
    """
    Get booking by UUID
    
    No more 404 errors due to lost in-memory data!
    """
    booking = booking_service.get_booking_by_id(booking_id)
    
    if not booking:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Booking not found",
                "booking_id": booking_id,
                "message": "Booking not found in database. Verify the booking ID is correct."
            }
        )
    
    return booking.to_dict()


@router.get("/confirmation/{confirmation_code}")
async def get_booking_by_confirmation(
    confirmation_code: str,
    booking_service: BookingService = Depends(get_booking_service)
):
    """Get booking by confirmation code"""
    booking = booking_service.get_booking_by_confirmation_code(confirmation_code)
    
    if not booking:
        raise HTTPException(
            status_code=404,
            detail=f"Booking not found for confirmation code: {confirmation_code}"
        )
    
    return booking.to_dict()


@router.get("")
async def list_bookings(
    status: Optional[str] = Query(None, description="Filter by status: pending, confirmed, cancelled"),
    email: Optional[str] = Query(None, description="Filter by patient email"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    booking_service: BookingService = Depends(get_booking_service)
):
    """List bookings with filters"""
    # Convert status string to enum
    status_enum = None
    if status:
        try:
            # Map string to enum
            status_map = {
                "pending": BookingStatus.PENDING,
                "confirmed": BookingStatus.CONFIRMED,
                "cancelled": BookingStatus.CANCELLED,
                "canceled": BookingStatus.CANCELLED,  # Alternative spelling
                "no_show": BookingStatus.NO_SHOW,
                "no-show": BookingStatus.NO_SHOW  # Alternative format
            }
            status_enum = status_map.get(status.lower())
            if not status_enum:
                raise ValueError(f"Invalid status: {status}")
        except (KeyError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be one of: pending, confirmed, cancelled, no_show"
            )
    
    bookings = booking_service.list_bookings(
        status=status_enum,
        email=email,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset
    )
    
    return {
        "bookings": [booking.to_dict() for booking in bookings],
        "total": len(bookings),
        "limit": limit,
        "offset": offset
    }


@router.delete("/{booking_id}")
async def cancel_booking(
    booking_id: str,
    reason: Optional[str] = None,
    booking_service: BookingService = Depends(get_booking_service)
):
    """Cancel a booking"""
    booking = booking_service.cancel_booking(booking_id, reason)
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return {
        "id": booking.id,
        "status": booking.status.value,
        "cancelled_at": booking.cancelled_at.isoformat() if booking.cancelled_at else None,
        "message": "Booking cancelled successfully"
    }


@router.get("/patient/{email}")
async def get_patient_bookings(
    email: str,
    status: Optional[str] = None,
    booking_service: BookingService = Depends(get_booking_service)
):
    """Get all bookings for a patient by email"""
    status_enum = None
    if status:
        try:
            status_enum = BookingStatus[status.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    bookings = booking_service.get_booking_by_email(email, status=status_enum)
    
    return {
        "email": email,
        "bookings": [booking.to_dict() for booking in bookings],
        "count": len(bookings)
    }

