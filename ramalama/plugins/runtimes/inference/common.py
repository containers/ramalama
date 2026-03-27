import argparse
import os
import sys
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
from ramalama.common import (
    ContainerEntryPoint,
    accel_image,
    ensure_image,
    genname,
    sanitize_filename,
    set_accel_env_vars,
)
from ramalama.config import ActiveConfig
from ramalama.engine import Engine
from ramalama.logger import logger
from ramalama.model_store.constants import DIRECTORY_NAME_BLOBS, DIRECTORY_NAME_REFS, DIRECTORY_NAME_SNAPSHOTS
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.model_store.reffile import RefJSONFile, StoreFileType, migrate_reffile_to_refjsonfile
from ramalama.path_utils import get_container_mount_path
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
        parser.add_argument(
            "--temp",
            dest="temp",
            type=float,
            default=config.temp,
            help="temperature of the response from the AI model",
            completer=suppressCompleter,
        )
        if command == "serve":
            parser.add_argument(
                "--host",
                default=config.host,
                help="IP address to listen",
                completer=suppressCompleter,
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
        parser.add_argument("MODEL", nargs="?", default=None, completer=local_models)  # positional argument
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

        if args.MODEL is None:
            return self._serve_router(args)

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

    def _serve_router(self, args: argparse.Namespace) -> None:
        """Serve all locally stored GGUF models using llama.cpp router mode (container-only)."""
        if not args.container:
            sys.exit("Error: router mode (ramalama serve with no model) requires a container runtime.")

        set_accel_env_vars()
        args.port = compute_serving_port(args)
        args.router_mode = True

        store = GlobalModelStore(args.store)
        models = _enumerate_store_gguf_models(
            store,
            DIRECTORY_NAME_REFS,
            DIRECTORY_NAME_SNAPSHOTS,
            DIRECTORY_NAME_BLOBS,
            RefJSONFile,
            migrate_reffile_to_refjsonfile,
        )

        if not models:
            sys.exit("Error: no GGUF models found in the model store. Pull a model first with: ramalama pull <model>")

        if args.container and not args.dryrun:
            config = ActiveConfig()
            should_pull = config.pull in ["always", "missing", "newer"]
            args.image = ensure_image(config.engine, accel_image(config), should_pull=should_pull)

        cmd = assemble_command(args)
        engine = Engine(args)
        name = getattr(args, "name", None) or genname()
        engine.add(["--label", "ai.ramalama", "--name", name, "--env=HOME=/tmp", "--init"])

        for host_path, container_name in models:
            mount_path = f"/mnt/models/{container_name}"
            container_host_path = get_container_mount_path(host_path)
            engine.add([f"--mount=type=bind,src={container_host_path},destination={mount_path},ro"])

        engine.add([args.image] + cmd)

        if args.dryrun:
            engine.dryrun()
            return
        engine.exec()


def _enumerate_store_gguf_models(store, refs_dir_name, snapshots_dir_name, blobs_dir_name, RefJSONFile, migrate_fn):
    """Walk the model store and return (host_blob_path, readable_name.gguf) for each GGUF model."""
    models = []
    seen_names = set()

    for root, subdirs, _ in os.walk(store.path):
        if refs_dir_name not in subdirs:
            continue

        ref_dir = os.path.join(root, refs_dir_name)
        for ref_file_name in os.listdir(ref_dir):
            ref_file_path = os.path.join(ref_dir, ref_file_name)
            ref_file = migrate_fn(ref_file_path, os.path.join(root, snapshots_dir_name))
            if ref_file is None:
                ref_file = RefJSONFile.from_path(ref_file_path)

            tag, _ = os.path.splitext(ref_file_name)
            model_rel = root.replace(store.path, "").lstrip(os.sep)
            parts = model_rel.split(os.sep)
            readable = "-".join(parts + [tag])

            for model_file in ref_file.model_files:
                if model_file.type != StoreFileType.GGUF_MODEL:
                    continue

                blob_path = os.path.join(root, blobs_dir_name, sanitize_filename(model_file.hash))
                if not os.path.exists(blob_path):
                    continue

                name = f"{readable}.gguf"
                if name in seen_names:
                    name = f"{readable}-{model_file.hash[:8]}.gguf"
                seen_names.add(name)
                models.append((blob_path, name))

    return models


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
