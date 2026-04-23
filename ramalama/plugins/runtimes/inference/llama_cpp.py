from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from http.client import HTTPConnection
from typing import Any, Optional, get_args
from urllib.parse import urlparse

from ramalama.benchmarks.manager import BenchmarksManager
from ramalama.benchmarks.schemas import BenchmarkRecord, get_benchmark_record
from ramalama.benchmarks.utilities import parse_json, print_bench_results
from ramalama.cli import (
    CoerceToBool,
    OverrideDefaultAction,
    _get_source_model,
    _rag_args,
    add_network_argument,
    default_image,
    default_rag_image,
    default_tools_image,
    get_shortnames,
    local_images,
    local_models,
    runtime_options,
    suppressCompleter,
)
from ramalama.common import (
    accel_image,
    ensure_image,
    get_gpu_type_env_vars,
    run_cmd,
    set_accel_env_vars,
    set_gpu_type_env_vars,
    version_tagged_image,
)
from ramalama.config import GGUF_QUANTIZATION_MODES, ActiveConfig, DefaultConfig
from ramalama.engine import Engine, dry_run, image_inspect
from ramalama.logger import logger
from ramalama.path_utils import file_uri_to_path
from ramalama.plugins.loader import assemble_command
from ramalama.plugins.runtimes.inference.common import ContainerizedInferenceRuntimePlugin
from ramalama.plugins.runtimes.inference.llama_cpp_commands import (
    _CACHE_REUSE_DEFAULT,
    _NGL_DEFAULT,
    _THINKING_DEFAULT,
    LlamaCppCommands,
    _default_threads,
)
from ramalama.rag import RagTransport
from ramalama.transports.api import APITransport
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New, TransportFactory


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


def get_gpu_backend_preferences(gpu_type: str) -> list[str]:
    """Returns preferred backends for a given GPU type in order of preference.
    On Windows, vulkan is not supported on WSL2, so vendor backends are preferred."""
    is_windows = platform.system() == "Windows"

    preferences = {
        "HIP_VISIBLE_DEVICES": ["vulkan", "rocm"],  # AMD: Vulkan preferred
        "CUDA_VISIBLE_DEVICES": ["cuda"],  # NVIDIA: CUDA only
        "INTEL_VISIBLE_DEVICES": ["vulkan", "sycl", "openvino"],  # Intel: Vulkan preferred
        "ASAHI_VISIBLE_DEVICES": ["vulkan"],  # Asahi: Vulkan only
        "ASCEND_VISIBLE_DEVICES": ["cann"],  # Ascend: CANN only
        "MUSA_VISIBLE_DEVICES": ["musa"],  # MUSA: MUSA only
        "GGML_VK_VISIBLE_DEVICES": ["vulkan"],  # Vulkan: Vulkan only
    }

    if is_windows:
        preferences["HIP_VISIBLE_DEVICES"] = ["rocm", "vulkan"]
        preferences["INTEL_VISIBLE_DEVICES"] = ["sycl", "vulkan", "openvino"]

    return preferences.get(gpu_type, [])


def backend_to_gpu_env(backend: str) -> str:
    """Maps a backend name to its corresponding GPU environment variable."""
    mapping = {
        "vulkan": "GGML_VK_VISIBLE_DEVICES",
        "rocm": "HIP_VISIBLE_DEVICES",
        "cuda": "CUDA_VISIBLE_DEVICES",
        "sycl": "INTEL_VISIBLE_DEVICES",
        "openvino": "OPENVINO_VISIBLE_DEVICES",
        "cann": "ASCEND_VISIBLE_DEVICES",
        "musa": "MUSA_VISIBLE_DEVICES",
        "asahi": "ASAHI_VISIBLE_DEVICES",
    }
    return mapping.get(backend, "")


def get_available_backends() -> list[str]:
    """Returns available backends based on detected GPU, in preference order.
    Always includes 'auto' as the first option."""
    set_gpu_type_env_vars()
    gpu_type = next(iter(get_gpu_type_env_vars()), "")

    if gpu_type:
        preferences = get_gpu_backend_preferences(gpu_type)
        if preferences:
            return ["auto"] + preferences

    return ["auto", "vulkan"]


