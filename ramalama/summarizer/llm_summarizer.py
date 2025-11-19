"""LLM-based summarization strategy for context management.

This approach uses the LLM itself to create intelligent summaries of conversation history.
More expensive (requires LLM inference) but can produce more coherent summaries.

Features:
- Cumulative summarization (incorporates previous summaries)
- Configurable target summary size
- Fallback to basic extraction if LLM fails
"""

import json
import urllib.error
import urllib.request

from ramalama.logger import logger
from ramalama.summarizer.base import ContextStrategy


class LLMSummarizer(ContextStrategy):
    """Context management using LLM-based summarization.

    Uses the model to create intelligent summaries of older conversation history.
    """

    # Prefix to identify summary messages vs original system prompts
    SUMMARY_PREFIX = "Previous conversation summary:"

    def __init__(
        self,
        max_context_messages: int = 6,
        target_summary_ratio: float = 0.25,
        api_url: str | None = None,
        model: str | None = None,
        timeout: int = 30,
        max_tokens: int | None = None,
    ):
        """Initialize LLM summarization strategy.

        Args:
            max_context_messages: Number of recent messages to keep after summarization
            target_summary_ratio: Target summary size as ratio of context (default: 0.25 = 25%)
            api_url: URL for the LLM API (required for summarization)
            model: Model name to use for summarization
            timeout: Timeout for summarization request
            max_tokens: Maximum tokens for summary output (overrides target_summary_ratio if set)
        """
        super().__init__(max_context_messages)
        self.target_summary_ratio = target_summary_ratio
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    def reduce_context(self, conversation_history: list[dict], n_ctx: int) -> list[dict]:
        """Reduce conversation history using LLM summarization.

        Args:
            conversation_history: List of message dicts
            n_ctx: Maximum context size in tokens

        Returns:
            Reduced conversation history with summary
        """
        if len(conversation_history) < 2:
            logger.debug("Not enough messages to summarize")
            return conversation_history

        # First, consolidate any consecutive user messages
        history = self.consolidate_consecutive_user_messages(conversation_history)

        # Separate messages into categories
        original_system_prompt = None
        previous_summary = None
        conversation_messages = []

        for msg in history:
            if self._is_summary_message(msg):
                previous_summary = self._extract_summary_content(msg.get("content", ""))
            elif msg.get("role") == "system" and original_system_prompt is None:
                original_system_prompt = msg
            elif msg.get("role") in ("user", "assistant"):
                conversation_messages.append(msg)

        # Need at least something to summarize
        if len(conversation_messages) < 2 and not previous_summary:
            logger.debug("Not enough content to summarize")
            return history

        # Keep the last user message as current context
        recent_msgs = [conversation_messages[-1]] if conversation_messages else []
        messages_to_summarize = conversation_messages[:-1] if len(conversation_messages) > 1 else []

        if not messages_to_summarize and not previous_summary:
            logger.debug("Only current message - cannot reduce further")
            return history

        # Calculate target sizes
        if self.max_tokens is not None:
            target_summary_tokens = self.max_tokens
        else:
            target_summary_tokens = int(n_ctx * self.target_summary_ratio)
        target_summary_chars = target_summary_tokens * 4
        max_input_chars = int(n_ctx * 0.4 * 4)

        logger.debug(f"Context: {n_ctx}, target summary: {target_summary_chars} chars")

        # Try LLM summarization
        summary = self._get_llm_summary(
            messages_to_summarize,
            previous_summary,
            target_summary_chars,
            max_input_chars,
        )

        if not summary:
            # Fallback to basic extraction
            summary = self._create_basic_summary(
                messages_to_summarize,
                previous_summary,
                target_summary_chars,
            )

        # Ensure summary isn't too long
        if len(summary) > target_summary_chars:
            summary = summary[: target_summary_chars - 3] + "..."

        # Build new history
        new_history = []

        if original_system_prompt:
            new_history.append(original_system_prompt)

        new_history.append({"role": "system", "content": f"{self.SUMMARY_PREFIX} {summary}"})

        new_history.extend(recent_msgs)

        logger.debug(f"Summarized: {len(conversation_history)} messages -> {len(new_history)} messages")
        return new_history

    def _is_summary_message(self, msg: dict) -> bool:
        """Check if a message is a summary message (vs original system prompt)."""
        if msg.get("role") != "system":
            return False
        content = msg.get("content", "")
        return content.startswith(self.SUMMARY_PREFIX) or content.startswith("Previous conversation:")

    def _extract_summary_content(self, content: str) -> str:
        """Extract the actual summary text from a summary message."""
        if content.startswith(self.SUMMARY_PREFIX):
            return content[len(self.SUMMARY_PREFIX) :].strip()
        if content.startswith("Previous conversation:"):
            return content[len("Previous conversation:") :].strip()
        return content

    def _get_llm_summary(
        self,
        messages: list[dict],
        previous_summary: str | None,
        target_chars: int,
        max_input_chars: int,
    ) -> str | None:
        """Get summary from LLM.

        Args:
            messages: Messages to summarize
            previous_summary: Previous summary to incorporate
            target_chars: Target length for summary
            max_input_chars: Max chars to include in prompt

        Returns:
            Summary string or None if failed
        """
        if not self.api_url:
            logger.warning("No API URL configured for LLM summarization")
            return None

        # Build content to summarize
        content_parts = []

        if previous_summary:
            content_parts.append(f"[Previous context: {previous_summary}]")

        # Add messages, truncating if needed
        total_chars = sum(len(m.get("content", "")) for m in messages)
        total_chars += len(previous_summary) if previous_summary else 0

        if total_chars > max_input_chars:
            remaining = max_input_chars - (len(previous_summary) if previous_summary else 0)
            chars_per_msg = max(100, remaining // max(1, len(messages)))

            for msg in messages:
                content = msg['content']
                if len(content) > chars_per_msg:
                    content = content[:chars_per_msg] + "..."
                content_parts.append(f"{msg['role']}: {content}")
        else:
            for msg in messages:
                content_parts.append(f"{msg['role']}: {msg['content']}")

        conversation_text = "\n".join(content_parts)
        target_words = max(20, int(target_chars // 6))  # Rough word estimate

        prompt = {
            "role": "user",
            "content": (
                f"Summarize this conversation in EXACTLY {target_words} words or fewer. "
                f"Be extremely brief. Only include essential facts (names, key topics). "
                f"Output ONLY the summary:\n\n{conversation_text}\n\nBrief summary:"
            ),
        }

        try:
            data = {
                "stream": False,
                "messages": [prompt],
            }
            if self.model:
                data["model"] = self.model

            request = urllib.request.Request(
                f"{self.api_url}/chat/completions",
                data=json.dumps(data).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read())
                summary = result['choices'][0]['message']['content'].strip()

                # Basic validation - summary should have meaningful content
                if len(summary) < 20:
                    logger.warning(f"LLM returned too short summary: {summary[:100]}")
                    return None

                return summary

        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")
            return None

    def _create_basic_summary(
        self,
        messages: list[dict],
        previous_summary: str | None,
        max_chars: int,
    ) -> str:
        """Create basic summary by extracting key content (fallback).

        Args:
            messages: Messages to summarize
            previous_summary: Previous summary to incorporate
            max_chars: Maximum summary length

        Returns:
            Basic summary string
        """
        max_chars = min(max_chars, 300)  # Hard cap for safety
        summary_parts = []

        if previous_summary:
            prev_max = min(100, max_chars // 4)
            if len(previous_summary) > prev_max:
                summary_parts.append(f"[Prior: {previous_summary[:prev_max]}...]")
            else:
                summary_parts.append(f"[Prior: {previous_summary}]")

        remaining_chars = max_chars - sum(len(p) for p in summary_parts)
        chars_per_msg = max(30, remaining_chars // max(1, len(messages)))

        for msg in messages:
            role = msg['role'][:1].upper()
            content = msg['content'][:chars_per_msg]
            if len(msg['content']) > chars_per_msg:
                content += "..."
            summary_parts.append(f"{role}: {content}")

        result = " | ".join(summary_parts)
        if len(result) > max_chars:
            result = result[: max_chars - 3] + "..."

        return result
