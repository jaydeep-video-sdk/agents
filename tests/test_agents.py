import pytest
import asyncio
from unittest.mock import Mock, patch
from id_verification.src.verification_agent import IDVerificationAgent
from medical_feedback.src.feedback_agent import MedicalFeedbackAgent
from pipeline_setup import PipelineManager

@pytest.fixture
def verification_data():
    return {
        'id': 'test_ver_123',
        'name': 'John Doe',
        'dob': '1990-01-01',
        'address': '123 Main St, City, State 12345'
    }

@pytest.fixture
def medical_visit_data():
    return {
        'visit_id': 'visit_123',
        'patient_name': 'Jane Doe',
        'visit_date': '2024-03-15',
        'department': 'Cardiology'
    }

@pytest.mark.asyncio
async def test_id_verification_flow():
    """Test the ID verification conversation flow"""
    agent = IDVerificationAgent()
    
    # Mock the session
    mock_session = Mock()
    mock_session.say = Mock()
    agent.session = mock_session
    
    # Start verification
    await agent.start_verification("+1234567890", "+0987654321", verification_data())
    
    # Test each step of the conversation
    responses = [
        "John Doe",  # Name verification
        "1990-01-01",  # DOB verification
        "123 Main St, City, State 12345"  # Address verification
    ]
    
    for response in responses:
        result = await agent.handle_response(response)
        assert 'verified' in result
    
    # Check final status
    status = await agent.get_verification_status()
    assert status['all_fields_verified'] is True
    assert status['is_complete'] is True

@pytest.mark.asyncio
async def test_medical_feedback_flow():
    """Test the medical feedback conversation flow"""
    agent = MedicalFeedbackAgent()
    
    # Mock the session
    mock_session = Mock()
    mock_session.say = Mock()
    agent.session = mock_session
    
    # Start feedback call
    await agent.start_feedback_call("+1234567890", "+0987654321", medical_visit_data())
    
    # Test each step of the conversation
    responses = [
        "Yes",  # Confirm visit
        "5",    # Rate experience
        "4",    # Service quality
        "The staff was very professional"  # Improvement feedback
    ]
    
    for response in responses:
        result = await agent.handle_response(response)
        assert result['response_recorded'] is True
    
    # Check feedback summary
    summary = await agent.get_feedback_summary()
    assert summary['complete'] is True
    assert summary['average_rating'] == 4.5

@pytest.mark.asyncio
async def test_pipeline_integration():
    """Test the real-time pipeline setup"""
    pipeline = await PipelineManager.create_pipeline()
    assert pipeline is not None
    
    # Test job context creation
    context = PipelineManager.create_job_context(
        room_id="test_room",
        auth_token="test_token",
        agent_name="Test Agent"
    )
    assert context is not None
    assert context.room_options.room_id == "test_room"

@pytest.mark.asyncio
async def test_conversation_history():
    """Test conversation history tracking"""
    # Test ID Verification Agent
    ver_agent = IDVerificationAgent()
    await ver_agent.handle_response("Test response 1")
    history = await ver_agent.get_conversation_history()
    assert len(history) == 1
    assert history[0]["content"] == "Test response 1"
    
    # Test Medical Feedback Agent
    med_agent = MedicalFeedbackAgent()
    await med_agent.handle_response("Test response 2")
    history = await med_agent.get_conversation_history()
    assert len(history) == 1
    assert history[0]["content"] == "Test response 2"

if __name__ == "__main__":
    pytest.main(["-v", "test_agents.py"])
