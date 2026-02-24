import argparse
import json
import os
from dataclasses import asdict
from http.client import HTTPConnection
from typing import Any

from ramalama.logger import logger
from ramalama.plugins.runtimes.common import ContainerizedInferenceRuntimePlugin
from ramalama.plugins.runtimes.llama_cpp_commands import (
    _CACHE_REUSE_DEFAULT,
    _NGL_DEFAULT,
    _THINKING_DEFAULT,
    LlamaCppCommands,
    _default_threads,
)

_LLAMA_CPP_IMAGES: dict[str, str] = {
    "ASAHI_VISIBLE_DEVICES": "quay.io/ramalama/asahi",
    "ASCEND_VISIBLE_DEVICES": "quay.io/ramalama/cann",
    "CUDA_VISIBLE_DEVICES": "quay.io/ramalama/cuda",
    "GGML_VK_VISIBLE_DEVICES": "quay.io/ramalama/ramalama",
    "HIP_VISIBLE_DEVICES": "quay.io/ramalama/rocm",
    "INTEL_VISIBLE_DEVICES": "quay.io/ramalama/intel-gpu",
    "MUSA_VISIBLE_DEVICES": "quay.io/ramalama/musa",
}


class LlamaCppPlugin(LlamaCppCommands, ContainerizedInferenceRuntimePlugin):
    @property
    def name(self) -> str:
        return "llama.cpp"

    def _convert_to_gguf(self, outdir, source_model, args):
        """Run convert_hf_to_gguf.py inside a container to produce a GGUF file."""
        import copy
        import shutil
        import tempfile

        from ramalama.engine import Engine

        with tempfile.TemporaryDirectory(prefix="RamaLama_convert_src_") as srcdir:
            ref_file = source_model.model_store.get_ref_file(source_model.model_tag)
            for file in ref_file.files:
                blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
                shutil.copyfile(blob_file_path, os.path.join(srcdir, file.name))
            engine = Engine(args)
            engine.add_volume(srcdir, "/model")
            engine.add_volume(outdir.name, "/output", opts="rw")
            args = copy.copy(args)
            args.model = source_model
            engine.add_args(args.rag_image)
            engine.add_args(*self._cmd_convert(args))
            if args.dryrun:
                engine.dryrun()
            else:
                engine.run()
        return self._quantize(source_model, args, outdir.name)

    def _quantize(self, source_model, args, model_dir):
        """Run llama-quantize inside a container to quantize a GGUF model."""
        import copy

        from ramalama.engine import Engine

        engine = Engine(args)
        engine.add_volume(model_dir, "/model", opts="rw")
        engine.add_args(args.image)
        args = copy.copy(args)
        args.subcommand = "quantize"
        engine.add_args(*self._cmd_quantize(args))
        if args.dryrun:
            engine.dryrun()
        else:
            engine.run()
        return f"{source_model.model_name}-{args.gguf}.gguf"

    def is_healthy(self, conn: HTTPConnection, args: Any, model_name: str | None = None) -> bool:
        conn.request("GET", "/health")
        health_resp = conn.getresponse()
        health_resp.read()
        if health_resp.status not in (200, 404):
            logger.debug(f"Container {args.name} /health status code: {health_resp.status}: {health_resp.reason}")
            return False

        conn.request("GET", "/models")
        models_resp = conn.getresponse()
        if models_resp.status != 200:
            logger.debug(f"Container {args.name} /models status code {models_resp.status}: {models_resp.reason}")
            return False

        content = models_resp.read()
        if not content:
            logger.debug(f"Container {args.name} /models returned an empty response")
            return False

        body = json.loads(content)
        if "models" not in body:
            logger.debug(f"Container {args.name} /models does not include a model list in the response")
            return False

        model_names = [m["name"] for m in body["models"]]
        if not model_name:
            # Inline import to avoid circular dependency
            from ramalama.transports.transport_factory import New

            model_name = New(args.MODEL, args).model_alias

        if not any(model_name in name for name in model_names):
            logger.debug(
                f'Container {args.name} /models does not include "{model_name}" in the model list: {model_names}'
            )
            return False

        logger.debug(f"Container {args.name} is healthy")
        return True

    def get_container_image(self, config: Any, gpu_type: str) -> str | None:
        # User override from [ramalama.images] takes precedence
        override = config.images.get(gpu_type) if gpu_type else None
        image = override if override else _LLAMA_CPP_IMAGES.get(gpu_type, config.default_image)
        return image if ":" in image else f"{image}:latest"

    # --- subcommand registration ---

    def _add_llama_cpp_inference_args(self, parser: "argparse.ArgumentParser", command: str) -> None:
        """Add llama.cpp-specific inference args to an already-created parser."""
        from ramalama.cli import (
            CoerceToBool,
            local_models,
            suppressCompleter,
        )

        parser.add_argument(
            "--cache-reuse",
            dest="cache_reuse",
            type=int,
            default=_CACHE_REUSE_DEFAULT,
            help="min chunk size to attempt reusing from the cache via KV shifting",
            completer=suppressCompleter,
        )
        parser.add_argument(
            "--logfile",
            dest="logfile",
            type=str,
            help="log output to a file",
            completer=suppressCompleter,
        )
        parser.add_argument(
            "--ngl",
            dest="ngl",
            type=int,
            default=_NGL_DEFAULT,
            help="number of layers to offload to the gpu, if available",
            completer=suppressCompleter,
        )
        parser.add_argument(
            "--thinking",
            default=_THINKING_DEFAULT,
            help="enable/disable thinking mode in reasoning models",
            action=CoerceToBool,
        )
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

        if command == "serve":
            parser.add_argument("--model-draft", help="Draft model", completer=local_models)
            parser.add_argument(
                "--webui",
                dest="webui",
                choices=["on", "off"],
                default="on",
                help="enable or disable the web UI (default: on)",
            )

    def _register_run_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_run_subcommand(subparsers)
        self._add_llama_cpp_inference_args(parser, "run")
        return parser

    def _register_serve_subcommand(self, subparsers: "argparse._SubParsersAction") -> "argparse.ArgumentParser":
        parser = super()._register_serve_subcommand(subparsers)
        self._add_llama_cpp_inference_args(parser, "serve")
        return parser

    def register_subcommands(self, subparsers: "argparse._SubParsersAction") -> None:
        super().register_subcommands(subparsers)
        # Function-level imports avoid circular dependency: cli.py imports plugins at
        # module level, but register_subcommands() is only called after cli.py is fully
        # initialized (from configure_subcommands()), so these imports are always safe.
        from ramalama.cli import (
            OverrideDefaultAction,
            add_network_argument,
            default_image,
            default_rag_image,
            local_images,
            local_models,
            runtime_options,
            suppressCompleter,
        )

        # bench / benchmark
        bench_parser = subparsers.add_parser("bench", aliases=["benchmark"], help="benchmark specified AI Model")
        runtime_options(bench_parser, "bench")
        # llama.cpp-specific bench args
        bench_parser.add_argument(
            "--ngl",
            dest="ngl",
            type=int,
            default=_NGL_DEFAULT,
            help="number of layers to offload to the gpu, if available",
            completer=suppressCompleter,
        )
        def_threads = _default_threads()
        bench_parser.add_argument(
            "-t",
            "--threads",
            type=int,
            default=def_threads,
            help=(
                f"number of cpu threads to use, the default is {def_threads} on this system, -1 means use this default"
            ),
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
        # llama.cpp-specific perplexity args
        perplexity_parser.add_argument(
            "--ngl",
            dest="ngl",
            type=int,
            default=_NGL_DEFAULT,
            help="number of layers to offload to the gpu, if available",
            completer=suppressCompleter,
        )
        perplexity_parser.add_argument(
            "-t",
            "--threads",
            type=int,
            default=def_threads,
            help=(
                f"number of cpu threads to use, the default is {def_threads} on this system, -1 means use this default"
            ),
            completer=suppressCompleter,
        )
        perplexity_parser.add_argument(
            "--cache-reuse",
            dest="cache_reuse",
            type=int,
            default=_CACHE_REUSE_DEFAULT,
            help="min chunk size to attempt reusing from the cache via KV shifting",
            completer=suppressCompleter,
        )
        perplexity_parser.add_argument("MODEL", completer=local_models)
        perplexity_parser.set_defaults(func=self._perplexity_handler)

        # convert
        from typing import get_args

        from ramalama.config import GGUF_QUANTIZATION_MODES, get_config

        config = get_config()
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
            "--rag-image",
            default=default_rag_image(),
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
        from ramalama.config import get_config

        config = get_config()
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

    def _convert_handler(self, args: argparse.Namespace) -> None:
        from ramalama.cli import _get_source_model, get_shortnames
        from ramalama.transports.transport_factory import TransportFactory

        if not args.container:
            raise ValueError("convert command cannot be run with the --nocontainer option.")

        shortnames = get_shortnames()
        tgt = shortnames.resolve(args.TARGET)
        model = TransportFactory(tgt, args).create_oci()
        source_model = _get_source_model(args)
        model.convert(source_model, args)

    def _bench_handler(self, args: argparse.Namespace) -> None:
        import json
        from datetime import datetime, timezone

        from ramalama.benchmarks.manager import BenchmarksManager
        from ramalama.benchmarks.schemas import BenchmarkRecord, get_benchmark_record
        from ramalama.benchmarks.utilities import parse_json, print_bench_results
        from ramalama.common import run_cmd, set_accel_env_vars
        from ramalama.config import get_config
        from ramalama.engine import dry_run
        from ramalama.plugins.loader import assemble_command
        from ramalama.transports.api import APITransport
        from ramalama.transports.transport_factory import New

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

        config = get_config()
        if not config.benchmarks.disable:
            BenchmarksManager(config.benchmarks.storage_folder).save(results)

    def _perplexity_handler(self, args: argparse.Namespace) -> None:
        from ramalama.common import set_accel_env_vars
        from ramalama.plugins.loader import assemble_command
        from ramalama.transports.api import APITransport
        from ramalama.transports.transport_factory import New

        model = New(args.MODEL, args)
        model.ensure_model_exists(args)

        if isinstance(model, APITransport):
            raise NotImplementedError("perplexity is not supported for hosted API transports.")

        set_accel_env_vars()
        model.execute_command(assemble_command(args), args)

    def _benchmarks_list_handler(self, args: argparse.Namespace) -> None:
        from ramalama.benchmarks.manager import BenchmarksManager
        from ramalama.benchmarks.utilities import print_bench_results
        from ramalama.config import get_config

        config = get_config()
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
