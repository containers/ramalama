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

from ramalama.config import CONFIG
from ramalama.console import EMOJI
from ramalama.model import should_colorize


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
        return ""

    engine = CONFIG.engine

    if os.path.basename(engine) == "podman":
        return "🦭 > "

    if os.path.basename(engine) == "docker":
        return "🐋 > "

    return "> "


class RamaLamaShell(cmd.Cmd):
    def __init__(self, args):
        super().__init__()
        self.conversation_history = []
        self.args = args
        self.request_in_process = False
        self.prompt = args.prefix

        self.url = f"{args.url}/v1/chat/completions"
        self.models_url = f"{args.url}/v1/models"
        self.models = []

    def model(self, index=0):
        try:
            if len(self.models) == 0:
                self.models = self.get_models()
            return self.models[index]
        except urllib.error.URLError:
            return ""

    def get_models(self):
        request = urllib.request.Request(self.models_url, method="GET")
        response = urllib.request.urlopen(request)
        for line in response:
            line = line.decode("utf-8").strip()
            return [d['id'] for d in json.loads(line)["data"]]

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
            "model": self.model(),
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
