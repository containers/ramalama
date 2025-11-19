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
        """Merge consecutive user messages into one to fix pathological states.

        This can happen if previous requests failed and user messages accumulated.

        Args:
            history: Conversation history

        Returns:
            Consolidated history
        """
        if len(history) < 2:
            return history

        consolidated = []
        pending_user_contents = []

        for msg in history:
            if msg.get("role") == "user":
                pending_user_contents.append(msg.get("content", ""))
            else:
                # Flush any accumulated user messages as a single message
                if pending_user_contents:
                    if len(pending_user_contents) == 1:
                        consolidated.append({"role": "user", "content": pending_user_contents[0]})
                    else:
                        # Merge multiple user messages
                        merged_content = "\n\n".join(pending_user_contents)
                        consolidated.append({"role": "user", "content": merged_content})
                        logger.debug(f"Consolidated {len(pending_user_contents)} consecutive user messages")
                    pending_user_contents = []
                consolidated.append(msg)

        # Don't forget trailing user messages
        if pending_user_contents:
            if len(pending_user_contents) == 1:
                consolidated.append({"role": "user", "content": pending_user_contents[0]})
            else:
                merged_content = "\n\n".join(pending_user_contents)
                consolidated.append({"role": "user", "content": merged_content})
                logger.debug(f"Consolidated {len(pending_user_contents)} trailing consecutive user messages")

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
