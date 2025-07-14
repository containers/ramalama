#!/usr/bin/env python3

import cmd
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
            line = line[len("data: ") :]
            choice = json.loads(line)["choices"][0]["delta"]
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
        self.conversation_history = []
        self.args = args
        self.request_in_process = False
        self.prompt = args.prefix
        self.url = f"{args.url}/chat/completions"
        self.prep_rag_message()

        self.operational_args = operational_args

    def prep_rag_message(self):
        if (context := self.args.rag) is None:
            return

        builder = OpanAIChatAPIMessageBuilder()
        messages = builder.load(context)
        self.conversation_history.extend(messages)

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
        if user_content in ["/bye", "exit"]:
            return True

        self.conversation_history.append({"role": "user", "content": user_content})
        self.request_in_process = True
        response = self._req()
        if not response:
            return True

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
        # Don't kill the server if we're still in the initial connection phase
        if getattr(self.args, "initial_connection", False):
            return

        if getattr(self.args, "pid2kill", False):
            os.kill(self.args.pid2kill, signal.SIGINT)
            os.kill(self.args.pid2kill, signal.SIGTERM)
            os.kill(self.args.pid2kill, signal.SIGKILL)
        elif getattr(self.args, "name", None):
            stop_container(self.args, self.args.name)

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
    shell.kills()


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
