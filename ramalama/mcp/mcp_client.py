#!/usr/bin/env python3
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, cast

from ramalama.proxy_support import setup_proxy_support

logging.basicConfig(level=logging.INFO)

# Setup proxy support on module import
setup_proxy_support()


class PureMCPClient:
    """A pure Python MCP client that works with FastMCP servers."""

    def __init__(self, base_url: str, timeout: int = 30, retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.session_id: Optional[str] = None
        self.request_id = 0
        self.timeout = timeout
        self.retries = retries

    def _get_next_request_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def _do_request(self, request: urllib.request.Request):
        """Perform HTTP request with retries and timeout."""
        for attempt in range(1, self.retries + 1):
            try:
                return urllib.request.urlopen(request, timeout=self.timeout)
            except (urllib.error.URLError, TimeoutError) as e:
                logging.warning("Request failed (attempt %s/%s): %s", attempt, self.retries, e)
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)  # exponential backoff

    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a JSON-RPC request via HTTP POST."""
        message = {"jsonrpc": "2.0", "id": self._get_next_request_id(), "method": method, "params": params or {}}

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        data = json.dumps(message).encode('utf-8')
        request = urllib.request.Request(self.base_url, data=data, headers=headers, method='POST')

        try:
            with self._do_request(request) as response:
                if "mcp-session-id" in response.headers:
                    self.session_id = response.headers["mcp-session-id"]

                content_type = response.headers.get("content-type", "")
                if content_type.startswith("text/event-stream"):
                    return self._parse_sse_stream(response)
                else:
                    return self._validate_response(
                        json.loads(response.read().decode("utf-8")),
                        cast(int, message["id"]),
                    )

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else "No error body"
            logging.error("Error response %s: %s", e.code, error_body)
            raise

    def _validate_response(self, response: Dict[str, Any], expected_id: int) -> Dict[str, Any]:
        """Ensure response is valid JSON-RPC."""
        if response.get("jsonrpc") != "2.0":
            raise ValueError(f"Invalid JSON-RPC version: {response}")
        if response.get("id") != expected_id:
            raise ValueError(f"Mismatched response ID: {response}")
        return response

    def _parse_sse_stream(self, response) -> Dict[str, Any]:
        collected = ""
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if line.startswith("data: "):
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                collected += payload

        try:
            return json.loads(collected)
        except json.JSONDecodeError:
            logging.warning("Malformed SSE JSON: %s", collected)
            return {}

    def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Send a JSON-RPC notification (no response expected)."""
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}

        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        data = json.dumps(message).encode("utf-8")
        request = urllib.request.Request(self.base_url, data=data, headers=headers, method="POST")

        try:
            with self._do_request(request) as response:
                if response.status not in [200, 202]:
                    logging.warning("Notification returned unexpected status %s", response.status)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else "No error body"
            logging.error("Notification error %s: %s", e.code, error_body)

    # --- Public API ---

    def initialize(self) -> Dict[str, Any]:
        result = self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                "clientInfo": {"name": "pure-python-client", "version": "1.0.0"},
            },
        )
        self._send_notification("notifications/initialized")
        return result

    def shutdown(self) -> Dict[str, Any]:
        """Shut down the MCP session cleanly."""
        return self._send_request("shutdown", {})

    def list_tools(self) -> Dict[str, Any]:
        return self._send_request("tools/list", {})

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._send_request("tools/call", {"name": name, "arguments": arguments or {}})

    def list_resources(self) -> Dict[str, Any]:
        return self._send_request("resources/list", {})

    def read_resource(self, uri: str) -> Dict[str, Any]:
        return self._send_request("resources/read", {"uri": uri})

    def list_prompts(self) -> Dict[str, Any]:
        return self._send_request("prompts/list", {})

    def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._send_request("prompts/get", {"name": name, "arguments": arguments or {}})

    def close(self):
        self.session_id = None
