#!/usr/bin/env python3

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List

from ramalama.config import get_config
from ramalama.logger import logger
from ramalama.mcp.mcp_client import PureMCPClient


class LLMAgent:
    """An LLM-powered agent that can make multiple tool calls to accomplish tasks."""

    def __init__(
        self,
        clients: List[PureMCPClient],
        llm_base_url: str = "http://localhost:8080",
        model: str | None = None,
        args=None,
    ):
        config_level = get_config().log_level or logging.INFO
        if logging.getLogger().handlers:
            logging.getLogger().setLevel(config_level)
        else:
            logging.basicConfig(level=config_level)
        self.clients = clients if isinstance(clients, list) else [clients]
        self.llm_base_url = llm_base_url.rstrip('/')
        self.model = model
        self.args = args
        self.available_tools: List[Dict[str, Any]] = []
        self.tool_to_client: Dict[str, PureMCPClient] = {}
        self._stream_callback: Callable[[str], None] | None = None

    def initialize(self):
        """Initialize the agent and get available tools from all clients."""
        all_init_results = []
        self.available_tools = []
        self.tool_to_client = {}

        for i, client in enumerate(self.clients):
            try:
                init_result = client.initialize()
                all_init_results.append(init_result)

                server_name = init_result['result']['serverInfo']['name']
                tools_result = client.list_tools()
                server_tools = tools_result['result']['tools']

                for tool in server_tools:
                    tool_name = tool['name']
                    if tool_name in self.tool_to_client:
                        original_name = tool_name
                        tool_name = f"{server_name}_{original_name}"
                        tool['name'] = tool_name

                    tool['server'] = server_name
                    self.tool_to_client[tool_name] = client
                    self.available_tools.append(tool)

            except Exception as e:
                logging.error("Failed to initialize client %s: %s", i, e, exc_info=True)

        if not self.available_tools:
            raise RuntimeError("No tools available from any server")

        return all_init_results, self.available_tools

    def print_tools(self):
        print("\nAvailable tools:\n")
        for i, tool in enumerate(self.available_tools, 1):
            name = tool.get("name", "unknown")
            description = tool.get("description", "").split(" (from")[0]
            logger.debug(f"{name}: {description}")

            input_props = tool.get("inputSchema", {}).get("properties", {})
            if input_props:
                inputs = [f"{key} ({prop.get('type', 'unknown')})" for key, prop in input_props.items()]
                inputs_str = ", ".join(inputs)
            else:
                inputs_str = "none"

            print(f"  {i}. {name}")
            print(f"     Inputs: {inputs_str}\n")

    def should_use_tools(self, content: str, conversation_history: list[dict[str, str]] | None = None) -> bool:
        """Determine if the request should be handled by tools using LLM."""
        tools_context = "Available tools:\n"
        for i, tool in enumerate(self.available_tools, 1):
            name = tool.get("name", "unknown")
            description = tool.get("description", "")
            tools_context += f"{i}. {name}: {description}\n"

        context_info = ""
        if conversation_history:
            context_info = "\nRecent conversation:\n"
            for msg in conversation_history[-3:]:
                role = msg['role'].capitalize()
                preview = msg['content'][:150] + "..." if len(msg['content']) > 150 else msg['content']
                context_info += f"{role}: {preview}\n"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an intelligent assistant that determines whether a user's "
                    "request should use the available tools.\n\n"
                    "Answer ONLY \"YES\" if tools should be used or \"NO\" otherwise."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"""User request: {content}
{context_info}
{tools_context}

Should this request use the available tools?"""
                ),
            },
        ]
        response = self._call_llm(messages)
        return response is not None and response.upper().strip() == "YES"

    def _call_llm(self, messages: List[Dict[str, str]], console_stream: bool = False) -> str | None:
        """
        Call the LLM with the given messages.
        """
        request_data = {"messages": messages, "stream": True}
        if self.model is not None:
            request_data["model"] = self.model
        data = json.dumps(request_data).encode("utf-8")

        headers = {"Content-Type": "application/json"}

        # Add API key if available
        if self.args and getattr(self.args, "api_key", None):
            headers["Authorization"] = f"Bearer {self.args.api_key}"
        request = urllib.request.Request(
            f"{self.llm_base_url}/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )

        if not console_stream:
            content = ""
            # Retry logic similar to regular chat system
            max_retries = 10
            retry_delay = 0.5

            for attempt in range(max_retries):
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        for raw_line in response:
                            line = raw_line.decode("utf-8").strip()
                            if line.startswith("data: "):
                                payload = line[6:]
                                if payload.strip() == "[DONE]":
                                    break
                                try:
                                    event = json.loads(payload)
                                    if "choices" in event and event["choices"]:
                                        delta = event["choices"][0].get("delta", {})
                                        if "content" in delta and delta["content"] is not None:
                                            content += delta["content"]
                                except json.JSONDecodeError:
                                    logging.warning("Malformed SSE line: %s", payload)
                        return content.strip()
                except Exception as e:
                    if attempt == max_retries - 1:
                        # Last attempt failed, log error and return empty
                        logging.error("LLM call failed after %d attempts: %s", max_retries, e)
                        return ""
                    else:
                        # Retry after delay
                        logging.debug("LLM call failed (attempt %d/%d), retrying: %s", attempt + 1, max_retries, e)
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
            return ""
        elif console_stream:
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    for raw_line in response:
                        line = raw_line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            payload = line[6:]
                            if payload.strip() == "[DONE]":
                                break
                            try:
                                event = json.loads(payload)
                                if "choices" in event and event["choices"]:
                                    delta = event["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"] is not None:
                                        if callable(self._stream_callback):
                                            self._stream_callback(delta["content"])
                                        else:
                                            print(delta["content"], end="", flush=True)
                            except json.JSONDecodeError:
                                logging.warning("Malformed SSE line: %s", payload)
                return None
            except Exception as e:
                logging.error("LLM streaming call failed: %s", e, exc_info=True)
                return None
        else:
            raise ValueError(f"Unknown mode: {console_stream}")

    def _get_tool_arguments_manual(self, tool: dict) -> dict:
        """Prompt user based on inputSchema."""
        args: dict[Any, Any] = {}
        input_props = tool.get("inputSchema", {}).get("properties", {})
        required_fields = tool.get("inputSchema", {}).get("required", [])

        for name, info in input_props.items():
            default = info.get("default")
            param_type = info.get("type", "string")
            prompt_str = f"Enter value for {name} ({param_type})"
            if default is not None:
                prompt_str += f" (default={default})"
            prompt_str += ": "

            while True:
                value = input(prompt_str).strip()
                if not value and default is not None:
                    value = default
                if value or name not in required_fields:
                    # Convert value based on type
                    try:
                        if param_type == "integer":
                            args[name] = int(value) if value else None
                        elif param_type == "number":
                            args[name] = float(value) if value else None
                        elif param_type == "boolean":
                            args[name] = value.lower() in ("true", "1", "yes", "on") if value else None
                        else:
                            args[name] = value
                    except ValueError:
                        print(f"Invalid {param_type} value for {name}. Please try again.")
                        continue
                    break
                print(f"{name} is required!")

        return args

    def _get_tool_arguments_auto(self, tool: dict, task: str, stream: bool = False) -> dict:
        """
        Use LLM to infer arguments automatically.
        If stream=True, stream the LLM output to console.
        """
        tool_inputs = tool.get("inputSchema", {}).get("properties", {})
        if not tool_inputs:
            return {}

        # Build argument descriptions
        arg_descriptions = []
        for name, info in tool_inputs.items():
            param_type = info.get('type', 'string')
            description = info.get('description', '')
            arg_descriptions.append(f"- {name} ({param_type}): {description}")

        prompt = f"""Task: {task}
Tool: {tool['name']}
Arguments needed:
{chr(10).join(arg_descriptions)}

Generate ONLY a JSON object with the arguments. Extract values from the task."""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a JSON generator. Respond ONLY with valid JSON. "
                    "No explanations, no markdown, just the JSON object."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        if stream:
            self._call_llm(messages, console_stream=True)
            return {}
        else:
            response = self._call_llm(messages, console_stream=False) or ""
            try:
                # Extract JSON from markdown code blocks if present
                json_str = response.strip()
                if json_str.startswith("```json") and json_str.endswith("```"):
                    json_str = json_str[7:-3].strip()
                elif json_str.startswith("```") and json_str.endswith("```"):
                    json_str = json_str[3:-3].strip()

                args = json.loads(json_str)
                # Convert types based on schema
                converted_args: dict[Any, Any] = {}
                for k, v in args.items():
                    if k in tool_inputs:
                        param_type = tool_inputs[k].get('type', 'string')
                        try:
                            if param_type == "integer" and v is not None:
                                converted_args[k] = int(v)
                            elif param_type == "number" and v is not None:
                                converted_args[k] = float(v)
                            elif param_type == "boolean" and v is not None:
                                converted_args[k] = bool(v)
                            else:
                                converted_args[k] = v
                        except (ValueError, TypeError):
                            logging.warning("Failed to convert argument %s to %s: %s", k, param_type, v)
                            converted_args[k] = v
                return converted_args
            except (json.JSONDecodeError, TypeError):
                logging.warning("LLM failed to produce valid JSON for tool arguments: %s", response)
                return {}

    def execute_task(self, task: str, manual: bool = False, stream: bool = False) -> str | None:
        """Execute one or more relevant tools for a task and combine results."""
        if not self.available_tools:
            return "No tools available."

        selected_tools = self._select_tools(task)
        if not selected_tools:
            return "No relevant tools found for this task."

        print(f"Selected tools: {', '.join([t['name'] for t in selected_tools])}")

        tool_outputs = []

        for tool in selected_tools:
            try:
                client = self.tool_to_client[tool["name"]]

                # Decide argument source based on manual/auto
                if manual:
                    arguments = self._get_tool_arguments_manual(tool)
                else:
                    arguments = self._get_tool_arguments_auto(tool, task)

                # Call the tool with the arguments
                result = client.call_tool(tool["name"], arguments)

                if "error" in result:
                    tool_outputs.append(f"{tool['name']} error: {result['error']['message']}")
                elif result.get("result", {}).get("isError"):
                    tool_outputs.append(f"{tool['name']} execution failed.")
                else:
                    # Safely extract text content
                    content_list = result.get("result", {}).get("content", [])
                    if content_list and isinstance(content_list, list):
                        text = "\n".join(c.get("text", "") for c in content_list)
                    else:
                        text = str(result.get("result", {}))
                    tool_outputs.append(f"{tool['name']} result:\n{text}")

            except Exception as e:
                tool_outputs.append(f"{tool['name']} exception: {e}")

        combined_output = "\n\n".join(tool_outputs)
        return self._result(task, combined_output, stream)

    def execute_specific_tool(self, task: str, tool_name: str, manual: bool = False) -> str | None:
        """Execute a specific tool by name."""
        if not self.available_tools:
            return "No tools available."

        tool = next((t for t in self.available_tools if t["name"] == tool_name), None)
        if not tool:
            return f"Tool '{tool_name}' not found."

        try:
            client = self.tool_to_client[tool["name"]]

            if manual:
                arguments = self._get_tool_arguments_manual(tool)
            else:
                arguments = self._get_tool_arguments_auto(tool, task)

            result = client.call_tool(tool["name"], arguments)

            if "error" in result:
                return f"Error: {result['error']['message']}"
            elif result.get("result", {}).get("isError"):
                return "Tool execution failed."
            else:
                content_list = result.get("result", {}).get("content", [])
                if content_list and isinstance(content_list, list):
                    text = "\n".join(c.get("text", "") for c in content_list)
                else:
                    text = str(result.get("result", {}))
                return self._result(task, text) if task.strip() else text

        except Exception as e:
            return f"Error executing tool: {e}"

    def _select_tools(self, task: str) -> List[Dict[str, Any]]:
        """Select one or more tools that should be used for the task."""
        if not self.available_tools:
            return []

        if len(self.available_tools) == 1:
            return [self.available_tools[0]]

        tools_context = "Available tools:\n"
        for i, tool in enumerate(self.available_tools, 1):
            name = tool.get("name", "unknown")
            description = tool.get("description", "")
            tools_context += f"{i}. {name}: {description}\n"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that selects ALL relevant tools for a given task. "
                    "Respond ONLY with a comma-separated list of tool names. "
                    "If none are useful, respond with NONE."
                ),
            },
            {"role": "user", "content": f"Task: {task}\n\n{tools_context}"},
        ]

        response = self._call_llm(messages)
        if response:
            response = response.strip()
        if not response or response.upper() == "NONE":
            return []

        chosen = [name.strip().lower() for name in response.split(",")]
        return [t for t in self.available_tools if t["name"].lower() in chosen]

    def _result(self, task: str, content: str, stream: bool = False) -> str | None:
        """Format the tool result into a user-friendly response."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that formats and presents information clearly. "
                    "Understand the user request, analyze the raw tool output, and provide a "
                    "clear, well-structured answer."
                ),
            },
            {"role": "user", "content": f"Request: {task}\n\nRaw tool output:\n{content}"},
        ]
        result = self._call_llm(messages, console_stream=stream)
        if stream and result is None:
            print("")
        return result

    def close(self):
        """Shutdown all MCP clients."""
        for client in self.clients:
            try:
                client.close()
            except Exception as e:
                logging.debug("Error closing MCP client %s", e)
