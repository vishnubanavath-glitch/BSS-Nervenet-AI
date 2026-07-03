import pytest
from conversation.token_manager import TokenManager
from conversation.constants import CLAUDE_INPUT_COST_PER_TOKEN, CLAUDE_OUTPUT_COST_PER_TOKEN

def test_token_manager():
    tm = TokenManager()
    
    # Cost calculations
    cost = tm.calculate_cost(prompt_tokens=1000, completion_tokens=500)
    expected_cost = (1000 * CLAUDE_INPUT_COST_PER_TOKEN) + (500 * CLAUDE_OUTPUT_COST_PER_TOKEN)
    assert pytest.approx(cost) == expected_cost
    
    # Token estimation checks
    est = tm.estimate_tokens("This is text")
    assert est == 3  # 12 chars / 4
    
    # Threshold checks
    assert tm.should_summarize(100) is False
    assert tm.should_summarize(5000) is True
