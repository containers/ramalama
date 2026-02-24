import argparse
from urllib.parse import urlparse

from ramalama.path_utils import file_uri_to_path
from ramalama.plugins.interface import InferenceRuntimePlugin


class AddPathOrUrl(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not isinstance(values, list):
            raise ValueError("AddPathOrUrl can only be used with the settings `nargs='+'`")
        setattr(namespace, self.dest, [])
        namespace.urls = []
        for value in values:
            parsed = urlparse(value)
            if parsed.scheme in ["http", "https"]:
                namespace.urls.append(value)
            else:
                getattr(namespace, self.dest).append(file_uri_to_path(value))


class BaseInferenceRuntime(InferenceRuntimePlugin):
    """Concrete base: registers run/serve subcommands and provides their handlers.

    Plugins that need only run/serve (e.g. MLX) inherit directly from this class.
    Plugins that also need RAG or other container-dependent subcommands inherit
    from ContainerizedInferenceRuntimePlugin instead.
    """

    def _add_inference_args(self, parser: "argparse.ArgumentParser", command: str) -> None:
        """Add inference-specific args shared across all runtimes for run/serve/perplexity."""
        from ramalama.cli import OverrideDefaultAction, parse_port_option, suppressCompleter
        from ramalama.config import get_config

        config = get_config()
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
        from ramalama.cli import chat_run_options, local_models, runtime_options, suppressCompleter

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
        from ramalama.cli import local_models, runtime_options

        parser = subparsers.add_parser("serve", help="serve REST API on specified AI Model")
        runtime_options(parser, "serve")
        self._add_inference_args(parser, "serve")
        parser.add_argument("MODEL", completer=local_models)  # positional argument
        parser.set_defaults(func=self._serve_handler)
        return parser

    def _run_handler(self, args: argparse.Namespace) -> None:
        from ramalama.cli import _rag_args
        from ramalama.common import ContainerEntryPoint
        from ramalama.logger import logger
        from ramalama.plugins.loader import assemble_command
        from ramalama.rag import RagTransport
        from ramalama.transports.api import APITransport
        from ramalama.transports.base import compute_serving_port
        from ramalama.transports.transport_factory import New, TransportFactory

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

        if getattr(args, "rag", None):
            if isinstance(model, APITransport):
                raise ValueError("ramalama run --rag is not supported for hosted API transports.")
            if not args.container:
                raise ValueError("ramalama run --rag cannot be run with the --nocontainer option.")
            args = _rag_args(args)

            model = RagTransport(model, assemble_command(args.model_args), args)
            model.ensure_model_exists(args)
            model.run(args, assemble_command(args))
            return

        if isinstance(model, APITransport):
            model.run(args, [])
            return

        cmd = assemble_command(args)
        if len(cmd) > 0 and isinstance(cmd[0], ContainerEntryPoint):
            cmd = cmd[1:]
        process = model.serve_nonblocking(args, cmd)
        if process:
            model._connect_and_chat(args, process)

    def _serve_handler(self, args: argparse.Namespace) -> None:
        from ramalama.cli import _rag_args
        from ramalama.common import set_accel_env_vars
        from ramalama.plugins.loader import assemble_command
        from ramalama.rag import RagTransport
        from ramalama.stack import Stack
        from ramalama.transports.api import APITransport
        from ramalama.transports.base import compute_serving_port
        from ramalama.transports.transport_factory import New, TransportFactory

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

        if getattr(args, "rag", None):
            if not args.container:
                raise ValueError("ramalama serve --rag cannot be run with the --nocontainer option.")
            args = _rag_args(args)

            model = RagTransport(model, assemble_command(args.model_args), args)
            model.ensure_model_exists(args)
            model.serve(args, assemble_command(args))
            return

        set_accel_env_vars()
        cmd = assemble_command(args)
        if getattr(args, "generate", None):
            model.generate_container_config(args, cmd)
            return
        try:
            model.execute_command(cmd, args)
        except Exception as e:
            model._cleanup_server_process(getattr(args, "server_process", None))
            raise e


class ContainerizedInferenceRuntimePlugin(BaseInferenceRuntime):
    """Base class for inference plugins that support container-dependent subcommands.

    Extends BaseInferenceRuntime with the 'rag' subcommand. 'rag' requires a
    container engine to run the RAG pipeline alongside the model, so it is only
    registered when containers are enabled (i.e. not --nocontainer).
    """

    def register_subcommands(self, subparsers: "argparse._SubParsersAction") -> None:
        from ramalama.config import get_config

        super().register_subcommands(subparsers)
        name_map = getattr(subparsers, "_name_parser_map", {})
        if "rag" not in name_map and get_config().container:
            self._register_rag_subcommand(subparsers)

    def _add_rag_args(self, parser: "argparse.ArgumentParser") -> None:
        from ramalama.cli import OverrideDefaultAction, default_rag_image, local_images, local_models

        parser.add_argument(
            "--rag", help="RAG vector database or OCI Image to be served with the model", completer=local_models
        )
        parser.add_argument(
            "--rag-image",
            default=default_rag_image(),
            help="OCI container image to run with the specified RAG data",
            action=OverrideDefaultAction,
            completer=local_images,
        )

    def _add_containerized_inference_args(self, parser: "argparse.ArgumentParser", command: str) -> None:
        from ramalama.cli import GENERATE_OPTIONS, parse_generate_option
        from ramalama.config import get_config

        config = get_config()
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
        self._add_containerized_inference_args(parser, "run")
        self._add_rag_args(parser)
        return parser

    def _register_serve_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_serve_subcommand(subparsers)
        self._add_containerized_inference_args(parser, "serve")
        self._add_rag_args(parser)
        return parser

    def _register_rag_subcommand(self, subparsers: "argparse._SubParsersAction") -> None:
        from textwrap import dedent

        from ramalama.cli import (
            CoerceToBool,
            OverrideDefaultAction,
            add_network_argument,
            default_rag_image,
            local_env,
            local_images,
            suppressCompleter,
        )
        from ramalama.config import get_config

        config = get_config()
        parser = subparsers.add_parser(
            "rag",
            help="generate and convert retrieval augmented generation (RAG) data from provided "
            "documents into an OCI Image",
        )
        parser.add_argument(
            "--env",
            dest="env",
            action='append',
            type=str,
            default=config.env,
            help="environment variables to add to the running RAG container",
            completer=local_env,
        )
        parser.add_argument(
            "--format",
            default=config.rag_format,
            help="Output format for RAG Data",
            choices=["qdrant", "json", "markdown", "milvus"],
        )
        parser.add_argument(
            "--image",
            default=default_rag_image(),
            help="Image to use for generating RAG data",
            action=OverrideDefaultAction,
            completer=local_images,
        )
        parser.add_argument(
            "--keep-groups",
            dest="podman_keep_groups",
            default=config.keep_groups,
            action="store_true",
            help=(
                "pass `--group-add keep-groups` to podman.\n"
                "If GPU device on host is accessible to via group access, "
                "this option leaks the user groups into the container."
            ),
        )
        add_network_argument(parser, dflt=None)
        parser.add_argument(
            "--pull",
            dest="pull",
            type=str,
            default=config.pull,
            choices=["always", "missing", "never", "newer"],
            help='pull image policy',
        )
        parser.add_argument(
            "--selinux",
            default=config.selinux,
            action=CoerceToBool,
            help="Enable SELinux container separation",
        )
        parser.add_argument(
            "PATHS",
            nargs="+",
            help=dedent("""
        Files/URLs/Directory containing PDF, DOCX, PPTX, XLSX, HTML, AsciiDoc & Markdown
        formatted files to be processed"""),
            action=AddPathOrUrl,
        )
        parser.add_argument(
            "DESTINATION", help="Path or OCI Image name to contain processed rag data", completer=suppressCompleter
        )
        parser.add_argument(
            "--ocr",
            dest="ocr",
            default=config.ocr,
            action="store_true",
            help="Enable embedded image text extraction from PDF (Increases RAM Usage significantly)",
        )
        parser.set_defaults(func=self._rag_handler)

    def _rag_handler(self, args: argparse.Namespace) -> None:
        from ramalama import rag as rag_module
        from ramalama.plugins.loader import assemble_command

        rag = rag_module.Rag(args.DESTINATION)
        args.inputdir = rag_module.INPUT_DIR
        rag.generate(args, assemble_command(args))
