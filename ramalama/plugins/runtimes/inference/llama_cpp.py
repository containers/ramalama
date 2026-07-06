from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import shutil
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http.client import HTTPConnection
from typing import Any, Literal, Optional, get_args
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
    genname,
    get_gpu_type_env_vars,
    run_cmd,
    set_accel_env_vars,
    set_gpu_type_env_vars,
    version_tagged_image,
)
from ramalama.config import ActiveConfig, DefaultConfig, coerce_to_bool
from ramalama.engine import Engine, dry_run, image_inspect
from ramalama.logger import logger
from ramalama.model_store.constants import DIRECTORY_NAME_BLOBS, DIRECTORY_NAME_REFS, DIRECTORY_NAME_SNAPSHOTS
from ramalama.model_store.global_store import GlobalModelStore
from ramalama.model_store.reffile import RefJSONFile, migrate_reffile_to_refjsonfile
from ramalama.path_utils import file_uri_to_path, get_container_mount_path
from ramalama.plugins.loader import assemble_command
from ramalama.plugins.runtimes.inference.common import ContainerizedInferenceRuntimePlugin, enumerate_store_gguf_models
from ramalama.plugins.runtimes.inference.llama_cpp_commands import (
    LlamaCppCommands,
    _default_threads,
)
from ramalama.rag import RagTransport
from ramalama.transports.api import APITransport
from ramalama.transports.base import compute_serving_port
from ramalama.transports.transport_factory import New, TransportFactory

GGUF_QUANTIZATION_MODES = Literal[
    "Q2_K",
    "Q3_K_S",
    "Q3_K_M",
    "Q3_K_L",
    "Q4_0",
    "Q4_K_S",
    "Q4_K_M",
    "Q5_0",
    "Q5_K_S",
    "Q5_K_M",
    "Q6_K",
    "Q8_0",
]
DEFAULT_GGUF_QUANTIZATION_MODE: GGUF_QUANTIZATION_MODES = "Q4_K_M"  # type: ignore[assignment]


@dataclass
class LlamaCppConfig:
    backend: Literal["auto", "vulkan", "rocm", "cuda", "sycl", "openvino", "cann", "musa"] = "auto"
    cache_reuse: Optional[int] = None
    gguf_quantization_mode: GGUF_QUANTIZATION_MODES = DEFAULT_GGUF_QUANTIZATION_MODE  # type: ignore[assignment]
    ngl: Optional[str] = None
    ncmoe: Optional[int] = None
    temp: float = 0.8
    thinking: Optional[bool] = None
    threads: int = field(default_factory=_default_threads)

    def __post_init__(self):
        if self.cache_reuse is not None:
            self.cache_reuse = int(self.cache_reuse)
        if self.ngl is not None:
            self.ngl = str(self.ngl)
        if self.ncmoe is not None:
            self.ncmoe = int(self.ncmoe)
        self.temp = float(self.temp)
        self.threads = int(self.threads)
        if self.thinking is not None:
            self.thinking = coerce_to_bool(self.thinking)


def _positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"--models-max must be a positive integer, got {value}")
    return ivalue


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


def parse_models_payload(payload: Any) -> list[str]:
    """Parse model identifiers from a llama-server /models response body."""
    if not isinstance(payload, Mapping):
        raise ValueError("Invalid model list payload")

    if isinstance(payload.get("models"), list):
        models: list[str] = []
        for entry in payload["models"]:
            if not isinstance(entry, Mapping):
                continue
            if name := entry.get("name") or entry.get("model"):
                models.append(str(name))
        return models

    if isinstance(payload.get("data"), list):
        models = []
        for entry in payload["data"]:
            if isinstance(entry, Mapping) and (model_id := entry.get("id")):
                models.append(str(model_id))
        return models

    raise ValueError("Invalid model list payload")


