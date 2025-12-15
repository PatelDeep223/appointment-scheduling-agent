"""
LLM Service for conversational AI responses
Uses OpenAI API with system prompts for natural conversation
"""

import os
from typing import List, Dict, Any, Optional
from openai import OpenAI

class LLMService:
    """
    Service for generating conversational responses using OpenAI
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Use cheaper model by default
    
    async def generate_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        user_message: str,
        context_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a conversational response using LLM
        
        Args:
            system_prompt: System prompt defining the assistant's behavior
            conversation_history: Previous conversation messages
            user_message: Current user message
            context_data: Additional context (appointment type, slots, etc.)
        
        Returns:
            Generated response message
        """
        # Build messages for API
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history (last 10 messages to keep context manageable)
        for msg in conversation_history[-10:]:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg.get("content", "")
                })
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Add context information if available
        if context_data:
            context_info = self._format_context(context_data)
            if context_info:
                # Add context as a system message or append to user message
                messages[-1]["content"] += f"\n\n[Context: {context_info}]"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,  # Balanced creativity
                max_tokens=500,  # Reasonable response length
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"❌ LLM API Error: {str(e)}")
            # Fallback to a simple response
            return "I apologize, but I'm having trouble processing that right now. Could you please rephrase your question?"
    
    def _format_context(self, context_data: Dict[str, Any]) -> str:
        """
        Format context data into a readable string for the LLM
        
        Args:
            context_data: Context information
        
        Returns:
            Formatted context string
        """
        context_parts = []
        
        if context_data.get("appointment_type"):
            appt_type = context_data["appointment_type"]
            context_parts.append(f"Appointment type: {appt_type}")
        
        if context_data.get("available_slots"):
            slots = context_data["available_slots"]
            if slots:
                slot_list = ", ".join([f"{s.get('date', '')} at {s.get('start_time', '')}" for s in slots[:3]])
                context_parts.append(f"Available slots: {slot_list}")
        
        if context_data.get("patient_info"):
            patient = context_data["patient_info"]
            if patient.get("name"):
                context_parts.append(f"Patient name: {patient['name']}")
            if patient.get("email"):
                context_parts.append(f"Patient email: {patient['email']}")
        
        if context_data.get("context"):
            context_parts.append(f"Current context: {context_data['context']}")
        
        return "; ".join(context_parts) if context_parts else ""

