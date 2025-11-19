"""Llama.cpp server API interactions.

This module handles communication with the llama.cpp server for operations like:
- Clearing slot cache
- Getting server info (context size, etc.)
- Health checks

These operations are specific to llama.cpp server and may need adaptation for other backends.
"""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from ramalama.logger import logger

__all__ = [
    "ServerTimeouts",
    "DEFAULT_TIMEOUTS",
    "LlamaServerAPI",
    "ChatClient",
    "handle_context_overflow",
]


@dataclass
class ServerTimeouts:
    """Configuration for server operation timeouts."""

    # Timeout for quick queries (context size, slot info, health)
    query: float = 2.0
    # Timeout for cache operations
    cache_clear: float = 5.0
    # Timeout for waiting for server ready
    wait_ready: float = 30.0
    # Interval between health checks when waiting
    health_check_interval: float = 0.5
    # Pause after cache clear for server stabilization
    post_cache_clear: float = 0.5


# Default timeout configuration
DEFAULT_TIMEOUTS = ServerTimeouts()


class LlamaServerAPI:
    """API client for llama.cpp server operations."""

    def __init__(self, base_url: str, timeouts: ServerTimeouts | None = None):
        """Initialize the llama.cpp server API client.

        Args:
            base_url: Base URL of the server (e.g., "http://127.0.0.1:8080/v1")
            timeouts: Timeout configuration (uses defaults if not provided)
        """
        # Normalize URL - remove /v1 suffix for slot operations
        self.base_url = base_url
        if base_url.endswith('/v1'):
            self.raw_url = base_url[:-3]
        elif '/v1/' in base_url:
            self.raw_url = base_url.replace('/v1/', '/')
        else:
            self.raw_url = base_url

        self.timeouts = timeouts or DEFAULT_TIMEOUTS

    def get_context_size(self, timeout: float | None = None) -> int:
        """Query the server to get the actual context size.

        Args:
            timeout: Request timeout in seconds (uses configured default if None)

        Returns:
            Context size in tokens (defaults to 500 if unable to query)
        """
        timeout = timeout if timeout is not None else self.timeouts.query

        try:
            slots_url = f"{self.raw_url}/slots"

            with urllib.request.urlopen(slots_url, timeout=timeout) as response:
                slots_data = json.loads(response.read())
                if slots_data and len(slots_data) > 0:
                    n_ctx = slots_data[0].get('n_ctx', 500)
                    logger.debug(f"Retrieved context size from server: {n_ctx}")
                    return n_ctx
        except Exception as e:
            logger.debug(f"Failed to get context size from server: {e}")

        # Default fallback
        return 500

    def clear_slot_cache(self, slot_id: int = 0, timeout: float | None = None) -> bool:
        """Clear the KV cache for a specific slot.

        This is useful when context is exceeded and we need to start fresh
        with a reduced conversation history.

        Args:
            slot_id: Slot ID to clear (default: 0)
            timeout: Request timeout in seconds (uses configured default if None)

        Returns:
            True if successful, False otherwise
        """
        timeout = timeout if timeout is not None else self.timeouts.cache_clear
        slot_url = f"{self.raw_url}/slots/{slot_id}?action=erase"

        logger.debug(f"Clearing slot cache at: {slot_url}")

        try:
            request = urllib.request.Request(slot_url, method="POST", headers={"Content-Type": "application/json"})

            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = response.read()
                logger.debug(f"Slot cache cleared: {result}")
                return True

        except urllib.error.HTTPError as e:
            logger.warning(f"HTTP error clearing slot cache: {e.code} {e.reason}")
            return False
        except Exception as e:
            logger.warning(f"Failed to clear slot cache: {e}")
            return False

    def get_slot_info(self, slot_id: int = 0, timeout: float | None = None) -> dict | None:
        """Get information about a specific slot.

        Args:
            slot_id: Slot ID to query
            timeout: Request timeout in seconds (uses configured default if None)

        Returns:
            Slot info dict or None if failed
        """
        timeout = timeout if timeout is not None else self.timeouts.query

        try:
            slots_url = f"{self.raw_url}/slots"

            with urllib.request.urlopen(slots_url, timeout=timeout) as response:
                slots_data = json.loads(response.read())
                if slots_data and len(slots_data) > slot_id:
                    return slots_data[slot_id]
        except Exception as e:
            logger.debug(f"Failed to get slot info: {e}")

        return None

    def health_check(self, timeout: float | None = None) -> bool:
        """Check if the server is healthy and ready.

        Args:
            timeout: Request timeout in seconds (uses configured default if None)

        Returns:
            True if server is healthy, False otherwise
        """
        timeout = timeout if timeout is not None else self.timeouts.query

        try:
            health_url = f"{self.raw_url}/health"

            with urllib.request.urlopen(health_url, timeout=timeout) as response:
                if response.status == 200:
                    return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")

        return False

    def wait_for_ready(
        self,
        timeout: float | None = None,
        check_interval: float | None = None,
    ) -> bool:
        """Wait for the server to become ready.

        Args:
            timeout: Maximum time to wait in seconds (uses configured default if None)
            check_interval: Time between health checks (uses configured default if None)

        Returns:
            True if server became ready, False if timeout
        """
        timeout = timeout if timeout is not None else self.timeouts.wait_ready
        check_interval = check_interval if check_interval is not None else self.timeouts.health_check_interval

        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            if self.health_check(timeout=check_interval):
                return True
            time.sleep(check_interval)

        return False

    def post_chat(
        self,
        messages: list[dict],
        stream: bool = True,
        model: str | None = None,
        timeout: float | None = None,
    ):
        """Post a chat completion request to the server.

        Args:
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream the response
            model: Model name (optional)
            timeout: Request timeout in seconds

        Returns:
            Response object (urllib response for streaming, or parsed JSON for non-streaming)
        """
        timeout = timeout if timeout is not None else self.timeouts.query

        data = {
            "stream": stream,
            "messages": messages,
        }
        if model:
            data["model"] = model

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        response = urllib.request.urlopen(request, timeout=timeout)

        if stream:
            return response
        else:
            result = json.loads(response.read())
            response.close()
            return result

    def reduce_context(
        self,
        messages: list[dict],
        context_strategy,
        slot_id: int = 0,
    ) -> list[dict]:
        """Reduce conversation context using the provided strategy.

        Args:
            messages: Current conversation history
            context_strategy: ContextStrategy instance to use
            slot_id: Slot ID to get context size from

        Returns:
            Reduced message list
        """
        n_ctx = self.get_context_size()
        return context_strategy.reduce_context(messages, n_ctx)

    def handle_context_overflow(
        self,
        slot_id: int,
        messages: list[dict],
        error: Exception | str | None,
        context_strategy=None,
        verbose: bool = True,
    ) -> tuple[list[dict], bool]:
        """Handle context overflow by clearing cache and reducing history.

        Args:
            slot_id: Slot ID to clear
            messages: Current conversation history
            error: The error that triggered overflow handling
            context_strategy: ContextStrategy instance (required if reducing context)
            verbose: Whether to print status messages

        Returns:
            Tuple of (reduced_messages, success)
        """
        if verbose:
            print("\nContext size exceeded. Processing...", flush=True)

        # Clear the cache
        if verbose:
            print("Clearing server cache...", flush=True)

        cache_cleared = self.clear_slot_cache(slot_id)
        if not cache_cleared:
            logger.warning("Failed to clear slot cache")
            if verbose:
                print("Warning: Could not clear server cache", flush=True)

        time.sleep(self.timeouts.post_cache_clear)

        # Reduce context if strategy provided
        if context_strategy is not None:
            reduced = self.reduce_context(messages, context_strategy, slot_id)
            if len(reduced) < len(messages):
                if verbose:
                    print(f"Context reduced: {len(messages)} -> {len(reduced)} messages", flush=True)
                if verbose:
                    print("Ready to continue...", flush=True)
                return reduced, True

        # Fallback: keep only last user message
        logger.warning("Cannot reduce context - clearing history")
        last_user = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg
                break
        reduced = [last_user] if last_user else []
        if verbose:
            print("Conversation history cleared.", flush=True)
            print("Ready to continue...", flush=True)
        return reduced, True


