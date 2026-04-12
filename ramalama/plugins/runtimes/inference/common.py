from __future__ import annotations

import argparse
from abc import abstractmethod
from typing import Any

from ramalama.cli import (
    GENERATE_OPTIONS,
    OverrideDefaultAction,
    chat_run_options,
    local_models,
    parse_generate_option,
    parse_port_option,
    runtime_options,
    suppressCompleter,
)
from ramalama.common import ContainerEntryPoint, accel_image, ensure_image, set_accel_env_vars
from ramalama.config import ActiveConfig
from ramalama.config_types import PathStr
from ramalama.logger import logger
from ramalama.plugins.interface import InferenceRuntimePlugin
from ramalama.plugins.loader import assemble_command
from ramalama.stack import Stack
from ramalama.transports.api import APITransport
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New, TransportFactory


class BaseInferenceRuntime(InferenceRuntimePlugin):
    """Concrete base: registers run/serve subcommands and provides their handlers.

    Plugins that need only run/serve (e.g. MLX) inherit directly from this class.
    Plugins that also need container-dependent subcommands inherit
    from ContainerizedInferenceRuntimePlugin instead.
    """

    @abstractmethod
    def _cmd_run(self, args: argparse.Namespace) -> list[str]:
        """Build the command list for the 'run' subcommand."""

    @abstractmethod
    def _cmd_serve(self, args: argparse.Namespace) -> list[str]:
        """Build the command list for the 'serve' subcommand."""

    def handle_subcommand(self, command: str, args: argparse.Namespace) -> list[str]:
        """Dispatch to the appropriate _cmd_<command> method.

        Command strings map to method names by replacing '-' with '_',
        then prefixing with '_cmd_'.  Examples:
          'run'    → _cmd_run
          'serve'  → _cmd_serve
        """
        method_name = "_cmd_" + command.replace("-", "_")
        method = getattr(self, method_name, None)
        if method is None:
            raise NotImplementedError(f"{self.name} plugin does not implement command '{command}'")
        return method(args)

    def _add_inference_args(self, parser: "argparse.ArgumentParser", command: str) -> None:
        """Add inference-specific args shared across all runtimes for run/serve/perplexity."""
        config = ActiveConfig()
        parser.add_argument(
            "-c",
            "--ctx-size",
            dest="ctx_size",
            type=int,
            default=config.ctx_size,
            help="size of the prompt context (0 = loaded from model)",
            completer=suppressCompleter,
        )
        parser.add_argument(
            "--max-tokens",
            dest="max_tokens",
            type=int,
            default=config.max_tokens,
            help="maximum number of tokens to generate (0 = unlimited)",
            completer=suppressCompleter,
        )
        if command in ("run", "serve"):
            parser.add_argument(
                "-p",
                "--port",
                type=parse_port_option,
                default=config.port,
                action=OverrideDefaultAction,
                help="port for AI Model server to listen on",
                completer=suppressCompleter,
            )
        parser.add_argument(
            "--runtime-args",
            dest="runtime_args",
            default="",
            type=str,
            help="arguments to add to runtime invocation",
            completer=suppressCompleter,
        )
        if command == "serve":
            parser.add_argument(
                "--host",
                default=config.host,
                help="IP address to listen",
                completer=suppressCompleter,
            )
        elif command == "run":
            parser.add_argument(
                "--attach",
                type=PathStr,
                action='append',
                dest='attachments',
                help="add an attachment to the initial request, can be specified multiple times to add multiple files",
            )

    def register_subcommands(self, subparsers: "argparse._SubParsersAction") -> None:
        super().register_subcommands(subparsers)
        name_map = getattr(subparsers, "_name_parser_map", {})
        if "run" not in name_map:
            self._register_run_subcommand(subparsers)
        if "serve" not in name_map:
            self._register_serve_subcommand(subparsers)

    def _register_run_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = subparsers.add_parser("run", help="run specified AI Model as a chatbot")
        runtime_options(parser, "run")
        self._add_inference_args(parser, "run")
        parser.add_argument(
            "--keepalive",
            type=str,
            help="duration to keep a model loaded (e.g. 5m)",
        )
        chat_run_options(parser)
        parser.add_argument("MODEL", completer=local_models)  # positional argument
        parser.add_argument(
            "ARGS",
            nargs="*",
            help="overrides the default prompt, and the output is returned without entering the chatbot",
            completer=suppressCompleter,
        )
        parser._actions.sort(key=lambda x: x.option_strings)
        parser.set_defaults(func=self._run_handler)
        return parser

    def _register_serve_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = subparsers.add_parser("serve", help="serve REST API on specified AI Model")
        runtime_options(parser, "serve")
        self._add_inference_args(parser, "serve")
        parser.add_argument("MODEL", completer=local_models)  # positional argument
        parser.set_defaults(func=self._serve_handler)
        return parser

    def _do_run(self, args: argparse.Namespace, model: "Any") -> None:
        """Execute run after the model is resolved. Override to inject pre-run logic."""
        if isinstance(model, APITransport):
            model.run(args, [])
            return

        if args.container and not args.dryrun:
            config = ActiveConfig()
            should_pull = config.pull in ["always", "missing", "newer"]
            args.image = ensure_image(config.engine, accel_image(config), should_pull=should_pull)

        cmd = assemble_command(args)
        if len(cmd) > 0 and isinstance(cmd[0], ContainerEntryPoint):
            cmd = cmd[1:]
        process = model.serve_nonblocking(args, cmd)
        if process:
            model._connect_and_chat(args, process)

    def _do_serve(self, args: argparse.Namespace, model: "Any") -> None:
        """Execute serve after the model is resolved. Override to inject pre-serve logic."""
        set_accel_env_vars()
        if args.container and not args.dryrun:
            config = ActiveConfig()
            generate = getattr(args, "generate", None)
            should_pull = False if generate else config.pull in ["always", "missing", "newer"]
            args.image = ensure_image(config.engine, accel_image(config), should_pull=should_pull)

        cmd = assemble_command(args)
        if getattr(args, "generate", None):
            model.generate_container_config(args, cmd)
            return
        try:
            model.execute_command(cmd, args)
        except Exception as e:
            model._cleanup_server_process(getattr(args, "server_process", None))
            raise e
        # When serving in a detached container, wait for the server to become healthy before returning
        if (
            not getattr(args, "dryrun", False)
            and not getattr(args, "generate", None)
            and getattr(args, "container", False)
            and getattr(args, "detach", False)
        ):
            model.wait_for_healthy(args)

    def _run_handler(self, args: argparse.Namespace) -> None:
        try:
            # detect available port and update arguments
            args.port = compute_serving_port(args)
            model = New(args.MODEL, args)
            model.ensure_model_exists(args)
        except KeyError as e:
            logger.debug(e)
            try:
                args.quiet = True
                model = TransportFactory(args.MODEL, args, ignore_stderr=True).create_oci()
                model.ensure_model_exists(args)
            except Exception as exc:
                raise e from exc

        self._do_run(args, model)

    def _serve_handler(self, args: argparse.Namespace) -> None:
        if not args.container:
            args.detach = False

        if getattr(args, "api", None) == "llama-stack":
            if not args.container:
                raise ValueError(
                    "ramalama serve --api llama-stack command cannot be run with the --nocontainer option."
                )

            stack = Stack(args)
            return stack.serve()

        try:
            # detect available port and update arguments
            args.port = compute_serving_port(args)

            model = New(args.MODEL, args)
            model.ensure_model_exists(args)
        except KeyError as e:
            try:
                if "://" in args.MODEL:
                    raise e
                args.quiet = True
                model = TransportFactory(args.MODEL, args, ignore_stderr=True).create_oci()
                model.ensure_model_exists(args)
                # Since this is a OCI model, prepend oci://
                args.MODEL = f"oci://{args.MODEL}"

            except Exception:
                raise e

        if isinstance(model, APITransport):
            raise ValueError("ramalama serve is not supported for hosted API transports.")

        self._do_serve(args, model)


