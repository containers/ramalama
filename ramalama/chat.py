#!/usr/bin/env python3

import _thread
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
from ramalama.proxy_support import setup_proxy_support

# Setup proxy support on module import
setup_proxy_support()


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
    name: str | None = None
    keepalive: int | None = None
    monitor: "ServerMonitor | None" = None


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
        self.message_count = 0  # Track messages for summarization

    def prep_rag_message(self):
        if (context := self.args.rag) is None:
            return

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(context)
        self.conversation_history.extend(messages)

    def _summarize_conversation(self):
        """Summarize the conversation history to prevent context growth."""
        if len(self.conversation_history) < 4:
            # Need at least a few messages to summarize
            return

        # Keep the first message (system/RAG context) and last 2 messages
        # Summarize everything in between
        first_msg = self.conversation_history[0]
        messages_to_summarize = self.conversation_history[1:-2]
        recent_msgs = self.conversation_history[-2:]

        if not messages_to_summarize:
            return

        # Create a summarization prompt
        conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages_to_summarize])

        summary_prompt = {
            "role": "user",
            "content": (
                f"Please provide a concise summary of the following conversation, "
                f"preserving key information and context:\n\n{conversation_text}\n\n"
                f"Provide only the summary, without any preamble."
            ),
        }

        # Make API call to get summary
        # Provide user feedback during summarization
        print("\nSummarizing conversation to reduce context size...", flush=True)
        try:
            req = self._make_api_request([summary_prompt], stream=False)

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                summary = result['choices'][0]['message']['content']

                # Rebuild conversation history with summary
                new_history = []
                if first_msg:
                    new_history.append(first_msg)

                # Add summary as a system message
                new_history.append({"role": "system", "content": f"Previous conversation summary: {summary}"})

                # Add recent messages
                new_history.extend(recent_msgs)

                self.conversation_history = new_history
                logger.debug(f"Summarized conversation: {len(messages_to_summarize)} messages -> 1 summary")

        except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to summarize conversation: {e}")
            # On failure, just keep the conversation as-is
        finally:
            # Clear the "Summarizing..." message
            print("\r" + " " * 60 + "\r", end="", flush=True)

    def _check_and_summarize(self):
        """Check if conversation needs summarization and trigger it."""
        summarize_after = getattr(self.args, "summarize_after", 0)
        if summarize_after > 0:
            self.message_count += 2  # user + assistant messages
            if self.message_count >= summarize_after:
                self._summarize_conversation()
                self.message_count = 0  # Reset counter after summarization

    def _make_api_request(self, messages, stream=True):
        """Make an API request with the given messages.

        Args:
            messages: List of message dicts to send
            stream: Whether to stream the response

        Returns:
            urllib.request.Request object
        """
        data = {
            "stream": stream,
            "messages": messages,
        }
        if getattr(self.args, "model", None):
            data["model"] = self.args.model
        if getattr(self.args, "temp", None):
            data["temperature"] = float(self.args.temp)
        if stream and getattr(self.args, "max_tokens", None):
            data["max_completion_tokens"] = self.args.max_tokens

        headers = add_api_key(self.args)
        headers["Content-Type"] = "application/json"

        return urllib.request.Request(
            self.url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method="POST",
        )

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

    def handle_args(self, monitor):
        prompt = " ".join(self.args.ARGS) if self.args.ARGS else None
        if not sys.stdin.isatty():
            stdin = sys.stdin.read()
            if prompt:
                prompt += f"\n\n{stdin}"
            else:
                prompt = stdin

        if prompt:
            self.default(prompt)
            monitor.stop()
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
                self._check_and_summarize()
            return False

        self.conversation_history.append({"role": "user", "content": content})
        self.request_in_process = True
        response = self._req()
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
        self.request_in_process = False
        self._check_and_summarize()

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

        if getattr(self.args, "server_process", False):
            self.args.server_process.terminate()
            try:
                self.args.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.args.server_process.kill()
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
                if self.operational_args.monitor and self.operational_args.monitor.is_exited():
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


