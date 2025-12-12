"""
Basic tests for the scheduling agent
"""

import pytest
import asyncio
from datetime import datetime

# Import modules (adjust imports based on your structure)
# from backend.agent.scheduling_agent import SchedulingAgent
# from backend.rag.faq_rag import FAQRetriever
# from backend.api.calendly_integration import CalendlyClient


def test_imports():
    """Test that all modules can be imported"""
    try:
        from backend.agent.scheduling_agent import SchedulingAgent
        from backend.rag.faq_rag import FAQRetriever
        from backend.api.calendly_integration import CalendlyClient
        from backend.models.schemas import ChatRequest, ChatResponse
        assert True
    except ImportError as e:
        pytest.fail(f"Import error: {e}")


@pytest.mark.asyncio
async def test_calendly_mock():
    """Test mock Calendly client"""
    from backend.api.calendly_integration import CalendlyClient
    
    client = CalendlyClient()
    
    # Test availability
    today = datetime.now().strftime("%Y-%m-%d")
    availability = await client.get_availability(
        date=today,
        appointment_type="consultation"
    )
    
    assert "date" in availability
    assert "available_slots" in availability
    assert isinstance(availability["available_slots"], list)


@pytest.mark.asyncio
async def test_scheduling_agent_basic():
    """Test basic scheduling agent functionality"""
    from backend.agent.scheduling_agent import SchedulingAgent
    from backend.api.calendly_integration import CalendlyClient
    
    agent = SchedulingAgent()
    calendly = CalendlyClient()
    
    session = {
        "context": "greeting",
        "appointment_type": None,
        "patient_info": {},
        "conversation_history": []
    }
    
    # Mock FAQ retriever (would need proper initialization in real test)
    class MockFAQRetriever:
        async def get_answer(self, category):
            return f"FAQ answer for {category}"
    
    faq_retriever = MockFAQRetriever()
    
    # Test greeting
    response = await agent.process_message(
        message="Hello",
        session=session,
        faq_retriever=faq_retriever,
        calendly_client=calendly
    )
    
    assert "message" in response
    assert "context" in response


def test_schemas():
    """Test Pydantic schemas"""
    from backend.models.schemas import ChatRequest, ChatResponse, AppointmentRequest
    
    # Test ChatRequest
    chat_req = ChatRequest(message="Hello", session_id="test-123")
    assert chat_req.message == "Hello"
    assert chat_req.session_id == "test-123"
    
    # Test ChatResponse
    chat_resp = ChatResponse(
        message="Hi there!",
        context="greeting",
        suggestions=["Option 1"]
    )
    assert chat_resp.message == "Hi there!"
    assert chat_resp.context == "greeting"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