_LLAMA_CPP_IMAGES: dict[str, str] = {
    "ASAHI_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/asahi"),
    "ASCEND_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/cann"),
    "CUDA_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/cuda"),
    "GGML_VK_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/ramalama"),
    "HIP_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/rocm"),
    "INTEL_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/intel-gpu"),
    "OPENVINO_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/openvino"),
    "MUSA_VISIBLE_DEVICES": version_tagged_image("quay.io/ramalama/musa"),
}


class LlamaCppPlugin(LlamaCppCommands, ContainerizedInferenceRuntimePlugin):
    @property
    def name(self) -> str:
        return "llama.cpp"

    def _convert_to_gguf(self, outdir, source_model, args):
        """Run convert_hf_to_gguf.py inside a container to produce a GGUF file."""
        with tempfile.TemporaryDirectory(prefix="RamaLama_convert_src_") as srcdir:
            ref_file = source_model.model_store.get_ref_file(source_model.model_tag)
            for file in ref_file.files:
                blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
                shutil.copyfile(blob_file_path, os.path.join(srcdir, file.name))
            engine = Engine(args)
            if engine.use_docker:
                # The uid in the container must match the euid on the host for contents of the
                # volumes to be readable.
                if hasattr(os, "geteuid"):
                    # Note: geteuid() doesn't exist on Windows, but this is only needed on Unix
                    engine.add_args(f"--user={os.geteuid()}")
            engine.add_volume(srcdir, "/model")
            engine.add_volume(outdir.name, "/output", opts="rw")
            args = copy.copy(args)
            args.model = source_model
            if not args.dryrun:
                config = ActiveConfig()
                should_pull = config.pull in ["always", "missing", "newer"]
                args.tools_image = ensure_image(args.engine, args.tools_image, should_pull=should_pull)
            engine.add_args(args.tools_image)
            engine.add_args(*self._cmd_convert(args))
            if args.dryrun:
                engine.dryrun()
            else:
                engine.run()
        return self._quantize(source_model, args, outdir.name)

    def _quantize(self, source_model, args, model_dir):
        """Run llama-quantize inside a container to quantize a GGUF model."""
        engine = Engine(args)
        if engine.use_docker:
            # The uid in the container must match the euid on the host for contents of the
            # volumes to be readable.
            if hasattr(os, "geteuid"):
                # Note: geteuid() doesn't exist on Windows, but this is only needed on Unix
                engine.add_args(f"--user={os.geteuid()}")
        engine.add_volume(model_dir, "/model", opts="rw")
        if not args.dryrun:
            config = ActiveConfig()
            should_pull = config.pull in ["always", "missing", "newer"]
            args.image = ensure_image(args.engine, args.image, should_pull=should_pull)
        engine.add_args(args.image)
        args = copy.copy(args)
        args.subcommand = "quantize"
        engine.add_args(*self._cmd_quantize(args))
        if args.dryrun:
            engine.dryrun()
        else:
            engine.run()
        return f"{source_model.model_name}-{args.gguf}.gguf"

    def service_ready_check(self, conn: HTTPConnection, args: Any, model_name: Optional[str] = None) -> bool:
        container_name = f"container {args.name}" if getattr(args, 'container', None) else 'server'
        conn.request("GET", "/health")
        health_resp = conn.getresponse()
        health_resp.read()
        if health_resp.status not in (200, 404):
            logger.debug(f"{self.name} {container_name} /health {health_resp.status}: {health_resp.reason}")

            return False

        conn.request("GET", "/models")
        models_resp = conn.getresponse()
        if models_resp.status != 200:
            logger.debug(f"{self.name} {container_name} /models status code {models_resp.status}: {models_resp.reason}")
            return False

        content = models_resp.read()
        if not content:
            logger.debug(f"{self.name} {container_name} /models returned an empty response")
            return False

        body = json.loads(content)
        if "models" not in body:
            logger.debug(f"{self.name} {container_name} /models does not include a model list in the response")
            return False

        model_names = [m["name"] for m in body["models"]]
        if not model_name:
            model_name = New(args.MODEL, args).model_alias

        if not any(model_name in name for name in model_names):
            logger.debug(
                f'{self.name} {container_name} /models does not include "{model_name}" in the model list: {model_names}'
            )
            return False

        logger.debug(f"{self.name} {container_name} is ready")
        return True

    def get_container_image(self, config: Any, detected_gpu_type: str) -> Optional[str]:
        backend = config.backend
        if backend == "auto":
            preferences = get_gpu_backend_preferences(detected_gpu_type)
            if preferences:
                gpu_type = backend_to_gpu_env(preferences[0])
                logger.debug(f"Auto mode selected {preferences[0]} backend for {detected_gpu_type}")
            else:
                gpu_type = detected_gpu_type
        else:
            gpu_type = backend_to_gpu_env(backend)
            if detected_gpu_type:
                preferences = get_gpu_backend_preferences(detected_gpu_type)
                if preferences and backend not in preferences:
                    gpu_name = detected_gpu_type.replace("_VISIBLE_DEVICES", "")
                    logger.warning(
                        f"Backend '{backend}' may not be compatible with detected {gpu_name} GPU. "
                        f"Recommended backends for {gpu_name}: {', '.join(preferences)}"
                    )

        override = config.images.get(gpu_type) if gpu_type else None
        return override if override else _LLAMA_CPP_IMAGES.get(gpu_type, config.default_image)

    def _container_image_is_ggml(self, args: argparse.Namespace) -> bool:
        if not args.container or args.dryrun:
            return False
        image = accel_image(ActiveConfig())
        default_image = accel_image(DefaultConfig())
        if image == default_image:
            return False
        try:
            image_entrypoint = image_inspect(args, image, format="{{ .Config.Entrypoint }}")
        except Exception as e:
            logger.debug(f"Error inspecting image {image}: {e}")
            return False  # Assume default image (non-ggml)
        # Upstream llama.cpp full image uses a wrapper script as the entrypoint
        return "tools.sh" in image_entrypoint

    # --- subcommand registration ---

    def _add_backend_arg(self, parser: "argparse.ArgumentParser") -> None:
        config = ActiveConfig()
        parser.add_argument(
            "--backend",
            dest="backend",
            default=config.backend,
            choices=get_available_backends(),
            help="GPU backend to use (auto, vulkan, rocm, cuda, sycl, openvino). See man page for details.",
        )

    def _add_ngl_arg(self, parser: "argparse.ArgumentParser") -> None:
        parser.add_argument(
            "--ngl",
            dest="ngl",
            type=int,
            default=_NGL_DEFAULT,
            help="number of layers to offload to the gpu, if available",
            completer=suppressCompleter,
        )

    def _add_threads_arg(self, parser: "argparse.ArgumentParser") -> None:
        def_threads = _default_threads()
        parser.add_argument(
            "-t",
            "--threads",
            type=int,
            default=def_threads,
            help=(
                f"number of cpu threads to use, the default is {def_threads} on this system, -1 means use this default"
            ),
            completer=suppressCompleter,
        )

    def _add_inference_args(self, parser: "argparse.ArgumentParser", command: str) -> None:
        """Add llama.cpp-specific inference args to an already-created parser."""
        super()._add_inference_args(parser, command)
        config = ActiveConfig()
        parser.add_argument(
            "--temp",
            dest="temp",
            type=float,
            default=config.temp,
            help="temperature of the response from the AI model",
            completer=suppressCompleter,
        )
        self._add_backend_arg(parser)
        parser.add_argument(
            "--cache-reuse",
            dest="cache_reuse",
            type=int,
            default=_CACHE_REUSE_DEFAULT,
            help="min chunk size to attempt reusing from the cache via KV shifting",
            completer=suppressCompleter,
        )
        self._add_ngl_arg(parser)
        if command in ["run", "serve"]:
            parser.add_argument(
                "--logfile",
                dest="logfile",
                type=str,
                help="log output to a file",
                completer=suppressCompleter,
            )
            parser.add_argument(
                "--thinking",
                default=_THINKING_DEFAULT,
                help="enable/disable thinking mode in reasoning models",
                action=CoerceToBool,
            )
        self._add_threads_arg(parser)
        if command == "serve":
            parser.add_argument("--model-draft", help="Draft model", completer=local_models)
            parser.add_argument(
                "--webui",
                dest="webui",
                choices=["on", "off"],
                default="on",
                help="enable or disable the web UI (default: on)",
            )

    @staticmethod
    def _set_openvino_env(args: argparse.Namespace) -> None:
        """Set OpenVINO env vars when Intel GPU is detected (llama.cpp-specific)."""
        if not os.environ.get("INTEL_VISIBLE_DEVICES"):
            return

        openvino_env = [
            f"GGML_OPENVINO_DEVICE={os.environ.get('GGML_OPENVINO_DEVICE', 'GPU')}",
            f"GGML_OPENVINO_STATEFUL_EXECUTION={os.environ.get('GGML_OPENVINO_STATEFUL_EXECUTION', 1)}",
        ]
        args.env = openvino_env + getattr(args, "env", [])

    def handle_subcommand(self, command: str, args: argparse.Namespace) -> list[str]:
        set_accel_env_vars()
        self._set_openvino_env(args)
        return super().handle_subcommand(command, args)

    def _do_run(self, args: argparse.Namespace, model: Any) -> None:
        if getattr(args, "rag", None):
            if isinstance(model, APITransport):
                raise ValueError("ramalama run --rag is not supported for hosted API transports.")
            self._run_rag(args, model)
            return
        super()._do_run(args, model)

    def _do_serve(self, args: argparse.Namespace, model: Any) -> None:
        if getattr(args, "rag", None):
            self._serve_rag(args, model)
            return
        super()._do_serve(args, model)

    def _add_rag_args(self, parser: "argparse.ArgumentParser") -> None:
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

    def _run_rag(self, args: argparse.Namespace, model: Any) -> None:
        if not args.container:
            raise ValueError("ramalama run --rag cannot be run with the --nocontainer option.")
        args = _rag_args(args)
        model = RagTransport(model, assemble_command(args.model_args), args)
        model.ensure_model_exists(args)
        embed_serve_args, embed_proc = self._start_rag_embedding_server(args)
        try:
            model.run(args, assemble_command(args))
        finally:
            from ramalama.plugins.runtimes.inference.rag.handler import _cleanup_servers

            _cleanup_servers(args, [embed_serve_args], [embed_proc])

    def _serve_rag(self, args: argparse.Namespace, model: Any) -> None:
        if not args.container:
            raise ValueError("ramalama serve --rag cannot be run with the --nocontainer option.")
        args = _rag_args(args)
        model = RagTransport(model, assemble_command(args.model_args), args)
        model.ensure_model_exists(args)
        embed_serve_args, embed_proc = self._start_rag_embedding_server(args)
        try:
            model.serve(args, assemble_command(args))
        finally:
            from ramalama.plugins.runtimes.inference.rag.handler import _cleanup_servers

            _cleanup_servers(args, [embed_serve_args], [embed_proc])

    def _start_rag_embedding_server(self, args):
        """Start a llama.cpp embedding server for RAG inference and set embed_url on args."""
        from ramalama.plugins.runtimes.inference.rag.handler import EMBEDDING_MODEL, _build_serve_args, _wait_for_server

        embedding_model = EMBEDDING_MODEL
        set_accel_env_vars()

        embed_port = compute_serving_port(args, quiet=True, exclude=[args.port, args.model_args.port])
        embed_serve_args = _build_serve_args(args.model_args, embedding_model, embed_port, runtime_args=["--embedding"])
        # Internal models should always be pullable regardless of the user's --pull flag
        embed_serve_args.pull = ActiveConfig().pull

        embed_transport = New(embedding_model, embed_serve_args)
        if isinstance(embed_transport, APITransport):
            raise ValueError(
                f"embedding model {embedding_model} resolved to an API transport, which cannot serve locally"
            )
        embed_transport.ensure_model_exists(embed_serve_args)

        embed_cmd = assemble_command(embed_serve_args)
        embed_proc = embed_transport.serve_nonblocking(embed_serve_args, embed_cmd)

        if not args.dryrun:
            _wait_for_server("127.0.0.1", int(embed_port))

        if args.model_args.engine == "podman":
            embed_host = "host.containers.internal"
        else:
            embed_host = f"host.{args.model_args.engine}.internal"

        args.embed_url = f"http://{embed_host}:{embed_port}"
        return embed_serve_args, embed_proc

    def _register_run_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_run_subcommand(subparsers)
        self._add_rag_args(parser)
        return parser

    def _register_serve_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_serve_subcommand(subparsers)
        self._add_rag_args(parser)
        return parser

    def register_subcommands(self, subparsers: "argparse._SubParsersAction") -> None:
        super().register_subcommands(subparsers)

        # bench / benchmark
        bench_parser = subparsers.add_parser("bench", aliases=["benchmark"], help="benchmark specified AI Model")
        runtime_options(bench_parser, "bench")
        self._add_backend_arg(bench_parser)
        self._add_ngl_arg(bench_parser)
        self._add_threads_arg(bench_parser)
        bench_parser.add_argument(
            "--runtime-args",
            dest="runtime_args",
            default="",
            type=str,
            help="arguments to add to runtime invocation",
            completer=suppressCompleter,
        )
        bench_parser.add_argument("MODEL", completer=local_models)
        bench_parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="output format (table or json)",
        )
        bench_parser.set_defaults(func=self._bench_handler)

        # perplexity
        perplexity_parser = subparsers.add_parser("perplexity", help="calculate perplexity for specified AI Model")
        runtime_options(perplexity_parser, "perplexity")
        self._add_inference_args(perplexity_parser, "perplexity")
        perplexity_parser.add_argument("MODEL", completer=local_models)
        perplexity_parser.set_defaults(func=self._perplexity_handler)

        # convert
        config = ActiveConfig()
        convert_parser = subparsers.add_parser(
            "convert",
            help="convert AI Model from local storage to OCI Image",
            formatter_class=argparse.RawTextHelpFormatter,
        )
        convert_parser.add_argument("--carimage", default=config.carimage, help=argparse.SUPPRESS)
        convert_parser.add_argument(
            "--gguf",
            choices=get_args(GGUF_QUANTIZATION_MODES),
            nargs="?",
            const=config.gguf_quantization_mode,
            default=None,
            help=f"GGUF quantization format. If specified without value, {config.gguf_quantization_mode} is used.",
        )
        add_network_argument(convert_parser)
        convert_parser.add_argument(
            "--tools-image",
            default=default_tools_image(),
            help="Image to use for conversion to GGUF",
            action=OverrideDefaultAction,
            completer=local_images,
        )
        convert_parser.add_argument(
            "--image",
            default=default_image(),
            help="Image to use for quantization",
            action=OverrideDefaultAction,
            completer=local_images,
        )
        convert_parser.add_argument(
            "--pull",
            dest="pull",
            type=str,
            default=config.pull,
            choices=["always", "missing", "never", "newer"],
            help="pull image policy",
        )
        convert_parser.add_argument(
            "--type",
            default=config.convert_type,
            choices=["artifact", "car", "raw"],
            help="""\
type of OCI Model Image to push.

Model "artifact" stores the AI Model as an OCI Artifact.
Model "car" includes base image with the model stored in a /models subdir.
Model "raw" contains the model and a link file model.file to it stored at /.""",
        )
        convert_parser.add_argument("SOURCE")
        convert_parser.add_argument("TARGET")
        convert_parser.set_defaults(func=self._convert_handler)

        # benchmarks (manage stored results)
        config = ActiveConfig()
        storage_folder = config.benchmarks.storage_folder
        epilog = f"Storage folder: {storage_folder}" if storage_folder else "Storage folder: not configured"
        benchmarks_parser = subparsers.add_parser(
            "benchmarks",
            help="manage and view benchmark results",
            epilog=epilog,
        )
        benchmarks_parser.set_defaults(func=lambda _: benchmarks_parser.print_help())
        benchmarks_subparsers = benchmarks_parser.add_subparsers(dest="benchmarks_command", metavar="[command]")
        benchmarks_list_parser = benchmarks_subparsers.add_parser("list", help="list benchmark results")
        benchmarks_list_parser.add_argument(
            "--limit", type=int, default=None, help="limit number of results to display"
        )
        benchmarks_list_parser.add_argument("--offset", type=int, default=0, help="offset for pagination")
        benchmarks_list_parser.add_argument(
            "--format", choices=["table", "json"], default="table", help="output format (table or json)"
        )
        benchmarks_list_parser.set_defaults(func=self._benchmarks_list_handler)

        # rag
        name_map = getattr(subparsers, "_name_parser_map", {})
        if "rag" not in name_map and ActiveConfig().container:
            self._register_rag_subcommand(subparsers)

    def _register_rag_subcommand(self, subparsers: "argparse._SubParsersAction") -> None:
        from ramalama.plugins.runtimes.inference.rag.cli import register_rag_subcommand

        register_rag_subcommand(self, subparsers)

    def _convert_handler(self, args: argparse.Namespace) -> None:
        if not args.container:
            raise ValueError("convert command cannot be run with the --nocontainer option.")

        shortnames = get_shortnames()
        tgt = shortnames.resolve(args.TARGET)
        model = TransportFactory(tgt, args).create_oci()
        source_model = _get_source_model(args)
        model.convert(source_model, args)

    def _bench_handler(self, args: argparse.Namespace) -> None:
        model = New(args.MODEL, args)
        model.ensure_model_exists(args)

        if isinstance(model, APITransport):
            raise NotImplementedError("bench is not supported for hosted API transports.")

        cmd = assemble_command(args)
        set_accel_env_vars()
        output_format = getattr(args, "format", "table")

        if args.dryrun:
            if args.container:
                model.setup_container(args)
                model.setup_mounts(args)
                model.engine.add([args.image] + cmd)
                model.engine.dryrun()
            else:
                dry_run(cmd)
            return

        if args.container:
            model.setup_container(args)
            model.setup_mounts(args)
            model.engine.add([args.image] + cmd)
            result = model.engine.run_process()
        else:
            result = run_cmd(cmd, encoding="utf-8")

        try:
            bench_results = parse_json(result.stdout)
        except (json.JSONDecodeError, ValueError):
            raise ValueError(f"Could not parse benchmark output. Expected JSON but got:\n{result.stdout}")

        base_payload: dict = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "configuration": {
                "container_image": args.image,
                "container_runtime": args.engine,
                "inference_engine": args.runtime,
                "runtime_args": cmd,
            },
        }
        results: list[BenchmarkRecord] = [
            get_benchmark_record({"result": r, **base_payload}, "v1") for r in bench_results
        ]

        if output_format == "json":
            print(result.stdout)
        else:
            print_bench_results(results)

        config = ActiveConfig()
        if not config.benchmarks.disable:
            BenchmarksManager(config.benchmarks.storage_folder).save(results)

    def _perplexity_handler(self, args: argparse.Namespace) -> None:
        model = New(args.MODEL, args)
        model.ensure_model_exists(args)

        if isinstance(model, APITransport):
            raise NotImplementedError("perplexity is not supported for hosted API transports.")

        set_accel_env_vars()
        model.execute_command(assemble_command(args), args)

    def _benchmarks_list_handler(self, args: argparse.Namespace) -> None:
        config = ActiveConfig()
        bench_manager = BenchmarksManager(config.benchmarks.storage_folder)
        results = bench_manager.list()

        if not results:
            print("No benchmark results found")
            return

        if args.format == "json":
            output = [asdict(item) for item in results]
            print(json.dumps(output, indent=2, sort_keys=True))
        else:
            print_bench_results(results)
