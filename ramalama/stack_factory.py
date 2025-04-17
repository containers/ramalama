import argparse
from typing import Callable

from ramalama.stack import Stack


class StackFactory:

    def __init__(
        self,
        distro: str,
        args: argparse,
        transport: str = "ollama",
        ignore_stderr: bool = False,
    ):
        self.distro = distro
        self.store_path = args.store
        self.use_model_store = args.use_model_store
        self.transport = transport
        self.engine = args.engine
        self.ignore_stderr = ignore_stderr
        self.container = args.container

        self.create: Callable[[], Stack]

    def create(self) -> Stack:
        stack = Stack(self.distro)
        return stack
