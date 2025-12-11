"""Simple Observation Masking strategy for context management.

Based on: https://medium.com/@balajibal/agent-context-management-why-simple-observation-masking-beats-llm-summarisation

This approach:
1. Keeps the last N messages in full (preserving recent context)
2. Extracts key info from older messages as a brief note
3. Removes older messages entirely

Benefits:
- No LLM call needed (fast, deterministic)
- Predictable context usage
- Recent context always preserved
"""

from ramalama.logger import logger
from ramalama.summarizer.base import ContextStrategy


class ObservationMasking(ContextStrategy):
    """Context management using simple observation masking.

    Keeps recent messages in full, masks/removes older ones with a brief context note.
    """

    def __init__(self, max_context_messages: int = 6):
        """Initialize observation masking strategy.

        Args:
            max_context_messages: Number of recent messages to keep in full (default: 6 = 3 exchanges)
        """
        super().__init__(max_context_messages)

    def reduce_context(self, conversation_history: list[dict], n_ctx: int) -> list[dict]:
        """Reduce conversation history using observation masking.

        Args:
            conversation_history: List of message dicts
            n_ctx: Maximum context size in tokens

        Returns:
            Reduced conversation history with recent messages preserved
        """
        if len(conversation_history) < 2:
            logger.debug("Not enough messages to mask")
            return conversation_history

        # First, consolidate any consecutive user messages
        history = self.consolidate_consecutive_user_messages(conversation_history)

        # Separate system messages from conversation
        system_messages, conversation_messages = self.separate_messages(history)

        if len(conversation_messages) <= self.max_context_messages:
            # Not enough messages to mask, try truncating long messages instead
            return self._truncate_long_messages(history, n_ctx)

        # Split into old (to mask/remove) and recent (to keep)
        old_messages = conversation_messages[:-self.max_context_messages]
        recent_messages = conversation_messages[-self.max_context_messages:]

        # Build new history
        new_history = []

        # Keep first system message (but limit to one to save space)
        if system_messages:
            new_history.append(system_messages[0])

        # Calculate available space for context note
        recent_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in recent_messages)
        system_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in new_history)
        available_for_old = n_ctx - recent_tokens - system_tokens - 100  # Reserve 100 for response

        if available_for_old > 50:
            # We have some room - keep a brief context note about old messages
            key_info = self._extract_key_info(old_messages)
            if key_info:
                context_note = f"[Earlier in conversation: {key_info}]"
                # Truncate if needed
                max_note_chars = available_for_old * 4
                if len(context_note) > max_note_chars:
                    context_note = context_note[:max_note_chars - 4] + "...]"
                new_history.append({
                    "role": "system",
                    "content": context_note
                })

        # Add recent messages in full
        new_history.extend(recent_messages)

        logger.debug(f"Masked conversation: {len(conversation_history)} messages -> {len(new_history)} messages")
        return new_history

    def _extract_key_info(self, messages: list[dict]) -> str:
        """Extract key information from messages for context note.

        Looks for names, topics, and important facts without using LLM.

        Args:
            messages: List of old messages to extract info from

        Returns:
            Brief string with key information
        """
        # Simple extraction - just grab first few words of each exchange
        snippets = []
        for msg in messages[-4:]:  # Last 4 old messages max
            content = msg.get("content", "")
            # Get first 50 chars or first sentence
            snippet = content[:50].split('.')[0].split('?')[0].split('!')[0]
            if len(content) > len(snippet):
                snippet += "..."
            if snippet.strip():
                snippets.append(snippet.strip())

        if snippets:
            return "; ".join(snippets[:3])  # Max 3 snippets
        return ""

    def _truncate_long_messages(self, history: list[dict], n_ctx: int) -> list[dict]:
        """Truncate individual long messages when we can't mask more.

        Args:
            history: Conversation history
            n_ctx: Maximum context size

        Returns:
            History with long messages truncated
        """
        modified = False
        max_msg_tokens = n_ctx // 4  # No single message should exceed 25% of context
        result = []

        for i, msg in enumerate(history):
            content = msg.get("content", "")
            msg_tokens = self.estimate_tokens(content)

            # Don't truncate the last message (current user input)
            if i < len(history) - 1 and msg_tokens > max_msg_tokens:
                # Truncate this message
                max_chars = max_msg_tokens * 4
                new_content = content[:max_chars - 20] + "... [truncated]"
                result.append({"role": msg["role"], "content": new_content})
                modified = True
                logger.debug(f"Truncated message {i} from {msg_tokens} to ~{max_msg_tokens} tokens")
            else:
                result.append(msg)

        if modified:
            logger.debug("Truncated long messages to fit context")

        return result
