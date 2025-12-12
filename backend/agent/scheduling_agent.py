"""
Main scheduling agent with intelligent conversation flow
Handles context switching between scheduling and FAQ answering
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from .prompts import SYSTEM_PROMPTS, RESPONSE_TEMPLATES
from rag.faq_rag import FAQRetriever
from api.calendly_integration import CalendlyClient


class SchedulingAgent:
    """
    Intelligent conversational agent for appointment scheduling
    Manages conversation flow, context switching, and booking logic
    """
    
    def __init__(self):
        self.appointment_types = {
            "consultation": {"duration": 30, "name": "General Consultation"},
            "followup": {"duration": 15, "name": "Follow-up"},
            "physical": {"duration": 45, "name": "Physical Exam"},
            "specialist": {"duration": 60, "name": "Specialist Consultation"}
        }
        
        self.context_handlers = {
            "greeting": self._handle_greeting,
            "collecting_reason": self._handle_collecting_reason,
            "collecting_time_preference": self._handle_time_preference,
            "selecting_slot": self._handle_slot_selection,
            "collecting_patient_info": self._handle_patient_info,
            "confirming": self._handle_confirmation,
            "faq": self._handle_faq,
            "faq_during_booking": self._handle_faq_during_booking
        }
    
    async def process_message(
        self,
        message: str,
        session: Dict[str, Any],
        faq_retriever: FAQRetriever,
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """
        Main message processing logic with context awareness
        
        Args:
            message: User's message
            session: Current session data
            faq_retriever: FAQ retrieval system
            calendly_client: Calendly API client
        
        Returns:
            Response dictionary with message and updated context
        """
        
        # First, check if this is an FAQ question
        faq_response = await self._check_faq(message, faq_retriever)
        
        if faq_response:
            # If we're in the middle of booking, note that we'll return
            if session["context"] not in ["greeting", "faq"]:
                return {
                    "message": f"{faq_response}\n\nNow, let's get back to scheduling your appointment. {self._get_context_continuation(session)}",
                    "context": session["context"]  # Return to previous context
                }
            else:
                return {
                    "message": f"{faq_response}\n\nWould you like to schedule an appointment?",
                    "context": "faq"
                }
        
        # Process based on current context
        current_context = session.get("context", "greeting")
        handler = self.context_handlers.get(
            current_context,
            self._handle_greeting
        )
        
        return await handler(
            message=message,
            session=session,
            calendly_client=calendly_client
        )
    
    async def _check_faq(
        self,
        message: str,
        faq_retriever: FAQRetriever
    ) -> Optional[str]:
        """
        Check if message is an FAQ query
        
        Returns:
            FAQ answer if found, None otherwise
        """
        # Quick keyword check for common FAQs
        lower_msg = message.lower()
        
        # Insurance
        if any(word in lower_msg for word in ['insurance', 'accept', 'coverage']):
            return await faq_retriever.get_answer("insurance")
        
        # Location
        if any(word in lower_msg for word in ['location', 'address', 'where', 'directions']):
            return await faq_retriever.get_answer("location")
        
        # Hours
        if any(word in lower_msg for word in ['hours', 'open', 'close', 'when open']):
            return await faq_retriever.get_answer("hours")
        
        # Parking
        if 'parking' in lower_msg:
            return await faq_retriever.get_answer("parking")
        
        # Cancellation
        if any(word in lower_msg for word in ['cancel', 'cancellation', 'reschedule']):
            return await faq_retriever.get_answer("cancellation")
        
        # First visit
        if any(phrase in lower_msg for phrase in ['first visit', 'new patient', 'what to bring', 'what do i bring']):
            return await faq_retriever.get_answer("first_visit")
        
        # Contact
        if any(word in lower_msg for word in ['phone', 'call', 'contact', 'reach']):
            return await faq_retriever.get_answer("contact")
        
        # Payment
        if any(word in lower_msg for word in ['payment', 'pay', 'cost', 'price', 'billing']):
            return await faq_retriever.get_answer("payment")
        
        return None
    
    async def _handle_greeting(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """Handle initial greeting and scheduling intent"""
        lower_msg = message.lower()
        
        # Check for scheduling intent
        scheduling_keywords = ['appointment', 'schedule', 'book', 'see doctor', 'visit', 'checkup']
        
        if any(keyword in lower_msg for keyword in scheduling_keywords):
            return {
                "message": RESPONSE_TEMPLATES["ask_reason"],
                "context": "collecting_reason",
                "suggestions": [
                    "I have a headache",
                    "Annual checkup",
                    "Follow-up visit"
                ]
            }
        
        # General greeting
        return {
            "message": RESPONSE_TEMPLATES["greeting"],
            "context": "greeting",
            "suggestions": [
                "I need an appointment",
                "What insurance do you accept?",
                "What are your hours?"
            ]
        }
    
    async def _handle_collecting_reason(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """Determine appointment type based on reason"""
        lower_msg = message.lower()
        
        # Determine appointment type
        appointment_type = "consultation"  # default
        
        if any(word in lower_msg for word in ['follow', 'followup', 'follow-up', 'check up', 'checkup']):
            appointment_type = "followup"
        elif any(word in lower_msg for word in ['physical', 'exam', 'examination']):
            appointment_type = "physical"
        elif any(word in lower_msg for word in ['specialist', 'cardio', 'derm', 'neuro']):
            appointment_type = "specialist"
        
        appt_info = self.appointment_types[appointment_type]
        
        response = f"I recommend a {appt_info['name']} ({appt_info['duration']} minutes) where the doctor can assess your symptoms. "
        response += "When would you like to come in? Do you have a preference for morning or afternoon appointments?"
        
        return {
            "message": response,
            "context": "collecting_time_preference",
            "appointment_type": appointment_type,
            "suggestions": [
                "Morning",
                "Afternoon",
                "As soon as possible"
            ]
        }
    
    async def _handle_time_preference(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """Handle time preference and show available slots"""
        lower_msg = message.lower()
        
        # Parse time preference
        is_afternoon = any(word in lower_msg for word in ['afternoon', 'evening', 'pm', 'later'])
        is_morning = any(word in lower_msg for word in ['morning', 'am', 'early'])
        is_asap = any(word in lower_msg for word in ['asap', 'soon as possible', 'urgent', 'today', 'tomorrow'])
        
        # Get available slots
        appointment_type = session.get("appointment_type", "consultation")
        
        try:
            # Fetch from Calendly
            # Calendly API requires future dates, so start from tomorrow
            today = datetime.now()
            available_slots = []
            
            # Start from tomorrow (day_offset=1) since Calendly requires future dates
            for day_offset in range(1, 8):  # Check next 7 days (starting from tomorrow)
                check_date = today + timedelta(days=day_offset)
                date_str = check_date.strftime("%Y-%m-%d")
                
                slots = await calendly_client.get_availability(
                    date=date_str,
                    appointment_type=appointment_type
                )
                
                # Filter by time preference
                for slot in slots.get("available_slots", []):
                    if not slot["available"]:
                        continue
                    
                    # Extract hour from time string (handles "09:00 AM" or "14:30" format)
                    time_str = slot.get("start_time", "")
                    try:
                        if "AM" in time_str.upper() or "PM" in time_str.upper():
                            time_obj = datetime.strptime(time_str.upper().strip(), "%I:%M %p")
                            hour = time_obj.hour
                        else:
                            # Try 24-hour format
                            hour_part = time_str.split(":")[0]
                            hour = int(hour_part) % 24
                    except:
                        # Fallback: try to extract first number
                        import re
                        match = re.search(r'(\d{1,2})', time_str)
                        hour = int(match.group(1)) % 24 if match else 12
                    
                    if is_morning and hour >= 12:
                        continue
                    if is_afternoon and hour < 12:
                        continue
                    
                    slot["date"] = check_date.strftime("%A, %B %d")
                    slot["full_date"] = date_str
                    available_slots.append(slot)
                    
                    if len(available_slots) >= 4:
                        break
                
                if len(available_slots) >= 4:
                    break
            
            if not available_slots:
                return {
                    "message": RESPONSE_TEMPLATES["no_slots_available"],
                    "context": "collecting_time_preference",
                    "suggestions": ["Try different time", "Contact office"]
                }
            
            # Format slots
            slot_list = "\n".join([
                f"• {slot['date']} at {slot['start_time']}"
                for slot in available_slots[:4]
            ])
            
            time_pref = "afternoon" if is_afternoon else "morning" if is_morning else ""
            response = f"Let me check our {time_pref} availability. I have these options:\n\n{slot_list}\n\nWhich works best for you?"
            
            # Store slots in session
            session["available_slots"] = available_slots
            
            return {
                "message": response,
                "context": "selecting_slot",
                "suggestions": [slot['start_time'] for slot in available_slots[:3]]
            }
            
        except Exception as e:
            print(f"Error fetching availability: {e}")
            return {
                "message": "I'm having trouble accessing our schedule right now. Would you like me to have someone call you back?",
                "context": "error",
                "suggestions": ["Yes, call me back", "Try again"]
            }
    
    async def _handle_slot_selection(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """Handle slot selection"""
        # Parse selected time
        lower_msg = message.lower()
        
        # Try to match with available slots
        available_slots = session.get("available_slots", [])
        selected_slot = None
        
        for slot in available_slots:
            if slot["start_time"].lower() in lower_msg or slot["date"].lower() in lower_msg:
                selected_slot = slot
                break
        
        if not selected_slot and available_slots:
            # Try to match just time
            time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', lower_msg, re.IGNORECASE)
            if time_match:
                search_time = time_match.group(0)
                for slot in available_slots:
                    if search_time in slot["start_time"].lower():
                        selected_slot = slot
                        break
        
        if not selected_slot:
            return {
                "message": "I didn't catch which time you'd prefer. Could you specify one of the times I mentioned?",
                "context": "selecting_slot",
                "suggestions": [slot["start_time"] for slot in available_slots[:3]]
            }
        
        # Store selection
        session["selected_slot"] = selected_slot
        
        response = f"Excellent! {selected_slot['date']} at {selected_slot['start_time']} for a {self.appointment_types[session['appointment_type']]['name']}.\n\n"
        response += "Before I confirm, I'll need a few details:\n"
        response += "• Your full name?\n"
        response += "• Best phone number to reach you?\n"
        response += "• Email address for confirmation?"
        
        return {
            "message": response,
            "context": "collecting_patient_info"
        }
    
    async def _handle_patient_info(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """Collect and validate patient information"""
        
        # Extract information
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message)
        phone_match = re.search(r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', message)
        
        patient_info = session.get("patient_info", {})
        
        if email_match:
            patient_info["email"] = email_match.group(0)
        if phone_match:
            patient_info["phone"] = phone_match.group(0)
        
        # Extract name (everything that's not email or phone)
        name_text = message
        if email_match:
            name_text = name_text.replace(email_match.group(0), "")
        if phone_match:
            name_text = name_text.replace(phone_match.group(0), "")
        
        name = name_text.strip()
        if name and not patient_info.get("name"):
            # Clean name
            name = re.sub(r'[^a-zA-Z\s]', '', name).strip()
            if name:
                patient_info["name"] = name
        
        session["patient_info"] = patient_info
        
        # Check if we have all required info
        required_fields = ["name", "email", "phone"]
        missing_fields = [f for f in required_fields if f not in patient_info or not patient_info[f]]
        
        if missing_fields:
            missing_str = ", ".join(missing_fields)
            return {
                "message": f"I still need your {missing_str}. Please provide these details.",
                "context": "collecting_patient_info"
            }
        
        # All info collected, proceed to book
        selected_slot = session["selected_slot"]
        appointment_type = session["appointment_type"]
        
        try:
            # Book appointment - need to convert time format for API
            # Convert "09:00 AM" format to "09:00" if needed
            api_start_time = selected_slot.get("raw_time")
            if not api_start_time:
                # Extract time from formatted time string
                time_str = selected_slot["start_time"]
                try:
                    if "AM" in time_str.upper() or "PM" in time_str.upper():
                        time_obj = datetime.strptime(time_str.upper().strip(), "%I:%M %p")
                        api_start_time = time_obj.strftime("%H:%M")
                    else:
                        api_start_time = time_str
                except:
                    # Fallback
                    api_start_time = "10:00"
            
            booking = await calendly_client.create_booking(
                appointment_type=appointment_type,
                date=selected_slot["full_date"],
                start_time=api_start_time,
                patient_name=patient_info["name"],
                patient_email=patient_info["email"],
                patient_phone=patient_info["phone"],
                reason=session.get("reason", "General consultation")
            )
            
            appt_info = self.appointment_types[appointment_type]
            
            response = f"Perfect! All set! 🎉\n\n"
            response += f"Your appointment is confirmed:\n"
            response += f"• Date & Time: {selected_slot['date']} at {selected_slot['start_time']}\n"
            response += f"• Type: {appt_info['name']}\n"
            response += f"• Duration: {appt_info['duration']} minutes\n"
            response += f"• Confirmation Code: {booking['confirmation_code']}\n\n"
            response += f"You'll receive a confirmation email at {patient_info['email']} with all the details.\n\n"
            response += "Is there anything else you'd like to know about your visit?"
            
            return {
                "message": response,
                "context": "confirmed",
                "appointment_details": {
                    "appointment_type": appt_info['name'],
                    "date": selected_slot['date'],
                    "time": selected_slot['start_time'],
                    "duration_minutes": appt_info['duration'],
                    "confirmation_code": booking['confirmation_code']
                },
                "suggestions": [
                    "What should I bring?",
                    "Where are you located?",
                    "What's your cancellation policy?"
                ]
            }
            
        except Exception as e:
            print(f"Error booking appointment: {e}")
            return {
                "message": "I encountered an issue while booking your appointment. Please call our office at +1-555-123-4567 to complete your booking.",
                "context": "error"
            }
    
    async def _handle_confirmation(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """Handle final confirmation"""
        # This is handled in patient_info collection
        pass
    
    async def _handle_faq(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """Handle FAQ questions"""
        # FAQ is handled in _check_faq method before context handlers
        return {
            "message": "How can I help you?",
            "context": "faq"
        }
    
    def _get_context_continuation(self, session: Dict[str, Any]) -> str:
        """Get appropriate continuation message based on context"""
        context = session.get("context")
        
        continuations = {
            "collecting_reason": "What brings you in today?",
            "collecting_time_preference": "When would you like your appointment?",
            "selecting_slot": "Which time slot works best for you?",
            "collecting_patient_info": "Could you provide your contact information?"
        }
        
        return continuations.get(context, "How can I help you?")
    
    async def _handle_faq_during_booking(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """Handle FAQ during booking process"""
        # FAQ is handled in _check_faq method before context handlers
        # This is a placeholder
        return {
            "message": "How can I help you with your appointment?",
            "context": session.get("context", "greeting")
        }