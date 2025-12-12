"""
Prompts and response templates for the scheduling agent
"""

SYSTEM_PROMPTS = {
    "main_agent": """You are a helpful medical appointment scheduling assistant for HealthCare Plus Clinic.

Your responsibilities:
1. Help patients schedule appointments in a warm, empathetic manner
2. Answer frequently asked questions about the clinic
3. Collect necessary information for booking
4. Suggest appropriate appointment types based on patient needs
5. Handle scheduling conflicts and edge cases gracefully

Appointment Types:
- General Consultation: 30 minutes (for new symptoms, general health concerns)
- Follow-up: 15 minutes (for checking progress on existing conditions)
- Physical Exam: 45 minutes (for comprehensive health assessments)
- Specialist Consultation: 60 minutes (for specific medical specialties)

Guidelines:
- Be conversational and empathetic (healthcare context)
- Ask one question at a time to avoid overwhelming the patient
- Confirm details before booking
- Seamlessly switch between FAQ answering and scheduling
- If no slots available, offer alternatives or suggest calling the office
- Handle ambiguous time references by asking for clarification
- Never make medical diagnoses or give medical advice

Clinic Information:
- Name: HealthCare Plus Clinic
- Phone: +1-555-123-4567
- Hours: Monday-Friday 8:00 AM - 6:00 PM, Saturday 9:00 AM - 2:00 PM
- Location: 123 Health Street, Medical District, NY 10001
""",
    
    "faq_assistant": """You are answering frequently asked questions about HealthCare Plus Clinic.

Provide accurate, helpful information based on the clinic's knowledge base.
Be concise but thorough. If you don't know something, direct the patient to call the clinic.

After answering an FAQ during a booking process, smoothly transition back to scheduling.
""",
}


RESPONSE_TEMPLATES = {
    "greeting": """Hello! I'm here to help you schedule a medical appointment at HealthCare Plus Clinic. 

I can help you:
• Schedule a new appointment
• Answer questions about our services
• Provide information about insurance, location, and hours

How can I assist you today?""",
    
    "ask_reason": """I'd be happy to help you schedule an appointment! 

Could you tell me what brings you in today? This will help me recommend the right type of appointment for you.""",
    
    "ask_appointment_type": """Based on your needs, I'd recommend a {appointment_type} ({duration} minutes).

Does that sound appropriate, or would you prefer a different type of appointment?""",
    
    "ask_time_preference": """When would you like to come in? 

Do you have a preference for:
• Morning appointments (before noon)
• Afternoon appointments (after noon)
• Specific day/date""",
    
    "show_available_slots": """I have these available times:\n\n{slots}\n\nWhich works best for your schedule?""",
    
    "no_slots_available": """I apologize, but we don't have any available appointments for your preferred time.

Here are some options:
• I can show you alternative dates/times
• You can join our waitlist for cancellations
• Call our office at +1-555-123-4567 for urgent scheduling

What would you prefer?""",
    
    "collect_patient_info": """Excellent! Before I confirm your appointment, I'll need a few details:

• Your full name
• Best phone number to reach you
• Email address for confirmation

Please provide these when you're ready.""",
    
    "confirm_booking": """Perfect! Your appointment is confirmed:

📅 Date: {date}
🕐 Time: {time}
📋 Type: {appointment_type}
⏱️ Duration: {duration} minutes
🔖 Confirmation Code: {confirmation_code}

You'll receive a confirmation email at {email} with all the details.

Important reminders:
• Please arrive 15 minutes early
• Bring your insurance card and ID
• Cancel at least 24 hours in advance if needed

Is there anything else you'd like to know?""",
    
    "booking_error": """I encountered an issue while booking your appointment. 

Please call our office at +1-555-123-4567 and mention booking reference {reference}. Our staff will be happy to help you complete your booking.""",
    
    "ambiguous_time": """Just to confirm, when you say "{user_input}", do you mean:

{clarification_options}

Which one did you have in mind?""",
    
    "change_mind": """No problem at all! We can start over.

Would you like to:
• Schedule a different type of appointment
• Choose a different time
• Ask questions about the clinic
• Something else""",
    
    "faq_transition_back": """Got it! Now, let's get back to scheduling your appointment.

{context_continuation}""",
}


INTENT_PATTERNS = {
    "scheduling": [
        "appointment", "schedule", "book", "booking",
        "see doctor", "visit", "checkup", "check-up",
        "consultation", "exam", "examination"
    ],
    
    "cancel": [
        "cancel", "cancellation", "reschedule",
        "change appointment", "modify booking"
    ],
    
    "faq_insurance": [
        "insurance", "coverage", "accept",
        "blue cross", "aetna", "cigna", "medicare"
    ],
    
    "faq_location": [
        "location", "address", "where",
        "directions", "how to get"
    ],
    
    "faq_hours": [
        "hours", "open", "close",
        "business hours", "when open"
    ],
    
    "faq_parking": [
        "parking", "park", "lot"
    ],
    
    "faq_payment": [
        "payment", "pay", "cost", "price",
        "billing", "fees", "charge"
    ],
    
    "faq_first_visit": [
        "first visit", "new patient",
        "what to bring", "documents"
    ],
    
    "urgent": [
        "urgent", "emergency", "asap",
        "soon as possible", "today", "right now"
    ]
}


VALIDATION_MESSAGES = {
    "invalid_email": "That doesn't look like a valid email address. Could you check and provide it again?",
    
    "invalid_phone": "I need a valid phone number to reach you. Please provide your phone number with area code.",
    
    "past_date": "That date has already passed. Please choose a future date for your appointment.",
    
    "outside_business_hours": "That time is outside our business hours (Mon-Fri 8AM-6PM, Sat 9AM-2PM). Could you choose a different time?",
    
    "slot_unavailable": "I'm sorry, that time slot is no longer available. Let me show you other options.",
    
    "missing_info": "I still need the following information: {missing_fields}",
}


ERROR_MESSAGES = {
    "api_error": "I'm having trouble connecting to our scheduling system. Please try again in a moment or call +1-555-123-4567.",
    
    "unknown_error": "Something went wrong. Please call our office at +1-555-123-4567 for assistance.",
    
    "timeout": "The request is taking longer than expected. Would you like to wait or try again later?",
}