class ChatClient:
    """High-level chat client that wraps LlamaServerAPI with context management."""

    def __init__(
        self,
        api: LlamaServerAPI,
        context_strategy=None,
        model: str | None = None,
    ):
        """Initialize the chat client.

        Args:
            api: LlamaServerAPI instance
            context_strategy: ContextStrategy for handling overflow (optional)
            model: Model name for requests (optional)
        """
        self.api = api
        self.context_strategy = context_strategy
        self.model = model
        self.conversation_history: list[dict] = []

    def chat(
        self,
        messages: list[dict],
        stream: bool = True,
        handle_overflow: bool = True,
    ):
        """Send a chat request with automatic overflow handling.

        Args:
            messages: Messages to send
            stream: Whether to stream the response
            handle_overflow: Whether to handle context overflow automatically

        Returns:
            Response from the server
        """
        self.conversation_history = messages

        try:
            return self.api.post_chat(messages, stream=stream, model=self.model)
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode('utf-8', errors='replace')
            except Exception:
                pass

            # Check for context overflow error
            is_context_error = "context" in error_body.lower() or "too long" in error_body.lower() or e.code == 400

            if handle_overflow and is_context_error and self.context_strategy:
                # Handle overflow and retry
                self.conversation_history, success = self.api.handle_context_overflow(
                    slot_id=0,
                    messages=self.conversation_history,
                    error=e,
                    context_strategy=self.context_strategy,
                )
                if success:
                    return self.api.post_chat(self.conversation_history, stream=stream, model=self.model)

            raise


