#!/usr/bin/env python3

import _thread
import cmd
import copy
import itertools
import json
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from ramalama.arg_types import ChatArgsType
from ramalama.chat_providers import ChatProvider, ChatRequestOptions
from ramalama.chat_providers.openai import OpenAICompletionsChatProvider
from ramalama.chat_utils import (
    AssistantMessage,
    ChatMessageType,
    SystemMessage,
    ToolMessage,
    UserMessage,
    stream_response,
)
from ramalama.common import perror
from ramalama.config import get_config
from ramalama.console import should_colorize
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


class Spinner:
    def __init__(self, wait_time: float = 0.1):
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None
        self.wait_time = wait_time

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    def start(self) -> "Spinner":
        if not sys.stdout.isatty():
            return self

        if self._thread is not None:
            self.stop()

        self._thread = threading.Thread(target=self._spinner_loop, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join(timeout=0.2)
        perror("\r", end="", flush=True)
        self._thread = None
        self._stop_event = threading.Event()

    def _spinner_loop(self):
        frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

        for frame in itertools.cycle(frames):
            if self._stop_event.is_set():
                break
            perror(f"\r{frame}", end="", flush=True)
            self._stop_event.wait(self.wait_time)


class RamaLamaShell(cmd.Cmd):
    def __init__(
        self,
        args: ChatArgsType,
        operational_args: ChatOperationalArgs | None = None,
        provider: ChatProvider | None = None,
    ):
        if operational_args is None:
            operational_args = ChatOperationalArgs()

        super().__init__()
        self.conversation_history: list[ChatMessageType] = []
        self.args = args
        self.operational_args = operational_args
        self.request_in_process = False
        self.prompt = args.prefix
        self.provider = provider or OpenAICompletionsChatProvider(args.url, getattr(args, "api_key", None))
        self.url = self.provider.build_url()

        self.prep_rag_message()
        self.mcp_agent: LLMAgent | None = None
        self.initialize_mcp()

        self.content: list[str] = []
        self.message_count = 0  # Track messages for summarization

    def do_help(self, args):
        """Display help information about available commands."""
        print("\nAvailable commands:")
        print("  /help, help, ?    - Show this help message")
        print("  /clear            - Clear conversation history")
        print("  /bye, exit        - Exit the chat session")
        if self.mcp_agent:
            print("  /tool [question]  - Manually select which MCP tool to use")
        print("  \\                 - End a line with backslash to continue on next line")
        print("  Ctrl+D            - Exit the chat session (EOF)")
        print()

    def prep_rag_message(self):
        if (context := self.args.rag) is None:
            return

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(context)
        self.conversation_history.extend(messages)

    def _summarize_conversation(self):
        """Summarize the conversation history to prevent context growth."""
        if len(self.conversation_history) < 10:
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
        conversation_text = "\n".join([self._format_message_for_summary(msg) for msg in messages_to_summarize])
        summary_prompt = UserMessage(
            text=(
                "Please provide a concise summary of the following conversation, "
                f"preserving key information and context:\n\n{conversation_text}\n\n"
                "Provide only the summary, without any preamble."
            )
        )

        # Make API call to get summary
        # Provide user feedback during summarization
        print("\nSummarizing conversation to reduce context size...", flush=True)
        try:
            req = self._make_api_request([summary_prompt], stream=False)

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                summary = result['choices'][0]['message']['content']

                # Rebuild conversation history with summary
                new_history: list[ChatMessageType] = []
                if first_msg:
                    new_history.append(first_msg)

                # Add summary as a system message
                new_history.append(SystemMessage(text=f"Previous conversation summary: {summary}"))

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

    def _history_snapshot(self) -> list[dict[str, str]]:
        return [
            {"role": msg.role, "content": self._format_message_for_summary(msg)} for msg in self.conversation_history
        ]

    def _format_message_for_summary(self, msg: ChatMessageType) -> str:
        content = msg.text or ""
        if isinstance(msg, AssistantMessage):
            if msg.tool_calls:
                content += f"\n[tool_calls: {', '.join(call.name for call in msg.tool_calls)}]"

        if isinstance(msg, ToolMessage):
            content = f"\n[tool_response: {msg.text}]"

        return f"{msg.role}: {content}".strip()

    def _make_api_request(self, messages: Sequence[ChatMessageType], stream: bool = True):
        """Create a provider request for arbitrary message lists."""
        max_tokens = self.args.max_tokens if stream and getattr(self.args, "max_tokens", None) else None
        options = self._build_request_options(stream=stream, max_tokens=max_tokens)
        return self.provider.create_request(messages, options)

    def _resolve_model_name(self) -> str | None:
        if getattr(self.args, "runtime", None) == "mlx":
            return None
        return getattr(self.args, "model", None)

    def _build_request_options(self, *, stream: bool, max_tokens: int | None) -> ChatRequestOptions:
        temperature = getattr(self.args, "temp", None)
        if max_tokens is not None and max_tokens <= 0:
            max_tokens = None
        return ChatRequestOptions(
            model=self._resolve_model_name(),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
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

                self.do_help("")

        except Exception as e:
            perror(f"Failed to initialize MCP: {e}")
            logger.debug(f"MCP initialization error: {e}", exc_info=True)

    def _should_use_mcp(self, content: str) -> bool:
        """Determine if the request should be handled by MCP tools."""
        if not self.mcp_agent:
            return False
        return self.mcp_agent.should_use_tools(content, self._history_snapshot())

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
        self.conversation_history.append(UserMessage(text=f"/tool {question}"))
        self.conversation_history.append(AssistantMessage(text=str(responses)))

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
        # Check for commands before processing multi-line input
        # Normalize: strip whitespace and make case-insensitive
        cmd = user_content.strip().lower()

        # Help command - show available commands
        if cmd in ["/help", "help", "?"]:
            self.do_help("")
            return False

        # Exit commands
        if cmd in ["/bye", "exit"]:
            return True

        # Clear command - reset conversation history and multi-line buffer
        if cmd == "/clear":
            self.conversation_history = []
            self.content = []
            print("Conversation history cleared.")
            return False

        # Handle multi-line input (backslash continuation)
        self.content.append(user_content.rstrip(" \\"))
        if user_content.endswith(" \\"):
            return False

        content = "\n".join(self.content)
        self.content = []

        # Check for manual tool selection command FIRST (case-insensitive)
        if self.mcp_agent and content.strip().lower().startswith("/tool"):
            self._handle_manual_tool_selection(content)
            return False

        # Check if MCP agent should handle this request
        if self.mcp_agent and self._should_use_mcp(content):
            response = self._handle_mcp_request(content)
            if response:
                # If streaming, _handle_mcp_request already printed output
                if isinstance(response, str) and response.strip():
                    print(response)
                self.conversation_history.append(UserMessage(text=content))
                self.conversation_history.append(AssistantMessage(text=response))
                self._check_and_summarize()
            return False

        self.conversation_history.append(UserMessage(text=content))
        self.request_in_process = True
        response = self._req()
        if response:
            self.conversation_history.append(AssistantMessage(text=response))
        self.request_in_process = False
        self._check_and_summarize()

    def _make_request_data(self):
        options = self._build_request_options(
            stream=True,
            max_tokens=getattr(self.args, "max_tokens", None),
        )
        request = self.provider.create_request(self.conversation_history, options)
        logger.debug("Request: URL=%s, Data=%s, Headers=%s", request.full_url, request.data, request.headers)
        return request

    def _req(self):
        request = self._make_request_data()

        i = 0.01
        total_time_slept = 0
        response = None

        # Adjust timeout based on whether we're in initial connection phase
        max_timeout = 30 if getattr(self.args, "initial_connection", False) else 16

        last_error: Exception | None = None

        spinner = Spinner().start()

        while True:
            try:
                response = urllib.request.urlopen(request)
                spinner.stop()
                break
            except urllib.error.HTTPError as http_err:
                error_body = http_err.read().decode("utf-8", "ignore").strip()
                message = f"HTTP {http_err.code}"
                if error_body:
                    message = f"{message}: {error_body}"
                perror(f"\r{message}")

                self.kills()
                spinner.stop()
                return None
            except Exception as exc:
                last_error = exc

            if total_time_slept > max_timeout:
                break

            total_time_slept += i
            time.sleep(i)

            i = min(i * 2, 0.1)

        spinner.stop()
        if response:
            return stream_response(response, self.args.color, self.provider)

        # Only show error and kill if not in initial connection phase
        if not getattr(self.args, "initial_connection", False):
            error_suffix = ""
            if last_error:
                error_suffix = f" ({last_error})"
            perror(f"\rError: could not connect to: {self.url}{error_suffix}")
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
                        print("Use /help for commands. Ctrl+d, /bye or exit to quit.")

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


def chat(
    args: ChatArgsType,
    operational_args: ChatOperationalArgs | None = None,
    provider: ChatProvider | None = None,
):
    if args.dryrun:
        assert args.ARGS is not None
        prompt = " ".join(args.ARGS)
        print(f"\nramalama chat --color {args.color} --prefix  \"{args.prefix}\" --url {args.url} {prompt}")
        return

    if provider is None:
        provider = OpenAICompletionsChatProvider(args.url, getattr(args, "api_key", None))

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
        conman = getattr(args, "engine", get_config().engine)
        if not conman:
            raise ValueError("Container engine is required when monitoring a container")
        monitor = ServerMonitor(container_name=container_name, container_engine=conman)
    else:
        # No monitoring needed - chat is being used directly without a service
        monitor = ServerMonitor()

    monitor.start()
    list_models = getattr(args, "list", False)
    if list_models:
        for model_id in provider.list_models():
            print(model_id)
        monitor.stop()
        if hasattr(signal, 'alarm'):
            signal.alarm(0)
        return

    # Ensure operational_args is initialized
    if operational_args is None:
        operational_args = ChatOperationalArgs()

    # Assign monitor to operational_args
    operational_args.monitor = monitor

    successful_exit = True
    try:
        shell = RamaLamaShell(args, operational_args, provider=provider)
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