class ContainerizedInferenceRuntimePlugin(BaseInferenceRuntime):
    """Base class for inference plugins that support container-dependent args"""

    def _add_containerized_inference_args(self, parser: "argparse.ArgumentParser", command: str) -> None:
        config = ActiveConfig()
        parser.add_argument(
            "--api",
            default=config.api,
            choices=["llama-stack", "none"],
            help="unified API layer for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.",
        )
        if command == "serve":
            parser.add_argument(
                "--generate",
                type=parse_generate_option,
                choices=GENERATE_OPTIONS,
                help="generate specified configuration format for running the AI Model as a service",
            )
            parser.add_argument(
                "--add-to-unit",
                dest="add_to_unit",
                action='append',
                type=str,
                help="add KEY VALUE pair to generated unit file in the section SECTION (only valid with --generate)",
                metavar="SECTION:KEY:VALUE",
            )
            parser.add_argument(
                "--dri",
                dest="dri",
                choices=["on", "off"],
                default="on",
                help="mount /dev/dri into the container when running llama-stack (default: on)",
            )

    def _register_run_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_run_subcommand(subparsers)
        if ActiveConfig().container:
            self._add_containerized_inference_args(parser, "run")
        return parser

    def _register_serve_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_serve_subcommand(subparsers)
        if ActiveConfig().container:
            self._add_containerized_inference_args(parser, "serve")
        return parser
