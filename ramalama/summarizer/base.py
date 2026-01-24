"""Base class for context management strategies."""

from abc import ABC, abstractmethod

from ramalama.logger import logger


class ContextStrategy(ABC):
    """Abstract base class for conversation context management strategies.

    Implementations handle reducing conversation history when context limits are reached.
    """

    def __init__(self, max_context_messages: int = 6):
        """Initialize the context strategy.

        Args:
            max_context_messages: Number of recent messages to preserve in full
        """
        self.max_context_messages = max_context_messages

    @abstractmethod
    def reduce_context(self, conversation_history: list[dict], n_ctx: int) -> list[dict]:
        """Reduce conversation history to fit within context limits.

        Args:
            conversation_history: List of message dicts with 'role' and 'content'
            n_ctx: Maximum context size in tokens

        Returns:
            Reduced conversation history
        """
        pass

    def estimate_tokens(self, text: str) -> int:
        """Rough estimate of token count from text (approx 4 chars per token)."""
        return len(text) // 4

    def estimate_history_tokens(self, history: list[dict]) -> int:
        """Estimate total tokens in conversation history."""
        total = 0
        for msg in history:
            total += self.estimate_tokens(msg.get("content", ""))
            total += 4  # Overhead for role, formatting
        return total

    def consolidate_consecutive_user_messages(self, history: list[dict]) -> list[dict]:
        """Merge only trailing consecutive user messages into one.

        This fixes pathological states where previous requests failed and user
        messages accumulated at the end without a response. We only consolidate
        trailing messages to preserve the semantic meaning of earlier exchanges.

        Args:
            history: Conversation history

        Returns:
            Consolidated history with trailing user messages merged
        """
        if len(history) < 2:
            return history

        # Count trailing consecutive user messages
        trailing_user_count = 0
        for msg in reversed(history):
            if msg.get("role") == "user":
                trailing_user_count += 1
            else:
                break

        # If 0 or 1 trailing user messages, nothing to consolidate
        if trailing_user_count <= 1:
            return history

        # Keep everything before the trailing user messages, then merge them
        consolidated = history[:-trailing_user_count]
        trailing_messages = history[-trailing_user_count:]
        merged_content = "\n\n".join(msg.get("content", "") for msg in trailing_messages)
        consolidated.append({"role": "user", "content": merged_content})
        logger.debug(f"Consolidated {trailing_user_count} trailing consecutive user messages")

        return consolidated

    def separate_messages(self, history: list[dict]) -> tuple[list[dict], list[dict]]:
        """Separate system messages from conversation messages.

        Args:
            history: Conversation history

        Returns:
            Tuple of (system_messages, conversation_messages)
        """
        system_messages = []
        conversation_messages = []

        for msg in history:
            if msg.get("role") == "system":
                system_messages.append(msg)
            else:
                conversation_messages.append(msg)

        return system_messages, conversation_messages
