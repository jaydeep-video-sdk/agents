import pytest
import asyncio
from unittest.mock import Mock, patch
from .agent import OutboundCallAgent
from .config import TEST_DATA

@pytest.mark.asyncio
async def test_verification_agent():
    """Test the verification agent conversation flow"""
    # Create verification agent
    agent = OutboundCallAgent('verification')
    
    # Mock the session
    mock_session = Mock()
    mock_session.say = Mock()
    agent.session = mock_session
    
    # Start conversation
    await agent.start_conversation(TEST_DATA['verification'])
    
    # Verify greeting
    mock_session.say.assert_called_with(agent.conversation_flow['greeting']['message'])
    
    # Test successful verification flow
    test_responses = [
        ("John Doe", True),  # Correct name
        ("01/15/1990", True),  # Correct DOB
        ("123 Main St, City, State 12345", True)  # Correct address
    ]
    
    for response, should_verify in test_responses:
        result = await agent.handle_response(response)
        assert result['verified'] == should_verify
    
    # Verify completion
    status = await agent.get_conversation_status()
    assert status['is_complete'] is True
    
    # Test failed verification
    agent = OutboundCallAgent('verification')
    agent.session = mock_session
    await agent.start_conversation(TEST_DATA['verification'])
    
    # Test with wrong name
    result = await agent.handle_response("Jane Doe")
    assert result['verified'] is False
    assert result['next_step'] == 'confirm_identity'  # Should stay on same step

@pytest.mark.asyncio
async def test_medical_feedback_agent():
    """Test the medical feedback agent conversation flow"""
    # Create medical feedback agent
    agent = OutboundCallAgent('medical_feedback')
    
    # Mock the session
    mock_session = Mock()
    mock_session.say = Mock()
    agent.session = mock_session
    
    # Start conversation
    await agent.start_conversation(TEST_DATA['medical_feedback'])
    
    # Verify greeting
    mock_session.say.assert_called_with(agent.conversation_flow['greeting']['message'])
    
    # Test feedback flow
    test_responses = [
        "Yes",  # Confirm visit
        "5",    # Rate experience
        "4",    # Service quality
        "The staff was very professional"  # Improvement feedback
    ]
    
    for response in test_responses:
        result = await agent.handle_response(response)
        assert 'error' not in result
    
    # Get conversation summary
    summary = await agent.get_conversation_summary()
    assert summary['type'] == 'medical_feedback'
    assert summary['completed'] is True
    assert summary['average_rating'] == 4.5  # Average of 5 and 4

@pytest.mark.asyncio
async def test_conversation_history():
    """Test conversation history tracking"""
    # Test both agent types
    for agent_type in ['verification', 'medical_feedback']:
        agent = OutboundCallAgent(agent_type)
        mock_session = Mock()
        mock_session.say = Mock()
        agent.session = mock_session
        
        # Start conversation
        await agent.start_conversation(TEST_DATA[agent_type])
        
        # Add some responses
        test_responses = ["Test response 1", "Test response 2"]
        for response in test_responses:
            await agent.handle_response(response)
        
        # Check history
        assert len(agent.conversation_history) == len(test_responses)
        for i, response in enumerate(test_responses):
            assert agent.conversation_history[i]['content'] == response
            assert agent.conversation_history[i]['role'] == 'user'

if __name__ == "__main__":
    pytest.main(["-v", "test_agent.py"])
