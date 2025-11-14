#!/usr/bin/env python3

import cmd
import copy
import itertools
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import timedelta

from ramalama.arg_types import ChatArgsType
from ramalama.common import perror
from ramalama.config import CONFIG
from ramalama.console import EMOJI, should_colorize
from ramalama.engine import stop_container
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
    server_exited_event: "threading.Event | None" = None


class RamaLamaShell(cmd.Cmd):
    def __init__(self, args: ChatArgsType, operational_args: ChatOperationalArgs | None = None):
        if operational_args is None:
            operational_args = ChatOperationalArgs()

        super().__init__()
        self.conversation_history: list[dict] = []
        self.args = args
        self.operational_args = operational_args
        self.request_in_process = False
        self.prompt = args.prefix
        self.url = f"{args.url}/chat/completions"
        self.prep_rag_message()
        self.mcp_agent: LLMAgent | None = None
        self.initialize_mcp()

        self.content: list[str] = []

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
            assert self.mcp_agent
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
            perror("No MCP tools available.")
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
            perror("\nCancelled.")
            return None

    def handle_args(self, monitor_thread):
        prompt = " ".join(self.args.ARGS) if self.args.ARGS else None
        if not sys.stdin.isatty():
            stdin = sys.stdin.read()
            if prompt:
                prompt += f"\n\n{stdin}"
            else:
                prompt = stdin

        if prompt:
            self.default(prompt)
            if monitor_thread:
                _stop_server_monitor(monitor_thread)
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
        if getattr(self.args, "temp", None):
            data["temperature"] = float(self.args.temp)
        if getattr(self.args, "max_tokens", None):
            data["max_completion_tokens"] = self.args.max_tokens
        # For MLX runtime, omit explicit model to allow server default ("default_model")
        if getattr(self.args, "runtime", None) != "mlx" and self.args.model is not None:
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
            # Send signals to terminate process
            # On Windows, only SIGTERM and SIGINT are supported
            try:
                os.kill(self.args.pid2kill, signal.SIGINT)
            except (ProcessLookupError, AttributeError):
                pass
            try:
                os.kill(self.args.pid2kill, signal.SIGTERM)
            except (ProcessLookupError, AttributeError):
                pass
            # SIGKILL doesn't exist on Windows, use SIGTERM instead
            if hasattr(signal, 'SIGKILL'):
                try:
                    os.kill(self.args.pid2kill, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        elif getattr(self.args, "name", None):
            args = copy.copy(self.args)
            args.ignore = True
            # Remove containers on normal exit (remove=True)
            stop_container(args, self.args.name, remove=True)
            if extra_name := self.operational_args.name:
                stop_container(args, extra_name, remove=True)

    def loop(self):
        while True:
            self.request_in_process = False
            try:
                self.cmdloop()
            except KeyboardInterrupt:
                # Distinguish between user interrupt and server/container exit
                if self.operational_args.server_exited_event and self.operational_args.server_exited_event.is_set():
                    # Server/container exited, exit with clear message
                    perror("\nServer or container exited. Shutting down client.")
                    raise
                else:
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
    Note: SIGALRM is Unix-only and not available on Windows.
    """
    raise TimeoutException()


def _start_server_monitor(server_pid):
    """Start a background thread to monitor the server process."""

    # Use a global variable to track monitor status
    global _server_monitor_active
    if getattr(_start_server_monitor, "_active", False):
        # Monitor already running, do not start another
        return None, None, None
    _start_server_monitor._active = True

    # Event to signal the monitor thread to stop
    stop_monitor = threading.Event()
    # Event to signal that server has exited
    server_exited = threading.Event()
    exit_info = {}

    def monitor_server_process():
        """Monitor the server process and report if it exits."""
        while not stop_monitor.is_set():
            try:
                # Use waitpid with WNOHANG to check without blocking
                pid, status = os.waitpid(server_pid, os.WNOHANG)
                if pid != 0:
                    # Process has exited
                    exit_info["pid"] = server_pid
                    exit_info["status"] = status
                    if os.WIFEXITED(status):
                        exit_info["type"] = "exit"
                        exit_info["code"] = os.WEXITSTATUS(status)
                    elif os.WIFSIGNALED(status):
                        exit_info["type"] = "signal"
                        exit_info["signal"] = os.WTERMSIG(status)
                    else:
                        exit_info["type"] = "unknown"
                    server_exited.set()
                    # Send SIGINT to main process to interrupt the chat
                    os.kill(os.getpid(), signal.SIGINT)
                    break
            except ChildProcessError:
                # Process doesn't exist or already reaped
                exit_info["pid"] = server_pid
                exit_info["type"] = "missing"
                server_exited.set()
                os.kill(os.getpid(), signal.SIGINT)
                break
            time.sleep(0.5)
        # Reset monitor status when thread exits
        _start_server_monitor._active = False

    monitor_thread = threading.Thread(target=monitor_server_process, daemon=True)
    monitor_thread.start()
    monitor_thread.stop_event = stop_monitor
    return monitor_thread, server_exited, exit_info


def _start_container_monitor(container_name, conman):
    """Start a background thread to monitor the container."""

    # Event to signal the monitor thread to stop
    stop_monitor = threading.Event()
    # Event to signal that container has exited
    container_exited = threading.Event()
    exit_info = {}

    def monitor_container():
        """Monitor the container and report if it exits."""
        while not stop_monitor.is_set():
            try:
                # Check if container is still running and get its state and exit code in one go
                inspect_format = "{{.State.Status}}\n{{.State.ExitCode}}"
                result = subprocess.run(
                    [conman, "inspect", "--format", inspect_format, container_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                output_lines = result.stdout.strip().split('\n')
                status = output_lines[0] if output_lines else ""
                exit_code_str = output_lines[1] if len(output_lines) > 1 else ""

                # Explicitly check for non-running states
                if status in ["exited", "dead", "removing"] or (status == "" and exit_code_str != ""):
                    # Container has exited
                    exit_info["name"] = container_name
                    exit_info["type"] = "container"
                    # Default to 'exited' if status is empty but exit code exists
                    exit_info["status"] = status if status else "exited"

                    try:
                        exit_info["code"] = int(exit_code_str)
                    except (ValueError, AttributeError):
                        exit_info["code"] = "unknown"

                    container_exited.set()
                    # Send SIGINT to main process to interrupt the chat
                    os.kill(os.getpid(), signal.SIGINT)
                    break
            except subprocess.TimeoutExpired:
                logger.debug(f"Timeout checking container {container_name} status")
            except subprocess.CalledProcessError:
                # Container not found or error checking status
                exit_info["name"] = container_name
                exit_info["type"] = "container_missing"
                container_exited.set()
                os.kill(os.getpid(), signal.SIGINT)
                break
            except Exception as e:
                logger.debug(f"Error checking container status: {e}")
            time.sleep(0.5)  # Check every 500ms

    # Start the monitoring thread
    monitor_thread = threading.Thread(target=monitor_container, daemon=True)
    monitor_thread.start()

    # Store stop_monitor in the thread object so we can access it later
    monitor_thread.stop_event = stop_monitor

    return monitor_thread, container_exited, exit_info


def _stop_server_monitor(monitor_thread):
    """Stop the server monitoring thread."""
    if hasattr(monitor_thread, "stop_event"):
        monitor_thread.stop_event.set()
        monitor_thread.join(timeout=1.0)


def _report_server_exit(exit_info):
    """Report details about server exit."""
    exit_type = exit_info.get("type", "unknown")

    if exit_type == "container":
        container_name = exit_info.get("name", "unknown")
        exit_code = exit_info.get("code", "unknown")
        status = exit_info.get("status", "unknown")
        perror(f"Container '{container_name}' exited unexpectedly with exit code {exit_code} (status: {status})")
        perror("\nThe chat session has been terminated because the container is no longer running.")
        perror(f"Check container logs with: podman logs {container_name}")
    elif exit_type == "container_missing":
        container_name = exit_info.get("name", "unknown")
        perror(f"Container '{container_name}' not found - may have been removed")
        perror("\nThe chat session has been terminated because the container is no longer available.")
    else:
        # Process-based exit
        pid = exit_info.get("pid", "unknown")

        if exit_type == "exit":
            exit_code = exit_info.get("code", "unknown")
            perror(f"Server process (PID {pid}) exited unexpectedly with exit code {exit_code}")
        elif exit_type == "signal":
            signal_num = exit_info.get("signal", "unknown")
            perror(f"Server process (PID {pid}) was terminated by signal {signal_num}")
        elif exit_type == "missing":
            perror(f"Server process (PID {pid}) not found - may have exited before monitoring started")
        else:
            perror(f"Server process (PID {pid}) exited unexpectedly")

        perror("\nThe chat session has been terminated because the server is no longer running.")
        perror("Check server logs for more details about why the service exited.")


def chat(args: ChatArgsType, operational_args: ChatOperationalArgs | None = None):
    if args.dryrun:
        assert args.ARGS is not None
        prompt = " ".join(args.ARGS)
        print(f"\nramalama chat --color {args.color} --prefix  \"{args.prefix}\" --url {args.url} {prompt}")
        return
    # SIGALRM is Unix-only, skip keepalive timeout handling on Windows
    if getattr(args, "keepalive", False) and hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(convert_to_seconds(args.keepalive))  # type: ignore

    # Start server process or container monitoring
    monitor_thread = None
    server_exited_event = None
    exit_info = {}

    # Check if we should monitor a process (pid2kill) or container (name)
    pid2kill = getattr(args, "pid2kill", None)
    container_name = getattr(args, "name", None)

    if pid2kill:
        # Monitor the server process
        monitor_thread, server_exited_event, exit_info = _start_server_monitor(pid2kill)
    elif container_name:
        # Monitor the container
        conman = getattr(args, "engine", CONFIG.engine)
        if conman:
            monitor_thread, server_exited_event, exit_info = _start_container_monitor(container_name, conman)
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

    # Ensure operational_args is initialized
    if operational_args is None:
        operational_args = ChatOperationalArgs()

    # Assign server_exited_event to operational_args immediately after thread/event creation
    if server_exited_event:
        operational_args.server_exited_event = server_exited_event

    try:
        shell = RamaLamaShell(args, operational_args)
        if shell.handle_args(monitor_thread):
            return

        if not list_models:
            shell.loop()
    except KeyboardInterrupt:
        # If monitor was already shut down exit cleanly
        if monitor_thread and monitor_thread.stop_event.is_set():
            return
        # Check if this was caused by server exit
        if server_exited_event and server_exited_event.is_set():
            # Server/container exited unexpectedly
            perror("\n" + "=" * 60)
            _report_server_exit(exit_info)
            perror("=" * 60)
            raise SystemExit(exit_info['code'])
        raise
    except TimeoutException as e:
        logger.debug(f"Timeout Exception: {e}")
        # Handle the timeout, e.g., print a message and exit gracefully
        perror("")
        pass
    finally:
        # Stop the monitoring thread if it was started
        if monitor_thread:
            _stop_server_monitor(monitor_thread)
        # Reset the alarm to 0 to cancel any pending alarms (Unix only)
        if hasattr(signal, 'alarm'):
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
