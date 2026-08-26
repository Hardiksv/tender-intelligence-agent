import pytest
from unittest.mock import patch, MagicMock
from app.llm.client import LiteLLMClient

class MockMessage:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]
        self.usage = None

def test_truncation_detection():
    client = LiteLLMClient()
    
    # Mock litellm.completion to return a truncated response on first call, 
    # then a success on second call
    mock_responses = [
        MockResponse("<think> Here is my reasoning... wait, I got cut off"),
        MockResponse("<think> Reasoning </think> Actual Answer")
    ]
    
    with patch('app.llm.client.litellm.completion', side_effect=mock_responses):
        res = client.generate("Test prompt")
        # Should catch the error on the first and succeed on the second attempt
        assert res["content"] == "Actual Answer"

def test_truncation_all_fail():
    client = LiteLLMClient()
    
    mock_responses = [
        MockResponse("<think> Truncated 1"),
        MockResponse("<think> Truncated 2"),
        MockResponse("<think> Truncated 3"),
        MockResponse("<think> Truncated 4"),
        MockResponse("<think> Truncated 5")
    ]
    
    with patch('app.llm.client.litellm.completion', side_effect=mock_responses):
        with pytest.raises(RuntimeError, match="truncated mid-reasoning"):
            client.generate("Test prompt")
