"""
Main scheduling agent with intelligent conversation flow
Handles context switching between scheduling and FAQ answering
Uses LLM for natural conversational responses
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from .prompts import SYSTEM_PROMPTS, RESPONSE_TEMPLATES
from .llm_service import LLMService
from rag.faq_rag import FAQRetriever
from api.calendly_integration import CalendlyClient
from tools.booking_tool import BookingTool


class SchedulingAgent:
    """
    Intelligent conversational agent for appointment scheduling
    Manages conversation flow, context switching, and booking logic
    """
    
    def __init__(self, use_llm: bool = True):
        self.appointment_types = {
            "consultation": {"duration": 30, "name": "General Consultation"},
            "followup": {"duration": 15, "name": "Follow-up"},
            "physical": {"duration": 45, "name": "Physical Exam"},
            "specialist": {"duration": 60, "name": "Specialist Consultation"}
        }
        
        # Initialize LLM service (will fail gracefully if API key not set)
        self.use_llm = use_llm
        try:
            self.llm_service = LLMService() if use_llm else None
        except Exception as e:
            print(f"⚠️ LLM service not available: {e}. Falling back to rule-based responses.")
            self.use_llm = False
            self.llm_service = None
        
        self.context_handlers = {
            "greeting": self._handle_greeting,
            "collecting_reason": self._handle_collecting_reason,
            "collecting_time_preference": self._handle_time_preference,
            "selecting_slot": self._handle_slot_selection,
            "confirming_slot": self._handle_slot_confirmation,
            "collecting_patient_info": self._handle_patient_info,
            "confirming": self._handle_confirmation,
            "faq": self._handle_faq,
            "faq_during_booking": self._handle_faq_during_booking,
            "checking_availability": self._handle_checking_availability,
            "checking_specific_date": self._handle_checking_specific_date,
            "waitlist": self._handle_waitlist,
            "cancelling_booking": self._handle_cancellation_confirmation,
            "rescheduling_booking": self._handle_rescheduling_booking
        }
    
    def get_system_prompt(self, session: Dict[str, Any], message: str = "") -> str:
        """
        Get the appropriate system prompt based on conversation context
        Defaults to smooth conversation for natural, flowing interactions
        
        Args:
            session: Current session data
            message: Current user message (optional, for detection)
        
        Returns:
            System prompt string to use
        """
        # Always use smooth conversation as default for natural, flowing conversations
        # This ensures all interactions are smooth and natural
        return SYSTEM_PROMPTS.get("smooth_conversation", SYSTEM_PROMPTS["main_agent"])
    
    async def _generate_llm_response(
        self,
        user_message: str,
        session: Dict[str, Any],
        context_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a conversational response using LLM
        
        Args:
            user_message: User's message
            session: Current session data
            context_data: Additional context for the LLM
        
        Returns:
            Generated response message
        """
        if not self.use_llm or not self.llm_service:
            return None  # Fallback to rule-based
        
        try:
            system_prompt = self.get_system_prompt(session, user_message)
            conversation_history = session.get("conversation_history", [])
            
            # Build context data
            if not context_data:
                context_data = {
                    "context": session.get("context", "greeting"),
                    "appointment_type": session.get("appointment_type"),
                    "available_slots": session.get("available_slots"),
                    "patient_info": session.get("patient_info", {})
                }
            
            response = await self.llm_service.generate_response(
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                user_message=user_message,
                context_data=context_data
            )
            
            return response
        except Exception as e:
            print(f"⚠️ LLM generation error: {e}")
            return None  # Fallback to rule-based
    
    async def process_message(
        self,
        message: str,
        session: Dict[str, Any],
        faq_retriever: FAQRetriever,
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """
        Main message processing logic with LLM-powered conversational responses
        
        Args:
            message: User's message
            session: Current session data
            faq_retriever: FAQ retrieval system
            calendly_client: Calendly API client
        
        Returns:
            Response dictionary with message and updated context (NO suggestions)
        """
        lower_msg = message.lower().strip()
        
        # Get system prompt (always smooth conversation by default)
        system_prompt = self.get_system_prompt(session, message)
        session["current_system_prompt"] = system_prompt
        
        # First, check if this is an FAQ question
        faq_response = await self._check_faq(message, faq_retriever)
        
        if faq_response:
            # Store previous context if we're in the middle of booking
            previous_context = session.get("context", "greeting")
            
            # If we're in the middle of booking, preserve all context
            if previous_context not in ["greeting", "faq", "confirmed", "error"]:
                session["previous_context"] = previous_context
                session["faq_answered"] = True
                
                # Use LLM to generate smooth transition
                llm_response = await self._generate_llm_response(
                    f"User asked: {message}. FAQ answer: {faq_response}. Now transition back to scheduling appointment. Context: {previous_context}",
                    session,
                    {"faq_answer": faq_response, "previous_context": previous_context}
                )
                
                if llm_response:
                    transition_msg = llm_response
                else:
                    # Fallback
                    continuation = self._get_context_continuation(session)
                    transition_msg = f"{faq_response}\n\nGreat question! Now, let's get back to scheduling your appointment. {continuation}"
                
                response = {
                    "message": transition_msg,
                    "context": previous_context,
                    "previous_context": previous_context
                }
                
                # Preserve slots if available
                if session.get("available_slots"):
                    response["available_slots"] = session["available_slots"]
                
                return response
            else:
                # Standalone FAQ - use LLM for natural response
                llm_response = await self._generate_llm_response(
                    f"User asked: {message}. FAQ answer: {faq_response}",
                    session,
                    {"faq_answer": faq_response}
                )
                
                if llm_response:
                    response_msg = llm_response
                else:
                    # Fallback
                    scheduling_intent = any(word in lower_msg for word in ['book', 'schedule', 'appointment', 'yes', 'sure', 'okay'])
                    if scheduling_intent:
                        response_msg = f"{faq_response}\n\nGreat! I'd be happy to help you schedule an appointment. What brings you in today?"
                        session["context"] = "collecting_reason"
                    else:
                        response_msg = f"{faq_response}\n\nIs there anything else I can help you with?"
                        session["context"] = "faq"
                
                return {
                    "message": response_msg,
                    "context": session.get("context", "faq")
                }
        
        # Check for cancellation intent if there's an existing booking
        appointment_details = session.get("appointment_details")
        booking_id = None
        if appointment_details:
            booking_id = appointment_details.get("booking_id")
        
        # Also check if there's a booking_id directly in session
        if not booking_id:
            booking_id = session.get("booking_id")
        
        # If there's a booking and user wants to cancel, handle cancellation
        if booking_id and self._is_cancellation_intent(lower_msg):
            return await self._handle_booking_cancellation(
                message=message,
                session=session,
                booking_id=booking_id,
                calendly_client=calendly_client
            )
        
        # If there's a booking and user wants to reschedule, handle rescheduling
        if booking_id and self._is_rescheduling_intent(lower_msg):
            return await self._handle_booking_rescheduling(
                message=message,
                session=session,
                booking_id=booking_id,
                calendly_client=calendly_client
            )
        
        # Process based on current context (handlers will use LLM)
        current_context = session.get("context", "greeting")
        handler = self.context_handlers.get(
            current_context,
            self._handle_greeting
        )
        
        return await handler(
            message=message,
            session=session,
            calendly_client=calendly_client,
            faq_retriever=faq_retriever
        )
    
    async def _check_faq(
        self,
        message: str,
        faq_retriever: FAQRetriever
    ) -> Optional[str]:
        """
        Check if message is an FAQ query using both keyword matching and semantic search
        
        Returns:
            FAQ answer if found, None otherwise
        """
        lower_msg = message.lower().strip()
        
        # Skip if message is clearly a scheduling response (short, time-related, etc.)
        # This helps avoid false positives
        scheduling_indicators = [
            'yes', 'no', 'ok', 'okay', 'sure', 'that works', 'sounds good',
            'morning', 'afternoon', 'tomorrow', 'today', 'next week',
            '9am', '10am', '2pm', '3pm', 'monday', 'tuesday', 'wednesday'
        ]
        
        # If message is very short and matches scheduling indicators, likely not FAQ
        if len(message.split()) <= 3 and any(indicator in lower_msg for indicator in scheduling_indicators):
            return None
        
        # Quick keyword check for common FAQs (fast path)
        faq_keywords = {
            'insurance': ['insurance', 'accept', 'coverage', 'blue cross', 'aetna', 'cigna', 'medicare', 'medicaid'],
            'location': ['location', 'address', 'where', 'directions', 'how to get'],
            'hours': ['hours', 'open', 'close', 'when open', 'business hours', 'what time'],
            'parking': ['parking', 'park', 'garage', 'validation'],
            'cancellation': ['cancel', 'cancellation', 'reschedule', 'change appointment'],
            'first_visit': ['first visit', 'new patient', 'what to bring', 'what do i bring', 'documents'],
            'contact': ['phone', 'call', 'contact', 'reach', 'number'],
            'payment': ['payment', 'pay', 'cost', 'price', 'billing', 'fee', 'charge']
        }
        
        # Check keywords first (fast)
        for category, keywords in faq_keywords.items():
            if any(keyword in lower_msg for keyword in keywords):
                answer = await faq_retriever.get_answer(category)
                if answer and len(answer) > 20:  # Ensure we got a real answer
                    return answer
        
        # If no keyword match but message looks like a question, try semantic search
        question_indicators = ['what', 'where', 'when', 'how', 'do you', 'can you', 'do they', 'is there']
        if any(indicator in lower_msg for indicator in question_indicators) and len(message.split()) > 2:
            # Try contextual search
            try:
                answer = await faq_retriever.get_contextual_answer(message)
                if answer and len(answer) > 30 and "don't have" not in answer.lower():
                    return answer
            except Exception as e:
                print(f"Error in contextual FAQ search: {e}")
                pass
        
        return None
    
    async def _handle_greeting(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle initial greeting with LLM-powered natural responses"""
        lower_msg = message.lower().strip()
        
        # Check for scheduling intent
        scheduling_keywords = ['appointment', 'schedule', 'book', 'see doctor', 'visit', 'checkup', 'need to see']
        if any(keyword in lower_msg for keyword in scheduling_keywords):
            session["context"] = "collecting_reason"
            # Use LLM for natural response
            llm_response = await self._generate_llm_response(
                f"User wants to schedule an appointment. Greet them warmly and ask what brings them in today.",
                session
            )
            return {
                "message": llm_response or RESPONSE_TEMPLATES["ask_reason"],
                "context": "collecting_reason"
            }
        
        # Check for availability check intent
        availability_keywords = ['check availability', 'check available', 'show availability', 'available slots', 'available times', 'what times', 'when available']
        if any(keyword in lower_msg for keyword in availability_keywords):
            return await self._handle_check_availability(session, calendly_client, faq_retriever)
        
        # Use LLM for natural greeting response
        llm_response = await self._generate_llm_response(
            f"User said: {message}. Greet them warmly and offer to help with scheduling or answering questions.",
            session
        )
        
        return {
            "message": llm_response or RESPONSE_TEMPLATES["greeting"],
            "context": "greeting"
        }
    
    async def _handle_collecting_reason(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Determine appointment type and use LLM for natural response"""
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
        session["appointment_type"] = appointment_type
        
        # Use LLM to generate natural response
        llm_response = await self._generate_llm_response(
            f"User said: {message}. Recommend a {appt_info['name']} ({appt_info['duration']} minutes) appointment. Then naturally ask when they'd like to come in, asking about morning or afternoon preference.",
            session,
            {"appointment_type": appointment_type, "appointment_name": appt_info['name'], "duration": appt_info['duration']}
        )
        
        if llm_response:
            response_msg = llm_response
        else:
            # Fallback
            response_msg = f"I recommend a {appt_info['name']} ({appt_info['duration']} minutes) where the doctor can assess your symptoms. When would you like to come in? Do you have a preference for morning or afternoon appointments?"
        
        return {
            "message": response_msg,
            "context": "collecting_time_preference",
            "appointment_type": appointment_type
        }
    
    async def _handle_time_preference(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
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
                    
                }
            
            # Format slots for display
            slot_list = "\n".join([
                f"• {slot['date']} at {slot['start_time']}"
                for slot in available_slots[:5]
            ])
            
            # Generate explanation for slot recommendations
            time_pref = "afternoon" if is_afternoon else "morning" if is_morning else ""
            date_pref = "this week" if is_asap else ""
            
            # Build explanation using LLM for natural reasoning
            explanation_prompt = f"User requested {message}. I found {len(available_slots)} available slots"
            if time_pref:
                explanation_prompt += f" for {time_pref} appointments"
            if date_pref:
                explanation_prompt += f" {date_pref}"
            explanation_prompt += ". Explain why these slots are good options in a natural, friendly way (1-2 sentences)."
            
            explanation = await self._generate_llm_response(
                explanation_prompt,
                session,
                {"time_preference": time_pref, "slots_count": len(available_slots)}
            )
            
            if explanation:
                response = f"{explanation}\n\nHere are the available options:\n\n{slot_list}\n\nWhich works best for you?"
            else:
                # Fallback with built-in explanation
                if time_pref:
                    response = f"I found these {time_pref} options because you mentioned preferring {time_pref} appointments, and these are the earliest available this week:\n\n{slot_list}\n\nWhich works best for you?"
                else:
                    response = f"Great! I found these available times that match your preferences:\n\n{slot_list}\n\nWhich works best for you?"
            
            # Store slots in session
            session["available_slots"] = available_slots
            
            # Prepare structured slot data for frontend (clickable buttons)
            structured_slots = []
            for slot in available_slots[:5]:
                structured_slots.append({
                    "date": slot.get("date", ""),
                    "full_date": slot.get("full_date", ""),
                    "start_time": slot.get("start_time", ""),
                    "end_time": slot.get("end_time", ""),
                    "raw_time": slot.get("raw_time", slot.get("start_time", "")),
                    "display_text": f"{slot.get('date', '')} at {slot.get('start_time', '')}",
                    "available": True
                })
            
            return {
                "message": response,
                "context": "selecting_slot",
                "available_slots": structured_slots  # Structured data for UI
            }
            
        except Exception as e:
            print(f"Error fetching availability: {e}")
            # Improved error message with helpful options
            error_msg = await self._generate_llm_response(
                "I encountered an error accessing the schedule. Apologize warmly and offer helpful alternatives: call back option, try again, or check specific date.",
                session
            )
            return {
                "message": error_msg or "I'm having trouble accessing our schedule right now. Would you like me to:\n\n• Have someone from our office call you back\n• Try again in a moment\n• Check availability for a specific date\n\nWhat would work best for you?",
                "context": "error"
            }
    
    async def _handle_slot_selection(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle slot selection - supports both text input and structured slot selection"""
        # Parse selected time
        lower_msg = message.lower()
        
        # Check if user is rejecting all slots
        if self._is_rejection(lower_msg) or any(phrase in lower_msg for phrase in ["none", "don't work", "doesn't work", "not work", "different", "other"]):
            return await self._handle_slot_rejection(session, calendly_client, faq_retriever)
        
        # Try to match with available slots
        available_slots = session.get("available_slots", [])
        selected_slot = None
        
        # Extract date and time from user's message for better matching
        user_date_parts = []
        user_time = None
        
        # Try to extract date patterns (e.g., "Wednesday, December 17", "Dec 17", "12/17", etc.)
        date_patterns = [
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+(january|february|march|april|may|june|july|august|september|october|november|december)[,\s]+(\d{1,2})',  # "Wednesday, December 17"
            r'(january|february|march|april|may|june|july|august|september|october|november|december)[,\s]+(\d{1,2})',  # "December 17"
            r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?',  # "12/17" or "12/17/2024"
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, lower_msg, re.IGNORECASE)
            if date_match:
                user_date_parts = list(date_match.groups())
                break
        
        # Extract time pattern (e.g., "12:00 PM", "12 PM", "12:00pm")
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)', lower_msg, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3).upper()
            # Normalize to 24-hour format for comparison
            if period == "PM" and hour != 12:
                hour += 12
            elif period == "AM" and hour == 12:
                hour = 0
            user_time = f"{hour:02d}:{minute:02d}"
        
        # First, try exact match with structured slot data (from clickable buttons)
        # Prioritize full display text match
        for slot in available_slots:
            slot_display = slot.get("display_text", "").lower()
            # Exact display text match is highest priority
            if slot_display and slot_display in lower_msg:
                selected_slot = slot
                break
        
        # If no exact display match, try matching date + time together
        if not selected_slot and user_date_parts and user_time:
            for slot in available_slots:
                slot_date = slot.get("date", "").lower()
                slot_full_date = slot.get("full_date", "")  # YYYY-MM-DD format
                slot_raw_time = slot.get("raw_time", "")  # HH:MM format
                slot_time = slot.get("start_time", "").lower()
                
                # Check if date matches (using both formatted date and full_date)
                date_matches = False
                if slot_date:
                    # Check if user's date parts appear in slot_date
                    date_match_count = sum(1 for part in user_date_parts if part and part.lower() in slot_date)
                    if date_match_count >= 2:  # At least 2 parts match (e.g., "december" and "17")
                        date_matches = True
                
                # Check if time matches
                time_matches = False
                if slot_raw_time and user_time:
                    # Compare raw times (HH:MM format)
                    time_matches = (slot_raw_time == user_time)
                elif slot_time and user_time:
                    # Fallback: check if time appears in formatted time
                    hour_str = str(int(user_time.split(":")[0]))
                    period = "pm" if int(user_time.split(":")[0]) >= 12 else "am"
                    if hour_str in slot_time and period in slot_time:
                        time_matches = True
                
                # Both date and time must match
                if date_matches and time_matches:
                    selected_slot = slot
                    break
        
        # If still no match, try partial matching (less strict)
        if not selected_slot:
            for slot in available_slots:
                slot_display = slot.get("display_text", "").lower()
                slot_time = slot.get("start_time", "").lower()
                slot_date = slot.get("date", "").lower()
                
                # Check if message matches any part of the slot (but require both date and time to be present)
                has_date_match = slot_date and any(part in slot_date for part in user_date_parts if part)
                has_time_match = slot_time and user_time and (
                    user_time.split(":")[0] in slot_time or 
                    slot_time in lower_msg
                )
                
                # If we have both date and time in user message, require both to match
                if user_date_parts and user_time:
                    if has_date_match and has_time_match:
                        selected_slot = slot
                        break
                # Otherwise, fall back to any match
                elif (slot_time in lower_msg or 
                      slot_date in lower_msg or 
                      slot_display in lower_msg or
                      lower_msg in slot_display):
                    selected_slot = slot
                    break
        
        # If no match, try to match just time pattern (last resort)
        if not selected_slot and available_slots and user_time:
            for slot in available_slots:
                slot_raw_time = slot.get("raw_time", "")
                slot_time = slot.get("start_time", "").lower()
                if slot_raw_time == user_time or (slot_time and user_time.split(":")[0] in slot_time):
                    selected_slot = slot
                    break
        
        if not selected_slot:
            # Show available slots again with clearer format
            slot_list = "\n".join([
                f"• {slot.get('display_text', slot.get('date', '') + ' at ' + slot.get('start_time', ''))}"
                for slot in available_slots[:5]
            ])
            return {
                "message": f"I didn't catch which time you'd prefer. Here are the available options again:\n\n{slot_list}\n\nCould you specify one of these times, or let me know if none of these work for you?",
                "context": "selecting_slot",
                "available_slots": available_slots  # Preserve structured slots
            }
        
        # Check if we're rescheduling
        rescheduling_info = session.get("rescheduling")
        if rescheduling_info:
            # Handle rescheduling - cancel old booking and create new one
            return await self._complete_rescheduling(
                selected_slot=selected_slot,
                session=session,
                calendly_client=calendly_client
            )
        
        # Store selection
        session["selected_slot"] = selected_slot
        
        # Get display text for confirmation
        display_text = selected_slot.get("display_text", 
            f"{selected_slot.get('date', '')} at {selected_slot.get('start_time', '')}")
        
        appt_name = self.appointment_types[session['appointment_type']]['name']
        appt_duration = self.appointment_types[session['appointment_type']]['duration']
        
        # Add confirmation step before collecting info
        confirmation_msg = f"Perfect! Just to confirm: {display_text} for a {appt_name} ({appt_duration} minutes). Is this correct?"
        
        # Use LLM for natural confirmation
        llm_confirmation = await self._generate_llm_response(
            f"User selected {display_text} for {appt_name}. Ask for confirmation in a warm, natural way before collecting their information.",
            session,
            {"selected_slot": display_text, "appointment_type": appt_name, "duration": appt_duration}
        )
        
        if llm_confirmation:
            confirmation_msg = llm_confirmation
        
        # Store that we're waiting for confirmation
        session["awaiting_confirmation"] = True
        session["confirmation_asked"] = False  # Reset confirmation asked flag
        
        return {
            "message": confirmation_msg,
            "context": "confirming_slot",
            "available_slots": None
        }
    
    async def _handle_patient_info(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Collect and validate patient information - handles multiple formats"""
        
        # Get existing patient info from session (preserve what was already collected)
        patient_info = session.get("patient_info", {})
        
        # Debug: Log what we already have
        print(f"📋 Current patient_info in session: {patient_info}")
        
        # Check if user is saying "done" or indicating completion
        lower_msg = message.lower().strip()
        completion_signals = ['done', 'that\'s all', 'that\'s it', 'finished', 'complete', 'all set', 'ready', 'ok', 'okay', 'yes', 'sure', 'go ahead', 'proceed']
        is_completion = any(signal in lower_msg for signal in completion_signals)
        
        if is_completion:
            print(f"✅ User sent completion signal: '{message}'")
        
        # If user says "done" and we have all info, proceed to booking
        if is_completion:
            required_fields = ["name", "email", "phone"]
            missing_fields = [f for f in required_fields if f not in patient_info or not patient_info[f]]
            
            if not missing_fields:
                # All info collected, proceed to book
                selected_slot = session.get("selected_slot")
                if selected_slot:
                    appointment_type = session.get("appointment_type", "consultation")
                    
                    try:
                        # Book appointment
                        api_start_time = selected_slot.get("raw_time")
                        if not api_start_time:
                            time_str = selected_slot["start_time"]
                            try:
                                if "AM" in time_str.upper() or "PM" in time_str.upper():
                                    time_obj = datetime.strptime(time_str.upper().strip(), "%I:%M %p")
                                    api_start_time = time_obj.strftime("%H:%M")
                                else:
                                    api_start_time = time_str
                            except:
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
                        
                        # Return booking response (same as below)
                        appt_info = self.appointment_types[appointment_type]
                        scheduling_link = booking.get('scheduling_link')
                        booking_status = booking.get('status', 'confirmed')
                        booking_id = booking.get('booking_id', '')
                        
                        response = f"Perfect! I've got everything I need. "
                        
                        if booking_status == 'pending':
                            response += f"I've prepared your appointment booking. "
                            if scheduling_link:
                                response += f"Please click the link below to complete your booking in Calendly. Your information is already pre-filled!\n\n"
                        else:
                            response += f"Your appointment is confirmed! "
                        
                        response += f"\n📋 Appointment Details:\n"
                        response += f"• Type: {appt_info['name']} ({appt_info['duration']} minutes)\n"
                        response += f"• Date: {selected_slot.get('date', '')}\n"
                        response += f"• Time: {selected_slot.get('start_time', '')}\n"
                        response += f"• Patient: {patient_info['name']}\n"
                        response += f"• Email: {patient_info['email']}\n"
                        if patient_info.get('phone'):
                            response += f"• Phone: {patient_info['phone']}\n"
                        
                        if booking.get('confirmation_code'):
                            response += f"• Confirmation Code: {booking['confirmation_code']}\n"
                        
                        if booking_status == 'pending' and scheduling_link:
                            response += f"\n🔗 Complete your booking: {scheduling_link}\n\n"
                            response += f"Once you complete the booking, you'll receive a confirmation email at {patient_info['email']}."
                        else:
                            response += f"\nYou'll receive a confirmation email at {patient_info['email']} with all the details.\n\n"
                        
                        return {
                            "message": response,
                            "context": "confirmed",
                            "appointment_details": {
                                "booking_id": booking_id,
                                "confirmation_code": booking.get('confirmation_code', ''),
                                "date": selected_slot.get('date', ''),
                                "time": selected_slot.get('start_time', ''),
                                "appointment_type": appt_info['name'],
                                "scheduling_link": scheduling_link,
                                "status": booking_status,
                                "patient_name": patient_info.get('name'),
                                "patient_email": patient_info.get('email'),
                                "patient_phone": patient_info.get('phone'),
                                "full_date": selected_slot.get('full_date', '')
                            }
                        }
                    except Exception as e:
                        error_msg = f"I encountered an error while booking your appointment: {str(e)}"
                        print(f"❌ Booking error: {e}")
                        return {
                            "message": error_msg,
                            "context": "error"
                        }
        
        # Extract information with improved patterns (only update if not already collected)
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message, re.IGNORECASE)
        # Improved phone pattern - handles various formats
        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', message)
        
        # Only update if not already in session (preserve existing data)
        if email_match:
            extracted_email = email_match.group(0).lower().strip()
            if not patient_info.get("email"):
                patient_info["email"] = extracted_email
                print(f"📧 Extracted and saved email: {extracted_email}")
            else:
                print(f"📧 Email already in session: {patient_info.get('email')}, ignoring new: {extracted_email}")
        
        if phone_match:
            # Clean phone number
            phone = phone_match.group(0).strip()
            # Remove common separators but keep format
            phone = re.sub(r'[^\d+]', '', phone)
            if not phone.startswith('+') and len(phone) == 10:
                phone = f"+1{phone}"  # Add US country code if missing
            
            if not patient_info.get("phone"):
                patient_info["phone"] = phone
                print(f"📞 Extracted and saved phone: {phone}")
            else:
                print(f"📞 Phone already in session: {patient_info.get('phone')}, ignoring new: {phone}")
        
        # Extract name (everything that's not email or phone)
        name_text = message
        if email_match:
            name_text = name_text.replace(email_match.group(0), "")
        if phone_match:
            name_text = name_text.replace(phone_match.group(0), "")
        
        # Remove common prefixes/suffixes
        name_text = re.sub(r'^(my name is|i am|this is|name:|i\'m|im)\s*', '', name_text, flags=re.IGNORECASE)
        name_text = re.sub(r'\s*(here|thanks|thank you)', '', name_text, flags=re.IGNORECASE)
        
        name = name_text.strip()
        if name and not patient_info.get("name"):
            # Clean name - keep letters, spaces, hyphens, apostrophes
            name = re.sub(r'[^a-zA-Z\s\-\']', '', name).strip()
            # Only accept if it looks like a real name (at least 2 characters, has letters)
            if name and len(name) >= 2 and re.search(r'[a-zA-Z]', name):
                # Capitalize properly
                name_parts = name.split()
                name = ' '.join([part.capitalize() for part in name_parts])
                patient_info["name"] = name
        
        session["patient_info"] = patient_info
        
        # Check if we have all required info FIRST (before checking completion signals)
        required_fields = ["name", "email", "phone"]
        missing_fields = [f for f in required_fields if f not in patient_info or not patient_info[f]]
        
        # If all info is collected, proceed to booking automatically
        if not missing_fields:
            # All info collected! Proceed to booking
            selected_slot = session.get("selected_slot")
            if selected_slot:
                # Check if user explicitly said to proceed (confirm, done, etc.)
                completion_keywords = ['confirm', 'done', 'ok', 'okay', 'yes', 'sure', 'go ahead', 'proceed', 'finalize', 'complete', 'book', 'schedule', 'finalize', 'all set']
                user_wants_to_proceed = is_completion or any(keyword in lower_msg for keyword in completion_keywords)
                
                # Also check if user just provided the last piece of info (email, phone, or name)
                just_provided_info = email_match or phone_match or (name and len(name.strip()) > 1)
                
                # Proceed if user said confirm/done OR if they just provided the last piece of info
                if user_wants_to_proceed or just_provided_info:
                    # Proceed to booking
                    appointment_type = session.get("appointment_type", "consultation")
                    
                    try:
                        # Book appointment
                        api_start_time = selected_slot.get("raw_time")
                        if not api_start_time:
                            time_str = selected_slot["start_time"]
                            try:
                                if "AM" in time_str.upper() or "PM" in time_str.upper():
                                    time_obj = datetime.strptime(time_str.upper().strip(), "%I:%M %p")
                                    api_start_time = time_obj.strftime("%H:%M")
                                else:
                                    api_start_time = time_str
                            except:
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
                        scheduling_link = booking.get('scheduling_link')
                        booking_status = booking.get('status', 'confirmed')
                        booking_id = booking.get('booking_id', '')
                        
                        response = f"Perfect! I've got everything I need. "
                        
                        if booking_status == 'pending':
                            response += f"I've prepared your appointment booking. "
                            if scheduling_link:
                                response += f"Please click the link below to complete your booking in Calendly. Your information is already pre-filled!\n\n"
                        else:
                            response += f"Your appointment is confirmed! "
                        
                        response += f"\n📋 Appointment Details:\n"
                        response += f"• Type: {appt_info['name']} ({appt_info['duration']} minutes)\n"
                        response += f"• Date: {selected_slot.get('date', '')}\n"
                        response += f"• Time: {selected_slot.get('start_time', '')}\n"
                        response += f"• Patient: {patient_info['name']}\n"
                        response += f"• Email: {patient_info['email']}\n"
                        if patient_info.get('phone'):
                            response += f"• Phone: {patient_info['phone']}\n"
                        
                        if booking.get('confirmation_code'):
                            response += f"• Confirmation Code: {booking['confirmation_code']}\n"
                        
                        if booking_status == 'pending' and scheduling_link:
                            response += f"\n🔗 Complete your booking: {scheduling_link}\n\n"
                            response += f"Once you complete the booking, you'll receive a confirmation email at {patient_info['email']}."
                        else:
                            response += f"\nYou'll receive a confirmation email at {patient_info['email']} with all the details.\n\n"
                        
                        return {
                            "message": response,
                            "context": "confirmed",
                            "appointment_details": {
                                "booking_id": booking_id,
                                "confirmation_code": booking.get('confirmation_code', ''),
                                "date": selected_slot.get('date', ''),
                                "time": selected_slot.get('start_time', ''),
                                "appointment_type": appt_info['name'],
                                "scheduling_link": scheduling_link,
                                "status": booking_status,
                                "patient_name": patient_info.get('name'),
                                "patient_email": patient_info.get('email'),
                                "patient_phone": patient_info.get('phone'),
                                "full_date": selected_slot.get('full_date', '')
                            }
                        }
                    except Exception as e:
                        error_msg = f"I encountered an error while booking your appointment: {str(e)}"
                        print(f"❌ Booking error: {e}")
                        import traceback
                        traceback.print_exc()
                        return {
                            "message": error_msg,
                            "context": "error"
                        }
        
        # Check if we're in rescheduling mode
        rescheduling_info = session.get("rescheduling")
        if rescheduling_info and rescheduling_info.get("selected_slot"):
            # We have a selected slot and are collecting info for rescheduling
            # Check if we have all required info
            required_fields = ["name", "email", "phone"]
            missing_fields = [f for f in required_fields if f not in patient_info or not patient_info[f]]
            
            if missing_fields:
                # Still missing info
                if len(missing_fields) == 3:
                    missing_str = "your name, phone number, and email address"
                elif len(missing_fields) == 2:
                    missing_str = "your " + " and ".join(missing_fields)
                else:
                    missing_str = f"your {missing_fields[0]}"
                
                llm_msg = await self._generate_llm_response(
                    f"User provided some info for rescheduling but still missing {missing_str}. Ask for remaining information.",
                    session,
                    {"missing_fields": missing_fields}
                )
                
                return {
                    "message": llm_msg or f"I still need {missing_str} to complete the rescheduling.",
                    "context": "rescheduling_booking",
                    "appointment_details": session.get("appointment_details")
                }
            
            # All info collected - complete rescheduling
            selected_slot = rescheduling_info.get("selected_slot")
            return await self._complete_rescheduling(
                selected_slot=selected_slot,
                session=session,
                calendly_client=calendly_client
            )
        
        # Still missing some info
        if missing_fields:
            # Show what we already have
            collected_info = []
            if patient_info.get("name"):
                collected_info.append(f"✓ Name: {patient_info['name']}")
            if patient_info.get("email"):
                collected_info.append(f"✓ Email: {patient_info['email']}")
            if patient_info.get("phone"):
                collected_info.append(f"✓ Phone: {patient_info['phone']}")
            
            # Create friendly message
            if len(missing_fields) == 3:
                missing_str = "your name, phone number, and email address"
            elif len(missing_fields) == 2:
                missing_str = "your " + " and ".join(missing_fields)
            else:
                missing_str = f"your {missing_fields[0]}"
            
            # Build message acknowledging what we have
            context_for_llm = f"User has already provided: {', '.join([f.replace('✓ ', '') for f in collected_info]) if collected_info else 'nothing'}. Still missing: {missing_str}."
            
            # Use LLM for natural message that acknowledges what we have
            llm_msg = await self._generate_llm_response(
                f"{context_for_llm} Acknowledge what information we already have, then ask for the remaining information in a warm, helpful way.",
                session,
                {"missing_fields": missing_fields, "collected_info": collected_info, "patient_info": patient_info}
            )
            
            # Build fallback message
            if collected_info:
                fallback_msg = f"Great! I have:\n" + "\n".join(collected_info) + f"\n\nI still need {missing_str} to complete your booking. You can provide it now, or let me know if you'd like to proceed with what we have."
            else:
                fallback_msg = f"I need {missing_str} to complete your booking. You can provide them all at once, or one at a time - whatever's easiest for you."
            
            return {
                "message": llm_msg or fallback_msg,
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
            
            # Check if this is a pending booking (with scheduling link) or confirmed
            scheduling_link = booking.get('scheduling_link')
            booking_status = booking.get('status', 'confirmed')
            booking_id = booking.get('booking_id', '')
            
            # For pending bookings, try to complete them immediately if possible
            # Note: Calendly API doesn't support direct event creation, so we mark as ready
            if scheduling_link and booking_status == 'pending':
                # Mark booking as ready in our system (even though it's pending in Calendly)
                # The webhook will confirm it later when user clicks the link
                response = f"Perfect! Your appointment is ready! 🎉\n\n"
                response += f"✅ Appointment Details:\n"
                response += f"• Date & Time: {selected_slot['date']} at {selected_slot['start_time']}\n"
                response += f"• Type: {appt_info['name']}\n"
                response += f"• Duration: {appt_info['duration']} minutes\n"
                response += f"• Confirmation Code: {booking['confirmation_code']}\n"
                response += f"• Patient: {patient_info['name']}\n"
                response += f"• Email: {patient_info['email']}\n\n"
                response += f"📅 Finalize Your Booking:\n"
                response += f"Your information is already pre-filled! Just click the link below to complete your booking in Calendly:\n\n"
                response += f"{scheduling_link}\n\n"
                response += f"Once you complete the booking, you'll receive a confirmation email at {patient_info['email']}.\n"
                response += f"Your appointment will be automatically confirmed in our system.\n\n"
                
                # Update booking status to "ready" in our system (pending in Calendly)
                booking_status = "ready"  # Custom status meaning "ready to finalize"
            else:
                response = f"Perfect! All set! 🎉\n\n"
                response += f"Your appointment is confirmed:\n"
                response += f"• Date & Time: {selected_slot['date']} at {selected_slot['start_time']}\n"
                response += f"• Type: {appt_info['name']}\n"
                response += f"• Duration: {appt_info['duration']} minutes\n"
                response += f"• Confirmation Code: {booking['confirmation_code']}\n\n"
                if scheduling_link:
                    response += f"📅 View/Manage Your Appointment:\n{scheduling_link}\n\n"
                response += f"You'll receive a confirmation email at {patient_info['email']} with all the details.\n\n"
            
            response += "Is there anything else you'd like to know about your visit?"
            
            # Build appointment_details with all relevant information
            appointment_details = {
                "booking_id": booking.get('booking_id'),
                "appointment_type": appt_info['name'],
                "date": selected_slot['date'],
                "time": selected_slot['start_time'],
                "duration_minutes": appt_info['duration'],
                "confirmation_code": booking['confirmation_code'],
                "status": booking_status,  # "ready" for pending bookings, "confirmed" for completed
                "patient_name": patient_info.get('name'),
                "patient_email": patient_info.get('email'),
                "patient_phone": patient_info.get('phone'),
                "full_date": selected_slot.get('full_date', '')  # Include for timezone conversion
            }
            
            # Add scheduling link if available
            if scheduling_link:
                appointment_details["scheduling_link"] = scheduling_link
            
            return {
                "message": response,
                "context": "confirmed",
                "appointment_details": appointment_details,
                "suggestions": [
                    "What should I bring?",
                    "Where are you located?",
                    "What's your cancellation policy?"
                ]
            }
            
        except Exception as e:
            print(f"Error booking appointment: {e}")
            # Improved error message with helpful guidance
            error_msg = await self._generate_llm_response(
                "I encountered an issue while booking the appointment. Apologize warmly, explain the situation, and offer helpful alternatives: call office, try different time, or waitlist.",
                session
            )
            return {
                "message": error_msg or "I'm sorry, but I encountered an issue while booking your appointment. This sometimes happens if the time slot was just taken. Would you like me to:\n\n• Show you other available times\n• Have someone from our office call you at +1-555-123-4567 to complete the booking\n• Put you on a waitlist for this time slot\n\nWhat would work best for you?",
                "context": "error"
            }
    
    async def _handle_slot_confirmation(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle slot confirmation before collecting patient info"""
        lower_msg = message.lower().strip()
        
        # Check if user is providing patient info (email, phone, name) - skip confirmation
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message, re.IGNORECASE)
        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', message)
        
        # If user provides email or phone, they're giving patient info - proceed to collection
        if email_match or phone_match or (len(message.split()) <= 3 and any(char.isdigit() for char in message)):
            session["awaiting_confirmation"] = False
            # Switch to patient info collection
            return await self._handle_patient_info(message, session, calendly_client, faq_retriever)
        
        # Check if user is providing a date/time - might be selecting different slot
        # Extract date and time from user's message for better matching
        user_date_parts = []
        user_time = None
        
        # Try to extract date patterns
        date_patterns = [
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+(january|february|march|april|may|june|july|august|september|october|november|december)[,\s]+(\d{1,2})',  # "Wednesday, December 17"
            r'(january|february|march|april|may|june|july|august|september|october|november|december)[,\s]+(\d{1,2})',  # "December 17"
            r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?',  # "12/17" or "12/17/2024"
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, lower_msg, re.IGNORECASE)
            if date_match:
                user_date_parts = list(date_match.groups())
                break
        
        # Extract time pattern
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)', lower_msg, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3).upper()
            # Normalize to 24-hour format for comparison
            if period == "PM" and hour != 12:
                hour += 12
            elif period == "AM" and hour == 12:
                hour = 0
            user_time = f"{hour:02d}:{minute:02d}"
        
        # If user provided both date and time, try to match with available slots
        if user_date_parts and user_time:
            available_slots = session.get("available_slots", [])
            matched_slot = None
            
            for slot in available_slots:
                slot_date = slot.get("date", "").lower()
                slot_raw_time = slot.get("raw_time", "")  # HH:MM format
                slot_time = slot.get("start_time", "").lower()
                
                # Check if date matches
                date_matches = False
                if slot_date:
                    date_match_count = sum(1 for part in user_date_parts if part and part.lower() in slot_date)
                    if date_match_count >= 2:  # At least 2 parts match
                        date_matches = True
                
                # Check if time matches
                time_matches = False
                if slot_raw_time and user_time:
                    time_matches = (slot_raw_time == user_time)
                elif slot_time and user_time:
                    hour_str = str(int(user_time.split(":")[0]))
                    period = "pm" if int(user_time.split(":")[0]) >= 12 else "am"
                    if hour_str in slot_time and period in slot_time:
                        time_matches = True
                
                # Both date and time must match
                if date_matches and time_matches:
                    matched_slot = slot
                    break
            
            if matched_slot:
                # User selected a different slot
                session["selected_slot"] = matched_slot
                session["awaiting_confirmation"] = False
                display_text = matched_slot.get("display_text", f"{matched_slot.get('date', '')} at {matched_slot.get('start_time', '')}")
                appt_name = self.appointment_types[session['appointment_type']]['name']
                return {
                    "message": f"Perfect! {display_text} for a {appt_name}. Before I confirm, I'll need a few details:\n\n• Your full name\n• Best phone number to reach you\n• Email address for confirmation\n\nYou can provide these all at once, or one at a time - whatever's easiest for you.",
                    "context": "collecting_patient_info",
                    "available_slots": None
                }
        # If only time provided (no date), try to match by time only (less reliable)
        elif user_time and not user_date_parts:
            time_pattern = re.search(r'\d{1,2}:?\d{0,2}\s*(am|pm)', lower_msg, re.IGNORECASE)
            if time_pattern:
                # User might want a different time - check if it matches available slots
                available_slots = session.get("available_slots", [])
                for slot in available_slots:
                    slot_raw_time = slot.get("raw_time", "")
                    slot_time = slot.get("start_time", "").lower()
                    if slot_raw_time == user_time or (slot_time and time_pattern.group(0).lower() in slot_time):
                        # User selected a different slot (by time only)
                        session["selected_slot"] = slot
                        session["awaiting_confirmation"] = False
                        display_text = slot.get("display_text", f"{slot.get('date', '')} at {slot.get('start_time', '')}")
                        appt_name = self.appointment_types[session['appointment_type']]['name']
                        return {
                            "message": f"Perfect! {display_text} for a {appt_name}. Before I confirm, I'll need a few details:\n\n• Your full name\n• Best phone number to reach you\n• Email address for confirmation\n\nYou can provide these all at once, or one at a time - whatever's easiest for you.",
                            "context": "collecting_patient_info",
                            "available_slots": None
                        }
        
        # Check if user confirms
        confirm_keywords = ['yes', 'correct', 'right', 'that works', 'sounds good', 'ok', 'okay', 'sure', 'yep', 'yeah']
        reject_keywords = ['no', 'wrong', 'incorrect', 'change', 'different', 'not', "don't"]
        
        if any(keyword in lower_msg for keyword in confirm_keywords):
            # User confirmed, proceed to collect patient info
            session["awaiting_confirmation"] = False
            selected_slot = session.get("selected_slot")
            display_text = selected_slot.get("display_text", 
                f"{selected_slot.get('date', '')} at {selected_slot.get('start_time', '')}")
            appt_name = self.appointment_types[session['appointment_type']]['name']
            
            # Use LLM for natural transition
            llm_response = await self._generate_llm_response(
                f"User confirmed {display_text} for {appt_name}. Now ask for their contact information (name, phone, email) in a warm, natural way.",
                session
            )
            
            if llm_response:
                response_msg = llm_response
            else:
                response_msg = f"Excellent! {display_text} for a {appt_name}.\n\nBefore I confirm, I'll need a few details:\n"
                response_msg += "• Your full name\n"
                response_msg += "• Best phone number to reach you\n"
                response_msg += "• Email address for confirmation\n\n"
                response_msg += "You can provide these all at once, or one at a time - whatever's easiest for you."
            
            return {
                "message": response_msg,
                "context": "collecting_patient_info",
                "available_slots": None
            }
        elif any(keyword in lower_msg for keyword in reject_keywords):
            # User wants to change selection
            session["awaiting_confirmation"] = False
            session["selected_slot"] = None
            
            # Use LLM for natural response
            llm_response = await self._generate_llm_response(
                "User wants to change their slot selection. Acknowledge warmly and ask which time they'd prefer instead.",
                session
            )
            
            return {
                "message": llm_response or "No problem at all! Which time would you prefer instead?",
                "context": "selecting_slot",
                "available_slots": session.get("available_slots", [])
            }
        else:
            # Check if message looks like patient info even if regex didn't catch it
            # Look for email pattern (@), phone pattern (digits), or short numeric strings
            has_email_pattern = '@' in message or '.com' in message.lower() or '.net' in message.lower() or '.org' in message.lower()
            has_phone_pattern = len([c for c in message if c.isdigit()]) >= 7  # At least 7 digits
            is_short_numeric = len(message.strip()) <= 15 and any(char.isdigit() for char in message) and len([c for c in message if c.isdigit()]) >= 7
            
            if has_email_pattern or has_phone_pattern or is_short_numeric:
                # User is providing patient info - skip confirmation and collect info
                session["awaiting_confirmation"] = False
                return await self._handle_patient_info(message, session, calendly_client, faq_retriever)
            
            # If we've already asked for confirmation once, don't repeat - assume they're confirming
            # and proceed to collect patient info
            if session.get("awaiting_confirmation", False) and session.get("confirmation_asked", False):
                session["awaiting_confirmation"] = False
                session["confirmation_asked"] = False
                # Assume confirmation and proceed to collect info
                selected_slot = session.get("selected_slot")
                display_text = selected_slot.get("display_text", 
                    f"{selected_slot.get('date', '')} at {selected_slot.get('start_time', '')}")
                appt_name = self.appointment_types[session['appointment_type']]['name']
                
                # Try to extract any info from message first
                return await self._handle_patient_info(message, session, calendly_client, faq_retriever)
            
            # Mark that we've asked for confirmation
            session["confirmation_asked"] = True
            
            # First time asking - ask for clarification
            return {
                "message": "I want to make sure I have this right. Is this time slot correct, or would you like to choose a different one?",
                "context": "confirming_slot"
            }
    
    async def _handle_confirmation(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle final confirmation after booking"""
        # This is handled in patient_info collection
        pass
    
    async def _handle_faq(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle FAQ questions"""
        # FAQ is handled in _check_faq method before context handlers
        # This handler is called if we're already in FAQ context
        lower_msg = message.lower()
        
        # Check for availability check intent
        availability_keywords = ['check availability', 'check available', 'show availability', 'available slots', 'available times', 'what times', 'when available']
        if any(keyword in lower_msg for keyword in availability_keywords):
            return await self._handle_check_availability(session, calendly_client, faq_retriever)
        
        # Check if user wants to schedule after FAQ
        scheduling_keywords = ['appointment', 'schedule', 'book', 'see doctor', 'visit', 'checkup', 'yes', 'sure', 'okay', 'ok']
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
        
        return {
            "message": "How can I help you?",
            "context": "faq",
            
        }
    
    def _is_rejection(self, message: str) -> bool:
        """Check if message is a rejection/negative response"""
        message = message.strip()
        message_words = message.split()
        lower_msg = message.lower()
        
        # Single word rejections
        if len(message_words) == 1 and lower_msg in ["no", "not", "none", "nope", "nah"]:
            return True
        
        # Two word rejections
        if len(message_words) <= 2:
            if lower_msg in ["no thanks", "not really", "not yet", "not now", "no way", "not interested"]:
                return True
            if lower_msg.startswith("not ") and len(message_words) == 2:
                # Check if second word is a verb/action that makes sense as rejection
                second_word = message_words[1].lower()
                if second_word in ["interested", "sure", "ready", "now", "yet", "today", "working", "good"]:
                    return True
        
        # Check for rejection patterns in context
        rejection_patterns = [
            r"don't want",
            r"doesn't work",
            r"won't work",
            r"can't do",
            r"not working",
            r"not good",
            r"not interested",
            r"no thanks",
            r"none of",
            r"not any",
            r"reject",
            r"decline",
            r"refuse",
            r"cancel",
            r"wrong",
            r"different time",
            r"other time",
            r"else"
        ]
        
        # Check for rejection patterns
        for pattern in rejection_patterns:
            if re.search(pattern, lower_msg, re.IGNORECASE):
                return True
        
        # Check if message starts with "not" and is short (likely rejection)
        if lower_msg.startswith("not ") and len(message_words) <= 4:
            # But exclude cases like "not sure" which might be uncertainty, not rejection
            if "sure" not in lower_msg and "certain" not in lower_msg:
                return True
        
        return False
    
    def _is_cancellation_intent(self, message: str) -> bool:
        """
        Check if message indicates user wants to cancel an existing booking
        
        Args:
            message: User's message (lowercase)
        
        Returns:
            True if cancellation intent detected
        """
        cancellation_keywords = [
            'cancel', 'cancellation', 'cancel this', 'cancel my', 'cancel the',
            'i will cancel', 'i want to cancel', 'i need to cancel',
            'cancel booking', 'cancel appointment', 'cancel my appointment',
            'remove', 'delete', 'don\'t want', "don't want", 'no longer need',
            'can\'t make it', "can't make it", 'wont make it', "won't make it"
        ]
        
        message_lower = message.lower().strip()
        
        # Check for cancellation keywords
        for keyword in cancellation_keywords:
            if keyword in message_lower:
                return True
        
        return False
    
    def _is_rescheduling_intent(self, message: str) -> bool:
        """
        Check if message indicates user wants to reschedule an existing booking
        
        Args:
            message: User's message (lowercase)
        
        Returns:
            True if rescheduling intent detected
        """
        rescheduling_keywords = [
            'reschedule', 're-schedule', 'change time', 'change date',
            'change appointment', 'move appointment', 'different time',
            'different date', 'new time', 'new date', 'switch time',
            'switch date', 'change my appointment', 'move my appointment',
            'i need to reschedule', 'i want to reschedule', 'can i reschedule',
            'change the time', 'change the date', 'modify appointment'
        ]
        
        message_lower = message.lower().strip()
        
        # Check for rescheduling keywords
        for keyword in rescheduling_keywords:
            if keyword in message_lower:
                return True
        
        return False
    
    async def _handle_booking_rescheduling(
        self,
        message: str,
        session: Dict[str, Any],
        booking_id: str,
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """
        Handle rescheduling of an existing booking
        
        Args:
            message: User's rescheduling message
            session: Current session data
            booking_id: Booking ID to reschedule
            calendly_client: Calendly client
        
        Returns:
            Response dictionary with rescheduling flow
        """
        # Get booking details for context
        appointment_details = session.get("appointment_details", {})
        booking_date = appointment_details.get("date", "your appointment")
        booking_time = appointment_details.get("time") or appointment_details.get("start_time", "")
        appointment_type = appointment_details.get("appointment_type", "consultation")
        
        # Use LLM to generate natural response
        llm_response = await self._generate_llm_response(
            f"User wants to reschedule their booking. Current booking: {booking_date} at {booking_time}. "
            "Acknowledge warmly and ask when they'd like to reschedule to (ask about date and time preference).",
            session,
            {
                "booking_date": booking_date,
                "booking_time": booking_time,
                "booking_id": booking_id,
                "appointment_type": appointment_type
            }
        )
        
        if llm_response:
            response_msg = llm_response
        else:
            # Fallback
            response_msg = f"I'd be happy to help you reschedule your appointment on {booking_date}"
            if booking_time:
                response_msg += f" at {booking_time}"
            response_msg += ". When would you like to reschedule to? Do you have a preferred date or time?"
        
        # Store rescheduling context
        session["rescheduling"] = {
            "booking_id": booking_id,
            "original_date": booking_date,
            "original_time": booking_time,
            "appointment_type": appointment_type
        }
        
        return {
            "message": response_msg,
            "context": "rescheduling_booking",
            "appointment_details": appointment_details
        }
    
    async def _handle_rescheduling_booking(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """
        Handle the rescheduling flow - collect new date/time and complete rescheduling
        
        Args:
            message: User's message with new date/time preference
            session: Current session data
            calendly_client: Calendly client
            faq_retriever: FAQ retriever (not used here)
        
        Returns:
            Response dictionary with rescheduling result
        """
        rescheduling_info = session.get("rescheduling", {})
        booking_id = rescheduling_info.get("booking_id")
        appointment_type = rescheduling_info.get("appointment_type", "consultation")
        
        if not booking_id:
            return {
                "message": "I'm sorry, I couldn't find the booking to reschedule. How can I help you today?",
                "context": "greeting"
            }
        
        # Use availability tool to get slots based on user's message
        from tools.availability_tool import AvailabilityTool
        availability_tool = AvailabilityTool(calendly_client)
        
        # Parse user message for date/time preferences
        lower_msg = message.lower().strip()
        
        # Try to extract date and time preference from message
        date_str = None
        time_preference = None
        
        # Check for specific dates
        from datetime import datetime, timedelta
        today = datetime.now()
        
        if "today" in lower_msg:
            date_str = today.strftime("%Y-%m-%d")
        elif "tomorrow" in lower_msg:
            date_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "next week" in lower_msg:
            date_str = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            # Try to parse date from message (simple patterns)
            import re
            date_patterns = [
                r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # MM/DD/YYYY
                r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY-MM-DD
            ]
            for pattern in date_patterns:
                match = re.search(pattern, message)
                if match:
                    try:
                        if len(match.groups()) == 3:
                            # Try to parse
                            date_str = message[match.start():match.end()]
                            # Normalize to YYYY-MM-DD
                            parsed_date = datetime.strptime(date_str.replace("/", "-"), "%Y-%m-%d")
                            date_str = parsed_date.strftime("%Y-%m-%d")
                            break
                    except:
                        pass
        
        # Check for time preferences
        if any(word in lower_msg for word in ["morning", "am", "before noon"]):
            time_preference = "morning"
        elif any(word in lower_msg for word in ["afternoon", "pm", "after noon"]):
            time_preference = "afternoon"
        elif any(word in lower_msg for word in ["evening", "night"]):
            time_preference = "evening"
        
        # If no specific date, default to checking next few days
        if not date_str:
            # Check next 7 days for availability
            date_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        try:
            # Get available slots
            availability = await availability_tool.get_available_slots(
                date=date_str,
                appointment_type=appointment_type,
                time_preference=time_preference
            )
            
            available_slots = availability.get("available_slots", [])
            
            if not available_slots:
                # Try a few more days
                for day_offset in range(2, 8):
                    check_date = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                    availability = await availability_tool.get_available_slots(
                        date=check_date,
                        appointment_type=appointment_type,
                        time_preference=time_preference
                    )
                    available_slots = availability.get("available_slots", [])
                    if available_slots:
                        date_str = check_date
                        break
            
            if not available_slots:
                # No slots available
                llm_response = await self._generate_llm_response(
                    f"User wants to reschedule but no slots available. Apologize and offer alternatives like checking specific dates or waitlist.",
                    session
                )
                
                return {
                    "message": llm_response or "I'm sorry, I don't have any available slots for that time. Would you like me to check a specific date, or would you prefer to be added to our waitlist?",
                    "context": "rescheduling_booking",
                    "appointment_details": session.get("appointment_details")
                }
            
            # Format slots for display
            slot_list = "\n".join([
                f"• {slot.get('date', date_str)} at {slot.get('start_time', 'N/A')}"
                for slot in available_slots[:5]
            ])
            
            # Store slots in session
            session["available_slots"] = available_slots
            session["rescheduling"]["available_slots"] = available_slots
            
            llm_response = await self._generate_llm_response(
                f"User wants to reschedule. Show these available slots: {slot_list}. Ask which time they prefer.",
                session
            )
            
            return {
                "message": llm_response or f"Great! I found these available times:\n\n{slot_list}\n\nWhich time would work best for you?",
                "context": "rescheduling_booking",
                "available_slots": available_slots,
                "appointment_details": session.get("appointment_details")
            }
            
        except Exception as e:
            print(f"❌ Error getting availability for rescheduling: {str(e)}")
            
            llm_response = await self._generate_llm_response(
                f"Error getting availability: {str(e)}. Apologize and ask user to specify a date.",
                session
            )
            
            return {
                "message": llm_response or "I'm sorry, I had trouble checking availability. Could you please tell me a specific date you'd like to reschedule to?",
                "context": "rescheduling_booking",
                "appointment_details": session.get("appointment_details")
            }
    
    async def _handle_booking_cancellation(
        self,
        message: str,
        session: Dict[str, Any],
        booking_id: str,
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """
        Handle cancellation of an existing booking
        
        Args:
            message: User's cancellation message
            session: Current session data
            booking_id: Booking ID to cancel
            calendly_client: Calendly client for cancellation
        
        Returns:
            Response dictionary with cancellation confirmation
        """
        # Use BookingTool to cancel
        booking_tool = BookingTool(calendly_client)
        
        # Check if user is confirming cancellation
        lower_msg = message.lower().strip()
        confirmation_keywords = ['yes', 'confirm', 'sure', 'ok', 'okay', 'proceed', 'do it']
        is_confirmation = any(keyword in lower_msg for keyword in confirmation_keywords)
        
        # If not confirmed yet, ask for confirmation
        if not is_confirmation and not self._is_cancellation_intent(lower_msg):
            # This shouldn't happen, but handle it
            pass
        
        # Get booking details for context
        appointment_details = session.get("appointment_details", {})
        booking_date = appointment_details.get("date", "your appointment")
        booking_time = appointment_details.get("start_time") or appointment_details.get("time", "")
        
        # If user hasn't explicitly confirmed, ask for confirmation
        if not is_confirmation:
            # Use LLM to generate natural confirmation request
            llm_response = await self._generate_llm_response(
                f"User wants to cancel their booking. Booking details: {booking_date} at {booking_time}. "
                "Ask them to confirm the cancellation in a warm, understanding way.",
                session,
                {"booking_date": booking_date, "booking_time": booking_time, "booking_id": booking_id}
            )
            
            if llm_response:
                response_msg = llm_response
            else:
                # Fallback
                response_msg = f"I understand you'd like to cancel your appointment on {booking_date}"
                if booking_time:
                    response_msg += f" at {booking_time}"
                response_msg += ". Are you sure you'd like to cancel this appointment?"
            
            # Store cancellation intent in session
            session["pending_cancellation"] = {
                "booking_id": booking_id,
                "confirmed": False
            }
            
            return {
                "message": response_msg,
                "context": "cancelling_booking",
                "appointment_details": appointment_details
            }
        
        # User confirmed - proceed with cancellation
        try:
            cancel_result = await booking_tool.cancel_booking(booking_id)
            
            if cancel_result.get("success"):
                # Clear booking from session
                session.pop("appointment_details", None)
                session.pop("booking_id", None)
                session.pop("selected_slot", None)
                session.pop("pending_cancellation", None)
                
                # Use LLM to generate natural cancellation confirmation
                llm_response = await self._generate_llm_response(
                    f"User confirmed cancellation. Booking on {booking_date} at {booking_time} has been cancelled. "
                    "Confirm the cancellation warmly and offer to help with anything else.",
                    session
                )
                
                if llm_response:
                    response_msg = llm_response
                else:
                    # Fallback
                    response_msg = f"✅ Your appointment on {booking_date}"
                    if booking_time:
                        response_msg += f" at {booking_time}"
                    response_msg += " has been cancelled successfully. Is there anything else I can help you with?"
                
                return {
                    "message": response_msg,
                    "context": "greeting",
                    "appointment_details": None
                }
            else:
                # Cancellation failed
                error_msg = cancel_result.get("error", "Unknown error")
                
                llm_response = await self._generate_llm_response(
                    f"Cancellation failed with error: {error_msg}. Apologize and offer alternatives.",
                    session
                )
                
                if llm_response:
                    response_msg = llm_response
                else:
                    # Fallback
                    response_msg = f"I'm sorry, I wasn't able to cancel your appointment. Error: {error_msg}. "
                    response_msg += "Please contact our office directly at +1-555-123-4567 for assistance."
                
                return {
                    "message": response_msg,
                    "context": session.get("context", "greeting"),
                    "appointment_details": appointment_details
                }
                
        except Exception as e:
            print(f"❌ Error cancelling booking: {str(e)}")
            
            llm_response = await self._generate_llm_response(
                f"An error occurred while cancelling: {str(e)}. Apologize and offer to help.",
                session
            )
            
            if llm_response:
                response_msg = llm_response
            else:
                response_msg = f"I'm sorry, there was an error cancelling your appointment. Please contact our office at +1-555-123-4567 for assistance."
            
            return {
                "message": response_msg,
                "context": session.get("context", "greeting"),
                "appointment_details": appointment_details
            }
    
    async def _complete_rescheduling(
        self,
        selected_slot: Dict[str, Any],
        session: Dict[str, Any],
        calendly_client: CalendlyClient
    ) -> Dict[str, Any]:
        """
        Complete the rescheduling process: cancel old booking and create new one
        
        Args:
            selected_slot: The new slot selected by user
            session: Current session data
            calendly_client: Calendly client
        
        Returns:
            Response dictionary with rescheduling result
        """
        rescheduling_info = session.get("rescheduling", {})
        old_booking_id = rescheduling_info.get("booking_id")
        appointment_type = rescheduling_info.get("appointment_type", "consultation")
        
        if not old_booking_id:
            return {
                "message": "I'm sorry, I couldn't find the booking to reschedule. How can I help you today?",
                "context": "greeting"
            }
        
        # Get patient info from original booking
        appointment_details = session.get("appointment_details", {})
        patient_info = {
            "name": appointment_details.get("patient_name", ""),
            "email": appointment_details.get("patient_email", ""),
            "phone": appointment_details.get("patient_phone", "")
        }
        
        # If patient info is missing, we need to collect it
        if not all([patient_info.get("name"), patient_info.get("email"), patient_info.get("phone")]):
            # Store rescheduling context and collect info
            session["selected_slot"] = selected_slot
            session["rescheduling"]["selected_slot"] = selected_slot
            
            llm_response = await self._generate_llm_response(
                f"User selected new time for rescheduling: {selected_slot.get('display_text', '')}. "
                "Ask for their contact information (name, email, phone) to complete the rescheduling.",
                session
            )
            
            return {
                "message": llm_response or "Perfect! To complete the rescheduling, I'll need your contact information:\n\n• Your full name\n• Your phone number\n• Your email address\n\nYou can provide them all at once or one at a time.",
                "context": "rescheduling_booking",
                "appointment_details": appointment_details
            }
        
        # We have all info - proceed with rescheduling
        booking_tool = BookingTool(calendly_client)
        
        # Get slot details
        new_date = selected_slot.get("full_date") or selected_slot.get("date", "")
        new_time = selected_slot.get("raw_time") or selected_slot.get("start_time", "")
        
        # Convert date format if needed
        if not re.match(r'\d{4}-\d{2}-\d{2}', new_date):
            # Try to parse and convert
            try:
                from datetime import datetime
                parsed_date = datetime.strptime(new_date, "%A, %B %d")
                # Use current year
                current_year = datetime.now().year
                parsed_date = parsed_date.replace(year=current_year)
                new_date = parsed_date.strftime("%Y-%m-%d")
            except:
                pass
        
        # Convert time to HH:MM format if needed
        if "AM" in new_time.upper() or "PM" in new_time.upper():
            try:
                from datetime import datetime
                time_obj = datetime.strptime(new_time.upper().strip(), "%I:%M %p")
                new_time = time_obj.strftime("%H:%M")
            except:
                pass
        
        try:
            # Cancel old booking
            cancel_result = await booking_tool.cancel_booking(old_booking_id)
            
            if not cancel_result.get("success"):
                llm_response = await self._generate_llm_response(
                    f"Failed to cancel old booking: {cancel_result.get('error', 'Unknown error')}. Apologize and offer alternatives.",
                    session
                )
                
                return {
                    "message": llm_response or f"I'm sorry, I wasn't able to cancel your original appointment. Error: {cancel_result.get('error', 'Unknown error')}. Please contact our office at +1-555-123-4567 for assistance.",
                    "context": "greeting",
                    "appointment_details": appointment_details
                }
            
            # Create new booking
            booking_result = await booking_tool.create_booking(
                appointment_type=appointment_type,
                date=new_date,
                start_time=new_time,
                patient_name=patient_info["name"],
                patient_email=patient_info["email"],
                patient_phone=patient_info["phone"],
                reason=appointment_details.get("reason", "Rescheduled appointment")
            )
            
            if booking_result.get("success"):
                new_booking = booking_result.get("booking", {})
                
                # Update appointment details
                new_appointment_details = {
                    "booking_id": new_booking.get("booking_id"),
                    "appointment_type": appointment_type,
                    "date": new_date,
                    "time": new_time,
                    "start_time": new_time,
                    "duration_minutes": self.appointment_types.get(appointment_type, {}).get("duration", 30),
                    "confirmation_code": new_booking.get("confirmation_code"),
                    "status": new_booking.get("status", "confirmed"),
                    "patient_name": patient_info["name"],
                    "patient_email": patient_info["email"],
                    "patient_phone": patient_info["phone"]
                }
                
                # Clear rescheduling context
                session.pop("rescheduling", None)
                session["appointment_details"] = new_appointment_details
                session["selected_slot"] = None
                
                # Generate success message
                display_text = selected_slot.get("display_text", f"{new_date} at {new_time}")
                
                llm_response = await self._generate_llm_response(
                    f"Successfully rescheduled appointment from {rescheduling_info.get('original_date')} at {rescheduling_info.get('original_time')} to {display_text}. "
                    "Confirm the rescheduling warmly and provide confirmation details.",
                    session
                )
                
                if llm_response:
                    response_msg = llm_response
                else:
                    response_msg = f"✅ Great! I've successfully rescheduled your appointment to {display_text}.\n\n"
                    response_msg += f"📋 Confirmation Code: {new_booking.get('confirmation_code', 'N/A')}\n"
                    response_msg += f"You'll receive a confirmation email at {patient_info['email']}.\n\n"
                    response_msg += "Is there anything else I can help you with?"
                
                return {
                    "message": response_msg,
                    "context": "confirmed",
                    "appointment_details": new_appointment_details
                }
            else:
                # Booking creation failed - old booking is already cancelled
                llm_response = await self._generate_llm_response(
                    f"Old booking cancelled but new booking failed: {booking_result.get('error', 'Unknown error')}. "
                    "Apologize and offer to help book a new appointment.",
                    session
                )
                
                # Clear rescheduling context
                session.pop("rescheduling", None)
                session.pop("appointment_details", None)
                
                return {
                    "message": llm_response or f"I'm sorry, I cancelled your original appointment but wasn't able to create the new one. Error: {booking_result.get('error', 'Unknown error')}. Would you like me to help you book a new appointment?",
                    "context": "greeting"
                }
                
        except Exception as e:
            print(f"❌ Error completing rescheduling: {str(e)}")
            
            llm_response = await self._generate_llm_response(
                f"Error during rescheduling: {str(e)}. Apologize and offer help.",
                session
            )
            
            return {
                "message": llm_response or f"I'm sorry, there was an error while rescheduling your appointment. Please contact our office at +1-555-123-4567 for assistance.",
                "context": "greeting",
                "appointment_details": appointment_details
            }
    
    async def _handle_cancellation_confirmation(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """
        Handle confirmation of booking cancellation
        
        Args:
            message: User's confirmation message
            session: Current session data
            calendly_client: Calendly client
            faq_retriever: FAQ retriever (not used here)
        
        Returns:
            Response dictionary with cancellation result
        """
        pending_cancellation = session.get("pending_cancellation", {})
        booking_id = pending_cancellation.get("booking_id")
        
        if not booking_id:
            return {
                "message": "I'm sorry, I couldn't find the booking to cancel. How can I help you today?",
                "context": "greeting"
            }
        
        lower_msg = message.lower().strip()
        
        # Check if user confirmed
        confirmation_keywords = ['yes', 'confirm', 'sure', 'ok', 'okay', 'proceed', 'do it', 'cancel', 'cancel it']
        is_confirmed = any(keyword in lower_msg for keyword in confirmation_keywords)
        
        # Check if user declined
        decline_keywords = ['no', 'not', "don't", "dont", 'keep', 'never mind', 'forget it']
        is_declined = any(keyword in lower_msg for keyword in decline_keywords)
        
        if is_declined:
            # User changed their mind
            session.pop("pending_cancellation", None)
            
            llm_response = await self._generate_llm_response(
                "User decided not to cancel. Acknowledge warmly and ask if there's anything else you can help with.",
                session
            )
            
            return {
                "message": llm_response or "No problem at all! Your appointment is still confirmed. Is there anything else I can help you with?",
                "context": "greeting",
                "appointment_details": session.get("appointment_details")
            }
        
        if is_confirmed:
            # Proceed with cancellation
            return await self._handle_booking_cancellation(
                message=message,
                session=session,
                booking_id=booking_id,
                calendly_client=calendly_client
            )
        
        # Unclear response - ask for clarification
        llm_response = await self._generate_llm_response(
            "User's response is unclear. Ask them to confirm if they want to cancel the appointment (yes/no).",
            session
        )
        
        return {
            "message": llm_response or "I want to make sure I understand correctly. Would you like to cancel your appointment? Please say 'yes' to confirm or 'no' to keep it.",
            "context": "cancelling_booking",
            "appointment_details": session.get("appointment_details")
        }
    
    async def _handle_rejection(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle rejection/negative responses based on context"""
        context = session.get("context", "greeting")
        lower_msg = message.lower()
        
        # Handle rejection in slot selection
        if context == "selecting_slot":
            return await self._handle_slot_rejection(session, calendly_client, faq_retriever)
        
        # Handle rejection in appointment type selection
        if context == "collecting_reason":
            return {
                "message": "No problem! Could you tell me more about what you need? I can help you find the right type of appointment.",
                "context": "collecting_reason",
                
            }
        
        # Handle rejection in time preference
        if context == "collecting_time_preference":
            return {
                "message": "That's okay! When would be a good time for you? I can check availability for any day or time.",
                "context": "collecting_time_preference",
                
            }
        
        # Handle rejection in patient info collection
        if context == "collecting_patient_info":
            return {
                "message": "I understand. Could you provide your contact information so I can confirm your appointment? I need your name, phone number, and email.",
                "context": "collecting_patient_info"
            }
        
        # General rejection - offer to help differently
        return {
            "message": "I understand. How can I help you today? I can help you schedule an appointment or answer questions about our clinic.",
            "context": "greeting",
            
        }
    
    async def _handle_slot_rejection(
        self,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle when user rejects all offered time slots"""
        appointment_type = session.get("appointment_type", "consultation")
        available_slots = session.get("available_slots", [])
        
        # Try to get more slots from different dates
        today = datetime.now()
        new_slots = []
        
        # Check more days ahead
        for day_offset in range(8, 15):  # Check days 8-14
            check_date = today + timedelta(days=day_offset)
            date_str = check_date.strftime("%Y-%m-%d")
            
            try:
                slots = await calendly_client.get_availability(
                    date=date_str,
                    appointment_type=appointment_type
                )
                
                for slot in slots.get("available_slots", []):
                    if slot["available"]:
                        slot["date"] = check_date.strftime("%A, %B %d")
                        slot["full_date"] = date_str
                        new_slots.append(slot)
                        
                        if len(new_slots) >= 4:
                            break
                
                if len(new_slots) >= 4:
                    break
            except:
                continue
        
        if new_slots:
            slot_list = "\n".join([
                f"• {slot['date']} at {slot['start_time']}"
                for slot in new_slots[:4]
            ])
            
            session["available_slots"] = new_slots
            
            # Prepare structured slot data
            structured_slots = []
            for slot in new_slots[:4]:
                structured_slots.append({
                    "date": slot.get("date", ""),
                    "full_date": slot.get("full_date", ""),
                    "start_time": slot.get("start_time", ""),
                    "end_time": slot.get("end_time", ""),
                    "raw_time": slot.get("raw_time", slot.get("start_time", "")),
                    "display_text": f"{slot.get('date', '')} at {slot.get('start_time', '')}",
                    "available": True
                })
            
            return {
                "message": f"No problem! Let me show you some additional options:\n\n{slot_list}\n\nWould any of these work better for you?",
                "context": "selecting_slot",
                "available_slots": structured_slots
            }
        else:
            return {
                "message": "I understand those times don't work for you. Unfortunately, I don't have other available slots in the near future. Would you like me to:\n\n• Check availability for a specific date\n• Put you on a waitlist for cancellations\n• Have someone from our office call you to find a time that works?",
                "context": "selecting_slot",
                
            }
    
    def _get_context_continuation(self, session: Dict[str, Any]) -> str:
        """Get appropriate continuation message based on context"""
        context = session.get("context") or session.get("previous_context", "greeting")
        
        continuations = {
            "collecting_reason": "What brings you in today?",
            "collecting_time_preference": "When would you like your appointment?",
            "selecting_slot": "Which time slot works best for you?",
            "collecting_patient_info": "Could you provide your contact information?"
        }
        
        return continuations.get(context, "How can I help you?")
    
    def _get_context_suggestions(self, context: str, session: Dict[str, Any]) -> List[str]:
        """Get appropriate suggestions based on context - DISABLED for natural conversation"""
        # No suggestions - let the conversation flow naturally
        return []
    
    async def _handle_faq_during_booking(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle FAQ during booking process"""
        # FAQ is handled in _check_faq method before context handlers
        # This is a placeholder
        return {
            "message": "How can I help you with your appointment?",
            "context": session.get("context", "greeting")
        }
    
    async def _handle_checking_availability(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle responses when checking availability"""
        lower_msg = message.lower().strip()
        
        # Handle "Check specific date" or "Check specific date" button click
        if "check specific date" in lower_msg or "specific date" in lower_msg or lower_msg == "check specific date":
            return {
                "message": "Sure! What date would you like me to check? You can tell me:\n\n• A specific date (e.g., 'December 20' or '12/20')\n• A day of the week (e.g., 'Monday' or 'next Friday')\n• 'Tomorrow' or 'next week'",
                "context": "checking_specific_date",
                
            }
        
        # Handle "Waitlist" button click
        if lower_msg == "waitlist" or "waitlist" in lower_msg:
            return {
                "message": "I've added you to our waitlist for cancellations. If an appointment becomes available, we'll contact you right away.\n\nTo complete your waitlist request, I'll need:\n• Your name\n• Your phone number\n• Your email address\n• Preferred appointment type\n\nWould you like to provide this information now?",
                "context": "waitlist",
                
            }
        
        # Handle "Call me" button click
        if "call me" in lower_msg or lower_msg == "call me":
            return {
                "message": "I'll have someone from our office call you. To help them assist you better, could you provide:\n\n• Your name\n• Your phone number\n• Best time to call you\n\nOr would you prefer to call us directly at +1-555-123-4567?",
                "context": "contact_request",
                
            }
        
        # If user provides a date, parse and check availability for that date
        date_patterns = [
            r'(tomorrow|today)',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(\d{1,2}[/-]\d{1,2})',
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, lower_msg, re.IGNORECASE)
            if match:
                # Parse the date and check availability for that specific date
                return await self._handle_checking_specific_date(message, session, calendly_client)
        
        # If user wants to book from shown slots, transition to slot selection
        if any(word in lower_msg for word in ['book', 'schedule', 'yes', 'that works', 'okay', 'ok']):
            # If we have slots, move to selection
            if session.get("available_slots"):
                return {
                    "message": "Great! Which time would you like to book?",
                    "context": "selecting_slot"
                }
        
        # Default: show availability again
        return await self._handle_check_availability(session, calendly_client, faq_retriever)
    
    async def _handle_check_availability(
        self,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle availability check request - fetch slots from Calendly"""
        try:
            # Use default appointment type or get from session
            appointment_type = session.get("appointment_type", "consultation")
            
            # Get available slots for the next 7 days
            today = datetime.now()
            available_slots = []
            
            # Start from tomorrow (day_offset=1) since Calendly requires future dates
            for day_offset in range(1, 8):  # Check next 7 days
                check_date = today + timedelta(days=day_offset)
                date_str = check_date.strftime("%Y-%m-%d")
                
                try:
                    slots = await calendly_client.get_availability(
                        date=date_str,
                        appointment_type=appointment_type
                    )
                    
                    # Filter available slots
                    for slot in slots.get("available_slots", []):
                        if slot["available"]:
                            slot["date"] = check_date.strftime("%A, %B %d")
                            slot["full_date"] = date_str
                            available_slots.append(slot)
                            
                            if len(available_slots) >= 5:
                                break
                    
                    if len(available_slots) >= 5:
                        break
                except Exception as e:
                    print(f"Error fetching availability for {date_str}: {e}")
                    continue
            
            # Store slots in session
            session["available_slots"] = available_slots
            
            if not available_slots:
                return {
                    "message": "I'm sorry, but I don't see any available appointments in the next week. Would you like me to:\n\n• Check availability for a specific date\n• Put you on a waitlist for cancellations\n• Have someone from our office call you?",
                    "context": "checking_availability",
                    
                }
            
            # Format slots for display
            slot_list = "\n".join([
                f"• {slot['date']} at {slot['start_time']}"
                for slot in available_slots[:5]
            ])
            
            appt_info = self.appointment_types.get(appointment_type, self.appointment_types["consultation"])
            
            response = f"Here are the available appointment times I found:\n\n{slot_list}\n\n"
            response += f"These are for {appt_info['name']} appointments ({appt_info['duration']} minutes). "
            response += "Which works best for you, or would you like to check a different date?"
            
            # Prepare structured slot data for frontend (clickable buttons)
            structured_slots = []
            for slot in available_slots[:5]:
                structured_slots.append({
                    "date": slot.get("date", ""),
                    "full_date": slot.get("full_date", ""),
                    "start_time": slot.get("start_time", ""),
                    "end_time": slot.get("end_time", ""),
                    "raw_time": slot.get("raw_time", slot.get("start_time", "")),
                    "display_text": f"{slot.get('date', '')} at {slot.get('start_time', '')}",
                    "available": True
                })
            
            return {
                "message": response,
                "context": "selecting_slot",
                "available_slots": structured_slots  # Structured data for UI
            }
            
        except Exception as e:
            print(f"Error checking availability: {e}")
            # Improved error message
            error_msg = await self._generate_llm_response(
                "I'm having trouble accessing the schedule. Apologize warmly and offer helpful alternatives.",
                session
            )
            return {
                "message": error_msg or "I'm having trouble accessing our schedule right now. This might be a temporary issue. Would you like me to:\n\n• Have someone from our office call you back\n• Try again in a moment\n• Check availability for a specific date\n\nWhat would work best for you?",
                "context": "error"
            }
    
    async def _handle_checking_specific_date(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle checking availability for a specific date"""
        lower_msg = message.lower().strip()
        today = datetime.now()
        target_date = None
        
        try:
            # Handle "tomorrow"
            if "tomorrow" in lower_msg:
                target_date = today + timedelta(days=1)
            # Handle "today"
            elif "today" in lower_msg:
                target_date = today
            # Handle day names (next Monday, etc.)
            elif any(day in lower_msg for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                for i in range(1, 14):  # Check next 2 weeks
                    check_date = today + timedelta(days=i)
                    if check_date.strftime("%A").lower() in lower_msg:
                        target_date = check_date
                        break
            # Try to parse date formats: MM/DD, MM-DD, YYYY-MM-DD, or "December 20"
            else:
                # Try MM/DD or MM-DD format
                date_match = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', message)
                if date_match:
                    month = int(date_match.group(1))
                    day = int(date_match.group(2))
                    year = int(date_match.group(3)) if date_match.group(3) else today.year
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                    try:
                        target_date = datetime(year, month, day)
                    except:
                        pass
                # Try "December 20" format
                else:
                    months = {
                        'january': 1, 'february': 2, 'march': 3, 'april': 4,
                        'may': 5, 'june': 6, 'july': 7, 'august': 8,
                        'september': 9, 'october': 10, 'november': 11, 'december': 12
                    }
                    for month_name, month_num in months.items():
                        if month_name in lower_msg:
                            day_match = re.search(r'\b(\d{1,2})\b', message)
                            if day_match:
                                day = int(day_match.group(1))
                                year = today.year
                                try:
                                    target_date = datetime(year, month_num, day)
                                    # If date is in the past, assume next year
                                    if target_date < today:
                                        target_date = datetime(year + 1, month_num, day)
                                except:
                                    pass
                            break
            
            if not target_date:
                return {
                    "message": "I didn't quite catch that date. Could you tell me a specific date? For example:\n\n• 'December 20'\n• '12/20'\n• 'Tomorrow'\n• 'Next Monday'",
                    "context": "checking_specific_date",
                    
                }
            
            # Ensure date is in the future
            if target_date.date() < today.date():
                return {
                    "message": "That date is in the past. Please choose a future date for your appointment.",
                    "context": "checking_specific_date",
                    
                }
            
            # Get availability for the specific date
            appointment_type = session.get("appointment_type", "consultation")
            date_str = target_date.strftime("%Y-%m-%d")
            
            slots = await calendly_client.get_availability(
                date=date_str,
                appointment_type=appointment_type
            )
            
            available_slots = [slot for slot in slots.get("available_slots", []) if slot.get("available")]
            
            if not available_slots:
                formatted_date = target_date.strftime("%A, %B %d, %Y")
                return {
                    "message": f"I'm sorry, but there are no available appointments on {formatted_date}. Would you like me to:\n\n• Check a different date\n• Put you on a waitlist for cancellations\n• Have someone from our office call you?",
                    "context": "checking_availability",
                    
                }
            
            # Format slots for display
            formatted_date = target_date.strftime("%A, %B %d")
            slot_list = "\n".join([
                f"• {slot.get('start_time', 'N/A')}"
                for slot in available_slots[:5]
            ])
            
            # Store slots in session with date info
            for slot in available_slots:
                slot["date"] = formatted_date
                slot["full_date"] = date_str
            
            session["available_slots"] = available_slots
            
            appt_info = self.appointment_types.get(appointment_type, self.appointment_types["consultation"])
            
            response = f"Here are the available times on {formatted_date}:\n\n{slot_list}\n\n"
            response += f"These are for {appt_info['name']} appointments ({appt_info['duration']} minutes). "
            response += "Which works best for you?"
            
            # Prepare structured slot data for frontend (clickable buttons)
            structured_slots = []
            for slot in available_slots[:5]:
                structured_slots.append({
                    "date": formatted_date,
                    "full_date": date_str,
                    "start_time": slot.get("start_time", ""),
                    "end_time": slot.get("end_time", ""),
                    "raw_time": slot.get("raw_time", slot.get("start_time", "")),
                    "display_text": f"{formatted_date} at {slot.get('start_time', '')}",
                    "available": True
                })
            
            return {
                "message": response,
                "context": "selecting_slot",
                "available_slots": structured_slots  # Structured data for UI
            }
            
        except Exception as e:
            print(f"Error checking specific date: {e}")
            # Improved error message with examples
            error_msg = await self._generate_llm_response(
                "I'm having trouble understanding that date. Apologize and provide helpful examples of date formats.",
                session
            )
            return {
                "message": error_msg or "I'm having trouble understanding that date. Could you try a different format? For example:\n\n• 'December 20'\n• '12/20'\n• 'Tomorrow'\n• 'Next Monday'\n\nWhich format would you like to use?",
                "context": "checking_specific_date"
                
            }
    
    async def _handle_waitlist(
        self,
        message: str,
        session: Dict[str, Any],
        calendly_client: CalendlyClient,
        faq_retriever: Optional[FAQRetriever] = None
    ) -> Dict[str, Any]:
        """Handle waitlist requests"""
        lower_msg = message.lower().strip()
        
        # If user confirms, collect their information
        if any(word in lower_msg for word in ['yes', 'sure', 'okay', 'ok', 'add me']):
            return {
                "message": "Great! I'll add you to our waitlist. Please provide:\n\n• Your full name\n• Your phone number\n• Your email address\n• Preferred appointment type (if any)",
                "context": "collecting_waitlist_info"
            }
        
        # If user declines
        if any(word in lower_msg for word in ['no', 'not', "don't", 'cancel']):
            return {
                "message": "No problem! Is there anything else I can help you with?",
                "context": "greeting",
                
            }
        
        # Collect waitlist information
        patient_info = session.get("patient_info", {})
        
        # Extract email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message)
        if email_match:
            patient_info["email"] = email_match.group(0)
        
        # Extract phone
        phone_match = re.search(r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', message)
        if phone_match:
            patient_info["phone"] = phone_match.group(0)
        
        # Extract name
        name_text = message
        if email_match:
            name_text = name_text.replace(email_match.group(0), "")
        if phone_match:
            name_text = name_text.replace(phone_match.group(0), "")
        
        name = re.sub(r'[^a-zA-Z\s]', '', name_text).strip()
        if name and len(name.split()) >= 2:  # At least first and last name
            patient_info["name"] = name
        
        session["patient_info"] = patient_info
        
        # Check if we have all required info
        required = ["name", "email", "phone"]
        missing = [f for f in required if f not in patient_info or not patient_info[f]]
        
        if missing:
            missing_str = ", ".join(missing)
            return {
                "message": f"I still need your {missing_str}. Please provide this information.",
                "context": "collecting_waitlist_info"
            }
        
        # All info collected - confirm waitlist addition
        return {
            "message": f"Perfect! I've added you to our waitlist, {patient_info.get('name', 'there')}. We'll contact you at {patient_info.get('phone', 'your phone')} or {patient_info.get('email', 'your email')} if an appointment becomes available.\n\nIs there anything else I can help you with?",
            "context": "waitlist_confirmed",
            
        }