class ServerMonitor:
    """Monitor server process or container and report when it exits."""

    def __init__(
        self,
        server_process=None,
        container_name=None,
        container_engine=None,
        join_timeout=3.0,
        check_interval=0.5,
        inspect_timeout=30.0,
    ):
        """
        Initialize the server monitor.

        Args:
            server_process: subprocess.Popen object to monitor
            container_name: Container name to monitor (for container monitoring)
            container_engine: Container engine command (podman/docker)
            join_timeout: Seconds for thread join when stopping (default: 3.0)
            check_interval: Seconds between monitoring checks (default: 0.5)
            inspect_timeout: Seconds to wait for container inspect command to complete (default: 30.0)

        Note: If neither server_process nor container_name is provided, the monitor
        operates in no-op mode (no actual monitoring occurs).
        """
        self.server_process = server_process
        self.container_name = container_name
        self.container_engine = container_engine
        self.timeout = join_timeout
        self.check_interval = check_interval
        self.inspect_timeout = inspect_timeout
        self._stop_event = threading.Event()
        self._exited_event = threading.Event()
        self._exit_info = {}
        self._monitor_thread = None

        # Determine monitoring mode
        if self.server_process:
            self._mode = "process"
        elif container_name and container_engine:
            self._mode = "container"
        else:
            # No monitoring needed - chat is being used without a service
            self._mode = "none"

    def start(self):
        """Start the monitoring thread."""
        # No-op if not monitoring anything
        if self._mode == "none":
            return

        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Monitor thread already running")
            return

        if self._mode == "process":
            target = self._monitor_process
        else:
            target = self._monitor_container

        self._monitor_thread = threading.Thread(target=target, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        """Stop the monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_event.set()
            self._monitor_thread.join(timeout=self.timeout)

    def is_exited(self):
        """Check if the monitored server/container has exited."""
        return self._exited_event.is_set()

    def is_stopping(self):
        """Check if the monitor is in the process of stopping."""
        return self._stop_event.is_set()

    def get_exit_info(self):
        """Get information about the exit."""
        return self._exit_info.copy()

    def _monitor_process(self):
        """Monitor the server process and report if it exits."""
        while not self._stop_event.is_set():
            try:
                exit_code = self.server_process.poll()
                if exit_code is not None:
                    # Process has exited
                    self._exit_info["pid"] = self.server_process.pid
                    self._exit_info["type"] = "exit"
                    self._exit_info["code"] = exit_code
                    self._exited_event.set()
                    # Send SIGINT to main process to interrupt the chat
                    _thread.interrupt_main()
                    break
            except Exception as e:
                logger.debug(f"Error monitoring process: {e}", exc_info=True)
                self._exit_info["pid"] = self.server_process.pid
                self._exit_info["type"] = "missing"
                self._exited_event.set()
                _thread.interrupt_main()
                break

            # Use wait() instead of sleep() for responsive shutdown
            self._stop_event.wait(self.check_interval)

    def _monitor_container(self):
        """Monitor the container and report if it exits."""
        while not self._stop_event.is_set():
            try:
                # Check if container is still running and get its state and exit code in one go
                inspect_format = "{{.State.Status}}\n{{.State.ExitCode}}"
                result = subprocess.run(
                    [self.container_engine, "inspect", "--format", inspect_format, self.container_name],
                    capture_output=True,
                    text=True,
                    timeout=self.inspect_timeout,
                )
                output_lines = result.stdout.strip().split('\n')
                status = output_lines[0] if output_lines else ""
                exit_code_str = output_lines[1] if len(output_lines) > 1 else ""

                # Explicitly check for non-running states
                if status in ["exited", "dead", "removing"] or (status == "" and exit_code_str != ""):
                    # Container has exited
                    self._exit_info["name"] = self.container_name
                    self._exit_info["type"] = "container"
                    # Default to 'exited' if status is empty but exit code exists
                    self._exit_info["status"] = status if status else "exited"

                    try:
                        self._exit_info["code"] = int(exit_code_str)
                    except (ValueError, AttributeError):
                        self._exit_info["code"] = "unknown"

                    self._exited_event.set()
                    # Send SIGINT to main process to interrupt the chat
                    _thread.interrupt_main()
                    break
            except subprocess.TimeoutExpired:
                logger.debug(f"Timeout checking container {self.container_name} status")
            except subprocess.CalledProcessError:
                # Container not found or error checking status
                self._exit_info["name"] = self.container_name
                self._exit_info["type"] = "container_missing"
                self._exited_event.set()
                _thread.interrupt_main()
                break
            except Exception as e:
                logger.debug(f"Error checking container status: {e}")
            # Use wait() instead of sleep() for responsive shutdown
            self._stop_event.wait(self.check_interval)


def _report_server_exit(monitor):
    """Report details about server exit."""
    exit_info = monitor.get_exit_info()
    exit_type = exit_info.get("type", "unknown")

    if exit_type == "container":
        container_name = exit_info.get("name", "unknown")
        exit_code = exit_info.get("code", "unknown")
        status = exit_info.get("status", "unknown")
        perror(f"Container '{container_name}' exited unexpectedly with exit code {exit_code} (status: {status})")
        perror("\nThe chat session has been terminated because the container is no longer running.")
        perror(f"Check container logs with: {monitor.container_engine} logs {container_name}")
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
    server_process = getattr(args, "server_process", None)
    container_name = getattr(args, "name", None)

    if server_process:
        # Monitor the server process
        monitor = ServerMonitor(server_process=server_process)
    elif container_name:
        # Monitor the container
        conman = getattr(args, "engine", CONFIG.engine)
        if not conman:
            raise ValueError("Container engine is required when monitoring a container")
        monitor = ServerMonitor(container_name=container_name, container_engine=conman)
    else:
        # No monitoring needed - chat is being used directly without a service
        monitor = ServerMonitor()

    monitor.start()
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

    # Assign monitor to operational_args
    operational_args.monitor = monitor

    successful_exit = True
    try:
        shell = RamaLamaShell(args, operational_args)
        if shell.handle_args(monitor):
            return

        if not list_models:
            shell.loop()
    except KeyboardInterrupt:
        # If monitor was already shut down exit cleanly
        if monitor.is_stopping():
            return
        # Check if this was caused by server exit
        if monitor.is_exited():
            successful_exit = False  # Server/container exited unexpectedly
            perror("\n" + "=" * 60)
            _report_server_exit(monitor)
            perror("=" * 60)
            exit_info = monitor.get_exit_info()
            exit_code = exit_info.get('code', 1)
            if exit_info.get('type') == 'signal' and isinstance(exit_info.get('signal'), int):
                exit_code = 128 + exit_info.get('signal')
            raise SystemExit(exit_code)
        raise
    except TimeoutException as e:
        logger.debug(f"Timeout Exception: {e}")
        # Handle the timeout, e.g., print a message and exit gracefully
        perror("")
        pass
    finally:
        # Stop the monitoring thread
        monitor.stop()
        # Reset the alarm to 0 to cancel any pending alarms (Unix only)
        if hasattr(signal, 'alarm'):
            signal.alarm(0)

    # Only clean up resources on successful exit
    # If server/container crashed, leave it for log inspection
    if successful_exit:
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