class LlamaCppPlugin(LlamaCppCommands, ContainerizedInferenceRuntimePlugin):
    config_type = LlamaCppConfig

    @property
    def name(self) -> str:
        return "llama.cpp"

    def _convert_to_gguf(self, outdir, source_model, args):
        """Run llama-convert-hf-to-gguf inside a container to produce a GGUF file."""
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
                args.tools_image = ensure_image(
                    args.engine, args.tools_image, should_pull=should_pull, quiet=getattr(args, "quiet", False)
                )
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
            args.image = ensure_image(
                args.engine, args.image, should_pull=should_pull, quiet=getattr(args, "quiet", False)
            )
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
        try:
            model_names = parse_models_payload(body)
        except ValueError:
            logger.debug(f"{self.name} {container_name} /models does not include a model list in the response")
            return False

        if not model_name:
            if hasattr(args, 'MODEL') and isinstance(args.MODEL, str):
                model_name = New(args.MODEL, args).model_alias
            else:
                if not model_names:
                    logger.debug(f"{self.name} {container_name} /models returned no available models yet")
                    return False
                logger.debug(f"{self.name} {container_name} is ready (router mode)")
                return True

        if model_name not in model_names:
            logger.debug(
                f'{self.name} {container_name} /models does not include "{model_name}" in the model list: {model_names}'
            )
            return False

        logger.debug(f"{self.name} {container_name} is ready")
        return True

    def get_container_image(self, config: Any, detected_gpu_type: str) -> Optional[str]:
        rt_config = self.get_runtime_config(config)
        backend = rt_config.backend
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
        rt_config = self.get_runtime_config(ActiveConfig())
        parser.add_argument(
            "--backend",
            dest="backend",
            default=rt_config.backend,
            choices=get_available_backends(),
            help="GPU backend to use (auto, vulkan, rocm, cuda, sycl, openvino, cann, musa). See man page for details.",
        )

    def _add_ngl_arg(self, parser: "argparse.ArgumentParser") -> None:
        parser.add_argument(
            "--ngl",
            dest="ngl",
            default=None,
            help="number of layers to store in VRAM: a number, 'auto', or 'all' (default: auto)",
            completer=suppressCompleter,
        )

    def _add_ncmoe_arg(self, parser: "argparse.ArgumentParser") -> None:
        parser.add_argument(
            "--ncmoe",
            dest="ncmoe",
            type=int,
            help="keep the Mixture of Experts (MoE) weights of the first N layers in the CPU",
            completer=suppressCompleter,
        )

    def _add_threads_arg(self, parser: "argparse.ArgumentParser") -> None:
        rt_config = self.get_runtime_config(ActiveConfig())
        parser.add_argument(
            "-t",
            "--threads",
            type=int,
            default=rt_config.threads,
            help=(
                f"number of cpu threads to use, the default is {rt_config.threads} on this system,"
                " -1 means use this default"
            ),
            completer=suppressCompleter,
        )

    def _add_inference_args(self, parser: "argparse.ArgumentParser", command: str) -> None:
        """Add llama.cpp-specific inference args to an already-created parser."""
        super()._add_inference_args(parser, command)
        rt_config = self.get_runtime_config(ActiveConfig())
        parser.add_argument(
            "--temp",
            dest="temp",
            type=float,
            default=rt_config.temp,
            help="temperature of the response from the AI model",
            completer=suppressCompleter,
        )
        self._add_backend_arg(parser)
        parser.add_argument(
            "--cache-reuse",
            dest="cache_reuse",
            type=int,
            default=None,
            help="min chunk size to attempt reusing from the cache via KV shifting",
            completer=suppressCompleter,
        )
        self._add_ngl_arg(parser)
        self._add_ncmoe_arg(parser)
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
                default=None,
                help="enable/disable thinking mode in reasoning models",
                action=CoerceToBool,
            )
            parser.add_argument("--model-draft", help="Draft model", completer=local_models)
        self._add_threads_arg(parser)
        if command == "serve":
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

    def _serve_handler(self, args: argparse.Namespace) -> None:
        if not args.container:
            args.detach = False

        if len(args.MODEL) != 1:
            return self._serve_router(args)

        args.MODEL = args.MODEL[0]
        if isinstance(getattr(args, "model", None), list):
            args.model = args.MODEL

        super()._serve_handler(args)

    def _serve_router(self, args: argparse.Namespace) -> None:
        """Serve multiple models using llama.cpp router mode (container-only)."""
        if not args.container:
            sys.exit("Error: multi-model router mode requires a container runtime.")

        set_accel_env_vars()
        args.port = compute_serving_port(args)
        args.router_mode = True

        if args.MODEL:
            models = self._resolve_specified_models(args)
        else:
            store = GlobalModelStore(args.store)
            self._migrate_store_ref_files(store)
            models = enumerate_store_gguf_models(
                store,
                DIRECTORY_NAME_REFS,
                DIRECTORY_NAME_BLOBS,
                RefJSONFile,
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

    @staticmethod
    def _migrate_store_ref_files(store: Any) -> None:
        """Migrate any old-format ref files to JSON before enumeration."""
        for root, subdirs, _ in os.walk(store.path):
            if DIRECTORY_NAME_REFS not in subdirs:
                continue
            ref_dir = os.path.join(root, DIRECTORY_NAME_REFS)
            for ref_file_name in os.listdir(ref_dir):
                ref_file_path = os.path.join(ref_dir, ref_file_name)
                migrate_reffile_to_refjsonfile(ref_file_path, os.path.join(root, DIRECTORY_NAME_SNAPSHOTS))

    @staticmethod
    def _resolve_specified_models(args: argparse.Namespace) -> list[tuple[str, str]]:
        """Resolve user-specified model names to (host_blob_path, container_name.gguf) tuples."""
        models: list[tuple[str, str]] = []
        seen_names: set[str] = set()
        for model_name in args.MODEL:
            model = New(model_name, args)
            model.ensure_model_exists(args)
            host_path = model._get_entry_model_path(False, False, False)
            alias = model.model_alias.replace("/", "-")
            name = f"{alias}.gguf"
            if name in seen_names:
                i = 2
                candidate = f"{alias}-{i}.gguf"
                while candidate in seen_names:
                    i += 1
                    candidate = f"{alias}-{i}.gguf"
                name = candidate
            seen_names.add(name)
            models.append((host_path, name))
        return models

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
            _wait_for_server(self, embed_serve_args, embed_transport.model_alias)

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

    def _add_model_argument(self, parser: "argparse.ArgumentParser") -> None:
        parser.add_argument("MODEL", nargs="*", default=[], completer=local_models)

    def _register_serve_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_serve_subcommand(subparsers)
        self._add_rag_args(parser)
        parser.add_argument(
            "--models-max",
            dest="models_max",
            type=_positive_int,
            default=4,
            help="maximum number of models to load concurrently in router mode (default: 4)",
            completer=suppressCompleter,
        )
        return parser

    def register_subcommands(self, subparsers: "argparse._SubParsersAction") -> None:
        super().register_subcommands(subparsers)

        # bench / benchmark
        bench_parser = subparsers.add_parser("bench", aliases=["benchmark"], help="benchmark specified AI Model")
        runtime_options(bench_parser, "bench")
        self._add_backend_arg(bench_parser)
        self._add_ngl_arg(bench_parser)
        self._add_ncmoe_arg(bench_parser)
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
        rt_config = self.get_runtime_config(config)
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
            const=rt_config.gguf_quantization_mode,
            default=None,
            help=f"GGUF quantization format. If specified without value, {rt_config.gguf_quantization_mode} is used.",
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
        model = TransportFactory(tgt, args, transport="oci").create_oci()
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
