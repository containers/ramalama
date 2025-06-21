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
from datetime import timedelta

from ramalama.config import CONFIG
from ramalama.console import EMOJI, should_colorize
from ramalama.engine import dry_run, stop_container


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
    if "LLAMA_PROMPT_PREFIX" in os.environ:
        return os.environ["LLAMA_PROMPT_PREFIX"]

    if not EMOJI:
        return "> "

    engine = CONFIG.engine

    if engine:
        if os.path.basename(engine) == "podman":
            return "🦭 > "

        if os.path.basename(engine) == "docker":
            return "🐋 > "

    return "🦙 > "


class RamaLamaShell(cmd.Cmd):
    def __init__(self, args):
        super().__init__()
        self.conversation_history = []
        self.args = args
        self.request_in_process = False
        self.prompt = args.prefix

        self.url = f"{args.url}/v1/chat/completions"

    def handle_args(self):
        if self.args.ARGS:
            self.default(" ".join(self.args.ARGS))
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
            "model": self.args.MODEL,
        }
        json_data = json.dumps(data).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        request = urllib.request.Request(self.url, data=json_data, headers=headers, method="POST")

        return request

    def _req(self):
        request = self._make_request_data()

        i = 0.01
        total_time_slept = 0
        response = None
        for c in itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']):
            try:
                response = urllib.request.urlopen(request)
                break
            except Exception:
                if sys.stdout.isatty():
                    print(f"\r{c}", end="", flush=True)

                if total_time_slept > 16:
                    break

                total_time_slept += i
                time.sleep(i)

                i = min(i * 2, 0.1)

        if response:
            return res(response, self.args.color)

        print(f"\rError: could not connect to: {self.url}", file=sys.stderr)
        self.kills()

        return None

    def kills(self):
        if self.args.pid2kill:
            os.kill(self.args.pid2kill, signal.SIGINT)
            os.kill(self.args.pid2kill, signal.SIGTERM)
            os.kill(self.args.pid2kill, signal.SIGKILL)
        elif self.args.name:
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


def chat(args):
    if args.dryrun:
        prompt = dry_run(args.ARGS)
        print(f"\nramalama chat --color {args.color} --prefix  \"{args.prefix}\" --url {args.url} {prompt}")
        return
    if hasattr(args, "keepalive") and args.keepalive:
        signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(convert_to_seconds(args.keepalive))

    try:
        shell = RamaLamaShell(args)
        if shell.handle_args():
            return
        shell.loop()
    except TimeoutException:
        # Handle the timeout, e.g., print a message and exit gracefully
        print("")
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
