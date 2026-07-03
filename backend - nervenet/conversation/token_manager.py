from conversation.constants import (
    CLAUDE_INPUT_COST_PER_TOKEN,
    CLAUDE_OUTPUT_COST_PER_TOKEN,
    SUMMARIZATION_TOKEN_THRESHOLD,
    CHARS_PER_TOKEN_ESTIMATE
)

class TokenManager:
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate the estimated USD cost based on token counts and Claude pricing."""
        input_cost = prompt_tokens * CLAUDE_INPUT_COST_PER_TOKEN
        output_cost = completion_tokens * CLAUDE_OUTPUT_COST_PER_TOKEN
        return input_cost + output_cost

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count of raw text using typical character density heuristic."""
        if not text:
            return 0
        return int(len(text) / CHARS_PER_TOKEN_ESTIMATE)

    def should_summarize(self, total_accumulated_tokens: int) -> bool:
        """Determine whether the accumulated token count crosses the threshold for summarization."""
        return total_accumulated_tokens >= SUMMARIZATION_TOKEN_THRESHOLD
