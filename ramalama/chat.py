#!/usr/bin/env python3

import cmd
import copy
import itertools
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta

from ramalama.arg_types import ChatArgsType
from ramalama.common import perror
from ramalama.config import CONFIG
from ramalama.console import EMOJI, should_colorize
from ramalama.engine import dry_run, stop_container
from ramalama.file_loaders.file_manager import OpanAIChatAPIMessageBuilder
from ramalama.logger import logger
from ramalama.mcp.mcp_agent import LLMAgent
from ramalama.mcp.mcp_client import PureMCPClient


def res(response, color):
    color_default = ""
    color_yellow = ""
    if (color == "auto" and should_colorize()) or color == "always":
        color_default = "\033[0m"
        color_yellow = "\033[33m"

    print("\r", end="")
    assistant_response = ""
    for line in response:
        line = line.decode("utf-8").strip()
        if line.startswith("data: {"):
            choice = ""

            json_line = json.loads(line[len("data: ") :])
            if "choices" in json_line and json_line["choices"]:
                choice = json_line["choices"][0]["delta"]
            if "content" in choice:
                choice = choice["content"]
            else:
                continue

            if choice:
                print(f"{color_yellow}{choice}{color_default}", end="", flush=True)
                assistant_response += choice

    print("")
    return assistant_response


def default_prefix():
    if not EMOJI:
        return "> "

    if CONFIG.prefix:
        return CONFIG.prefix

    engine = CONFIG.engine

    if engine:
        if os.path.basename(engine) == "podman":
            return "🦭 > "

        if os.path.basename(engine) == "docker":
            return "🐋 > "

    return "🦙 > "


def add_api_key(args, headers=None):
    # static analyzers suggest for dict, this is a safer way of setting
    # a default value, rather than using the parameter directly
    headers = headers or {}
    if getattr(args, "api_key", None):
        api_key_min = 20
        if len(args.api_key) < api_key_min:
            perror("Warning: Provided API key is invalid.")

        headers["Authorization"] = f"Bearer {args.api_key}"

    return headers


@dataclass
class ChatOperationalArgs:
    initial_connection: bool = False
    pid2kill: int | None = None
    name: str | None = None
    keepalive: int | None = None