def handle_context_overflow(
    server_api: LlamaServerAPI,
    conversation_history: list[dict],
    context_strategy,
    verbose: bool = True,
) -> tuple[list[dict], bool]:
    """Handle context size overflow by clearing cache and reducing history.

    Args:
        server_api: LlamaServerAPI instance
        conversation_history: Current conversation history
        context_strategy: ContextStrategy instance to use for reduction
        verbose: Whether to print status messages

    Returns:
        Tuple of (reduced_history, success)
    """
    if verbose:
        print("\nContext size exceeded. Processing...", flush=True)

    # Step 1: Clear the server cache
    if verbose:
        print("Clearing server cache...", flush=True)

    cache_cleared = server_api.clear_slot_cache()
    if not cache_cleared:
        logger.warning("Failed to clear slot cache")
        if verbose:
            print("Warning: Could not clear server cache", flush=True)

    # Brief pause for server to stabilize
    time.sleep(server_api.timeouts.post_cache_clear)

    # Step 2: Reduce conversation history
    n_ctx = server_api.get_context_size()
    reduced_history = context_strategy.reduce_context(conversation_history, n_ctx)

    if len(reduced_history) < len(conversation_history):
        if verbose:
            print(f"Context reduced: {len(conversation_history)} -> {len(reduced_history)} messages", flush=True)
        success = True
    else:
        # Couldn't reduce - fallback to keeping only last user message
        logger.warning("Cannot reduce context - clearing history")
        last_user = None
        for msg in reversed(conversation_history):
            if msg.get("role") == "user":
                last_user = msg
                break
        reduced_history = [last_user] if last_user else []
        if verbose:
            print("Conversation history cleared.", flush=True)
        success = True

    if verbose:
        print("Ready to continue...", flush=True)

    return reduced_history, success
