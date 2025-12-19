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

from ramalama.logger import logger


class LlamaServerAPI:
    """API client for llama.cpp server operations."""

    def __init__(self, base_url: str):
        """Initialize the llama.cpp server API client.

        Args:
            base_url: Base URL of the server (e.g., "http://127.0.0.1:8080/v1")
        """
        # Normalize URL - remove /v1 suffix for slot operations
        self.base_url = base_url
        if base_url.endswith('/v1'):
            self.raw_url = base_url[:-3]
        elif '/v1/' in base_url:
            self.raw_url = base_url.replace('/v1/', '/')
        else:
            self.raw_url = base_url

    def get_context_size(self, timeout: float = 2.0) -> int:
        """Query the server to get the actual context size.

        Args:
            timeout: Request timeout in seconds

        Returns:
            Context size in tokens (defaults to 500 if unable to query)
        """
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

    def clear_slot_cache(self, slot_id: int = 0, timeout: float = 5.0) -> bool:
        """Clear the KV cache for a specific slot.

        This is useful when context is exceeded and we need to start fresh
        with a reduced conversation history.

        Args:
            slot_id: Slot ID to clear (default: 0)
            timeout: Request timeout in seconds

        Returns:
            True if successful, False otherwise
        """
        slot_url = f"{self.raw_url}/slots/{slot_id}?action=erase"

        logger.debug(f"Clearing slot cache at: {slot_url}")

        try:
            request = urllib.request.Request(
                slot_url,
                method="POST",
                headers={"Content-Type": "application/json"}
            )

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

    def get_slot_info(self, slot_id: int = 0, timeout: float = 2.0) -> dict | None:
        """Get information about a specific slot.

        Args:
            slot_id: Slot ID to query
            timeout: Request timeout in seconds

        Returns:
            Slot info dict or None if failed
        """
        try:
            slots_url = f"{self.raw_url}/slots"

            with urllib.request.urlopen(slots_url, timeout=timeout) as response:
                slots_data = json.loads(response.read())
                if slots_data and len(slots_data) > slot_id:
                    return slots_data[slot_id]
        except Exception as e:
            logger.debug(f"Failed to get slot info: {e}")

        return None

    def health_check(self, timeout: float = 2.0) -> bool:
        """Check if the server is healthy and ready.

        Args:
            timeout: Request timeout in seconds

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            health_url = f"{self.raw_url}/health"

            with urllib.request.urlopen(health_url, timeout=timeout) as response:
                if response.status == 200:
                    return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")

        return False

    def wait_for_ready(self, timeout: float = 30.0, check_interval: float = 0.5) -> bool:
        """Wait for the server to become ready.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: Time between health checks

        Returns:
            True if server became ready, False if timeout
        """
        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            if self.health_check(timeout=check_interval):
                return True
            time.sleep(check_interval)

        return False


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
    time.sleep(0.5)

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