class RamaLamaShell(cmd.Cmd):
    def __init__(self, args: ChatArgsType, operational_args: ChatOperationalArgs | None = None):
        if operational_args is None:
            operational_args = ChatOperationalArgs()

        super().__init__()
        self.conversation_history: list[dict] = []
        self.args = args
        self.request_in_process = False
        self.prompt = args.prefix
        self.url = f"{args.url}/chat/completions"
        self.prep_rag_message()
        self.mcp_agent = None
        self.initialize_mcp()

        self.operational_args = operational_args

        self.content = []

    def prep_rag_message(self):
        if (context := self.args.rag) is None:
            return

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(context)
        self.conversation_history.extend(messages)

    def initialize_mcp(self):
        """Initialize MCP servers if specified."""
        if not hasattr(self.args, 'mcp') or not self.args.mcp:
            return

        try:
            # Create clients for each MCP server URL
            clients = []
            for url in self.args.mcp:
                try:
                    clients.append(PureMCPClient(url))
                    logger.debug(f"Created MCP client for {url}")
                except Exception as e:
                    perror(f"Failed to create MCP client for {url}: {e}")

            if clients:
                # Use the same LLM URL as the chat for the agent
                llm_url = self.args.url
                self.mcp_agent = LLMAgent(clients, llm_url, self.args.model, self.args)

                # Set up proper streaming callback for MCP agent
                def mcp_stream_callback(text):
                    color_default = ""
                    color_yellow = ""
                    if (self.args.color == "auto" and should_colorize()) or self.args.color == "always":
                        color_default = "\033[0m"
                        color_yellow = "\033[33m"
                    print(f"{color_yellow}{text}{color_default}", end="", flush=True)

                self.mcp_agent._stream_callback = mcp_stream_callback

                # Initialize the agent and get available tools
                init_results, tools = self.mcp_agent.initialize()

                # Show connection summary (simplified)
                for i, result in enumerate(init_results):
                    server_name = result['result']['serverInfo']['name']
                    server_tools = [tool for tool in tools if tool.get('server') == server_name]
                    logger.debug(f"Connected to: {server_name}")
                    print(f"Found {len(server_tools)} tool(s) from {server_name}")

                print("\nUsage:")
                print("  - Ask questions naturally (automatic tool selection)")
                print("  - Use '/tool [question]' to manually select which tool to use")
                print("  - Use '/bye' or 'exit' to quit")

        except Exception as e:
            perror(f"Failed to initialize MCP: {e}")
            logger.debug(f"MCP initialization error: {e}", exc_info=True)

    def _should_use_mcp(self, content: str) -> bool:
        """Determine if the request should be handled by MCP tools."""
        if not self.mcp_agent:
            return False
        return self.mcp_agent.should_use_tools(content, self.conversation_history)

    def _handle_mcp_request(self, content: str) -> str:
        """Handle a request using MCP tools (multi-tool capable, automatic)."""
        try:
            # Automatic tool selection and argument generation
            results = self.mcp_agent.execute_task(content, manual=False, stream=True)

            # When streaming, results will be None since output is streamed directly
            if results is None:
                return ""  # Return empty string since content was already streamed
            # If multiple tools ran, join results into a single answer
            elif isinstance(results, list):
                combined = "\n\n".join(f"🔧 {r['tool']}: {r['output']}" for r in results)
                return f"Multi-tool execution:\n{combined}"
            else:
                return results
        except Exception as e:
            logger.debug(f"MCP request handling error: {e}", exc_info=True)
            return f"Error using MCP tools: {e}"

    def _handle_manual_tool_selection(self, content: str):
        if not self.mcp_agent or not self.mcp_agent.available_tools:
            print("No MCP tools available.")
            return

        parts = content.strip().split(None, 1)
        question = parts[1] if len(parts) > 1 else ""

        selected_tools = self._select_tools()
        if not selected_tools:
            return

        responses = []
        for tool in selected_tools:
            response = self.mcp_agent.execute_specific_tool(question, tool['name'], manual=False)
            responses.append({"tool": tool['name'], "output": response})

        # Display results
        for r in responses:
            print(f"\n {r['tool']} -> {r['output']}")

        # Save to history
        self.conversation_history.append({"role": "user", "content": f"/tool {question}"})
        self.conversation_history.append({"role": "assistant", "content": str(responses)})

    def _select_tools(self):
        """Interactive multi-tool selection without prompting for arguments."""
        if not self.mcp_agent or not self.mcp_agent.available_tools:
            return None

        self.mcp_agent.print_tools()

        try:
            choice = input("\nSelect tool(s) (e.g. 1,2,3) or 'q' to cancel: ").strip()
            if choice.lower() == 'q':
                return None

            indices = [int(c.strip()) - 1 for c in choice.split(",")]
            selected = [
                self.mcp_agent.available_tools[i] for i in indices if 0 <= i < len(self.mcp_agent.available_tools)
            ]

            return selected

        except (ValueError, KeyboardInterrupt):
            print("\nCancelled.")
            return None

    def handle_args(self):
        prompt = " ".join(self.args.ARGS) if self.args.ARGS else None
        if not sys.stdin.isatty():
            stdin = sys.stdin.read()
            if prompt:
                prompt += f"\n\n{stdin}"
            else:
                prompt = stdin

        if prompt:
            self.default(prompt)
            self.kills()
            return True

        return False

    def do_EOF(self, user_content):
        print("")
        return True

    def default(self, user_content):
        self.content.append(user_content.rstrip(" \\"))
        if user_content.endswith(" \\"):
            return False

        if user_content in ["/bye", "exit"]:
            return True

        content = "\n".join(self.content)
        self.content = []

        # Check for manual tool selection command FIRST
        if self.mcp_agent and content.strip().startswith("/tool"):
            self._handle_manual_tool_selection(content)
            return False

        # Check if MCP agent should handle this request
        if self.mcp_agent and self._should_use_mcp(content):
            response = self._handle_mcp_request(content)
            if response:
                # If streaming, _handle_mcp_request already printed output
                if isinstance(response, str) and response.strip():
                    print(response)
                self.conversation_history.append({"role": "user", "content": content})
                self.conversation_history.append({"role": "assistant", "content": response})
            return False

        self.conversation_history.append({"role": "user", "content": content})
        self.request_in_process = True
        response = self._req()
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
        self.request_in_process = False

    def _make_request_data(self):
        data = {
            "stream": True,
            "messages": self.conversation_history,
        }
        if self.args.model is not None:
            data["model"] = self.args.model

        json_data = json.dumps(data).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }

        headers = add_api_key(self.args, headers)
        logger.debug("Request: URL=%s, Data=%s, Headers=%s", self.url, json_data, headers)
        request = urllib.request.Request(self.url, data=json_data, headers=headers, method="POST")

        return request

    def _req(self):
        request = self._make_request_data()

        i = 0.01
        total_time_slept = 0
        response = None

        # Adjust timeout based on whether we're in initial connection phase
        max_timeout = 30 if getattr(self.args, "initial_connection", False) else 16

        for c in itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']):
            try:
                response = urllib.request.urlopen(request)
                break
            except Exception:
                if sys.stdout.isatty():
                    perror(f"\r{c}", end="", flush=True)

                if total_time_slept > max_timeout:
                    break

                total_time_slept += i
                time.sleep(i)

                i = min(i * 2, 0.1)

        if response:
            return res(response, self.args.color)

        # Only show error and kill if not in initial connection phase
        if not getattr(self.args, "initial_connection", False):
            perror(f"\rError: could not connect to: {self.url}")
            self.kills()
        else:
            logger.debug(f"Could not connect to: {self.url}")

        return None

    def kills(self):
        # Clean up MCP connections first
        if self.mcp_agent:
            try:
                for client in self.mcp_agent.clients:
                    client.close()
                logger.debug("Closed MCP connections")
            except Exception as e:
                logger.debug(f"Error closing MCP connections: {e}")

        # Don't kill the server if we're still in the initial connection phase
        if getattr(self.args, "initial_connection", False):
            return

        if getattr(self.args, "pid2kill", False):
            os.kill(self.args.pid2kill, signal.SIGINT)
            os.kill(self.args.pid2kill, signal.SIGTERM)
            os.kill(self.args.pid2kill, signal.SIGKILL)
        elif getattr(self.args, "name", None):
            args = copy.copy(self.args)
            args.ignore = True
            stop_container(args, self.args.name)

    def loop(self):
        while True:
            self.request_in_process = False
            try:
                self.cmdloop()
            except KeyboardInterrupt:
                print("")
                if not self.request_in_process:
                    print("Use Ctrl + d or /bye or exit to quit.")

                continue

            break


class TimeoutException(Exception):
    pass


def alarm_handler(signum, frame):
    """
    Signal handler for SIGALRM. Raises TimeoutException when invoked.
    """
    raise TimeoutException()


def chat(args: ChatArgsType, operational_args: ChatOperationalArgs = ChatOperationalArgs()):
    if args.dryrun:
        prompt = dry_run(args.ARGS)
        print(f"\nramalama chat --color {args.color} --prefix  \"{args.prefix}\" --url {args.url} {prompt}")
        return
    if getattr(args, "keepalive", False):
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(convert_to_seconds(args.keepalive))

    list_models = getattr(args, "list", False)
    if list_models:
        url = f"{args.url}/models"
        headers = add_api_key(args)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            ids = [model["id"] for model in data.get("data", [])]
            for id in ids:
                print(id)
    try:
        shell = RamaLamaShell(args, operational_args)
        if shell.handle_args():
            return

        if not list_models:
            shell.loop()
    except TimeoutException as e:
        logger.debug(f"Timeout Exception: {e}")
        # Handle the timeout, e.g., print a message and exit gracefully
        perror("")
        pass
    finally:
        # Reset the alarm to 0 to cancel any pending alarms
        signal.alarm(0)
    try:
        shell.kills()
    except Exception as e:
        logger.warning(f"Failed to clean up resources: {e}")


UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def convert_to_seconds(s):
    if isinstance(s, int):
        # We are dealing with a raw number
        return s

    try:
        seconds = int(s)
        # We are dealing with an integer string
        return seconds
    except ValueError:
        # We are dealing with some other string or type
        pass

    # Expecting a string ending in [m|h|d|s|w]
    count = int(s[:-1])
    unit = UNITS[s[-1]]
    td = timedelta(**{unit: count})
    return td.seconds + 60 * 60 * 24 * td.days
