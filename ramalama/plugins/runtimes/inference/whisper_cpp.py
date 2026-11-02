from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from http.client import HTTPConnection
from typing import Any, Optional, cast

from ramalama.arg_types import TranscribeArgsType
from ramalama.cli import OverrideDefaultAction, local_models, parse_port_option, runtime_options, suppressCompleter
from ramalama.common import ContainerEntryPoint, accel_image, ensure_image, set_accel_env_vars
from ramalama.config import ActiveConfig, ensure_tmpdir
from ramalama.logger import logger
from ramalama.path_utils import get_container_mount_path
from ramalama.plugins.runtimes.inference.common import BaseInferenceRuntime
from ramalama.transports.api import APITransport
from ramalama.transports.transport_factory import New

_WHISPER_IMAGE_REPO = "ghcr.io/ggml-org/whisper.cpp"
_WHISPER_DEFAULT_IMAGE = f"{_WHISPER_IMAGE_REPO}:main"
_WHISPER_ARM64_IMAGE = f"{_WHISPER_IMAGE_REPO}:main-arm64"
_WHISPER_ARM64_VULKAN_IMAGE = f"{_WHISPER_IMAGE_REPO}:main-vulkan-arm64"

# GPU type (as reported by get_gpu_type_env_vars) to the published image that
# matches it. There is no ROCm build, so HIP falls back to Vulkan below.
_WHISPER_IMAGES: dict[str, str] = {
    "CUDA_VISIBLE_DEVICES": f"{_WHISPER_IMAGE_REPO}:main-cuda",
    "GGML_VK_VISIBLE_DEVICES": f"{_WHISPER_IMAGE_REPO}:main-vulkan",
    "HIP_VISIBLE_DEVICES": f"{_WHISPER_IMAGE_REPO}:main-vulkan",
    "INTEL_VISIBLE_DEVICES": f"{_WHISPER_IMAGE_REPO}:main-intel",
    "MUSA_VISIBLE_DEVICES": f"{_WHISPER_IMAGE_REPO}:main-musa",
}

_AUDIO_DEST_DIR = "/mnt/audio"


@dataclass
class WhisperCppConfig:
    language: str = "auto"
    threads: Optional[int] = None

    def __post_init__(self):
        if self.threads is not None:
            self.threads = int(self.threads)
        if not self.language:
            self.language = "auto"


def _is_arm64() -> bool:
    return platform.machine().lower() in ("arm64", "aarch64")


def _default_image_for_gpu(gpu_type: str) -> Optional[str]:
    if gpu_type == "HIP_VISIBLE_DEVICES":
        logger.warning("No ROCm whisper.cpp image is published; using the Vulkan image for the detected AMD GPU.")
    if _is_arm64():
        if gpu_type in ("GGML_VK_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES"):
            return _WHISPER_ARM64_VULKAN_IMAGE
        return _WHISPER_ARM64_IMAGE
    return _WHISPER_IMAGES.get(gpu_type)


def _audio_container_path(audio: str) -> str:
    """Container path the audio file is mounted at.

    The destination is fixed rather than following the host file name: a comma
    in a file name would break the --mount=type=bind option.
    """
    ext = os.path.splitext(os.path.basename(audio))[1]
    return f"{_AUDIO_DEST_DIR}/input{ext}"


def _selinux_relabel(args: TranscribeArgsType) -> str:
    if args.selinux and os.path.basename(str(args.engine)) == "podman":
        return ",z"
    return ""


class WhisperCppPlugin(BaseInferenceRuntime):
    config_type = WhisperCppConfig

    @property
    def name(self) -> str:
        return "whisper.cpp"

    def get_container_image(self, config: Any, detected_gpu_type: str) -> Optional[str]:
        if detected_gpu_type:
            image = config.images.get(f"WHISPER_{detected_gpu_type}")
            if image:
                return image

        image = config.images.get("WHISPER")
        if image:
            return image

        if detected_gpu_type:
            image = _default_image_for_gpu(detected_gpu_type)
            if image:
                return image

        return _WHISPER_ARM64_IMAGE if _is_arm64() else _WHISPER_DEFAULT_IMAGE

    def _add_inference_args(self, parser: "argparse.ArgumentParser", command: str, *, tls: bool = True) -> None:
        config = ActiveConfig()
        rt_config = self.get_runtime_config(config)
        if command == "serve":
            # Also parsed by "ramalama sandbox", which borrows the serve options
            # and computes a serving port even for runtimes without their own
            # port option.
            parser.add_argument(
                "-p",
                "--port",
                type=parse_port_option,
                default=config.port,
                action=OverrideDefaultAction,
                help="port for whisper-server to listen on",
                completer=suppressCompleter,
            )
        if command == "serve":
            parser.add_argument(
                "--host",
                default=config.host,
                help="IP address to listen",
                completer=suppressCompleter,
            )
        parser.add_argument(
            "-l",
            "--language",
            dest="language",
            default=rt_config.language,
            help="spoken language of the audio, or 'auto' to detect it",
            completer=suppressCompleter,
        )
        parser.add_argument(
            "-t",
            "--threads",
            dest="threads",
            type=int,
            default=rt_config.threads,
            help="number of CPU threads to use",
            completer=suppressCompleter,
        )
        if command == "transcribe":
            parser.add_argument(
                "--translate",
                action="store_true",
                help="translate the audio to English instead of transcribing it",
            )
        parser.add_argument(
            "--runtime-args",
            dest="runtime_args",
            default="",
            type=str,
            help="arguments to add to runtime invocation",
            completer=suppressCompleter,
        )

    def register_subcommands(self, subparsers: "argparse._SubParsersAction") -> None:
        # Run comes from BaseInferenceRuntime but whisper.cpp has no chat
        # equivalent, so only transcribe and serve are registered here.
        parser = subparsers.add_parser("transcribe", help="transcribe audio to text")
        runtime_options(parser, "transcribe")
        self._add_inference_args(parser, "transcribe")
        parser.add_argument("MODEL", completer=local_models)
        parser.add_argument(
            "AUDIO",
            nargs="?",
            default=None,
            help="audio file to transcribe, or '-' to read the audio from stdin",
        )
        parser.set_defaults(func=self._transcribe_handler)
        self._register_serve_subcommand(subparsers)

    def _cmd_run(self, args: argparse.Namespace) -> list[str]:
        raise NotImplementedError("whisper.cpp does not support 'run'; use 'transcribe' instead")

    def service_ready_check(self, conn: HTTPConnection, args: Any, model_name: Optional[str] = None) -> bool:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        container_name = f"container {args.name}" if getattr(args, 'container', None) else 'server'
        if resp.status != 200:
            # whisper-server answers 503 until the model has finished loading.
            logger.debug(f"{self.name} {container_name} /health status code: {resp.status}: {resp.reason}")
            return False
        logger.debug(f"{self.name} {container_name} is ready")
        return True

    def _cmd_serve(self, args: argparse.Namespace) -> list[str]:
        is_container = args.container
        cmd: list[str] = []
        if is_container:
            # whisper-server only listens on 127.0.0.1 by default, while the
            # published port reaches the container's external interface.
            cmd.append(ContainerEntryPoint("whisper-server"))
            host = "::"
        else:
            cmd.append("whisper-server")
            host = args.host

        model = New(args.MODEL, args)
        model_path = model._get_entry_model_path(is_container, False, args.dryrun)

        cmd += ["-m", model_path, "--host", str(host), "--port", str(args.port)]
        cmd += ["-l", args.language or "auto"]
        if args.threads is not None:
            cmd += ["-t", str(args.threads)]
        if args.runtime_args:
            cmd.extend(args.runtime_args)

        return cmd

    def _cmd_transcribe(self, args: TranscribeArgsType) -> list[str]:
        if args.AUDIO is None:
            raise ValueError("transcribe requires an audio file, or audio piped to stdin")

        is_container = args.container
        cmd: list[str] = []
        if is_container:
            cmd.append(ContainerEntryPoint("whisper-cli"))
            audio = _audio_container_path(args.AUDIO)
        else:
            cmd.append("whisper-cli")
            audio = args.AUDIO

        model = New(args.MODEL, args)
        model_path = model._get_entry_model_path(is_container, False, args.dryrun)

        cmd += ["-m", model_path, "-f", audio, "-otxt", "-of", "-", "-np"]
        cmd += ["-l", args.language or "auto"]
        if args.translate:
            cmd.append("-tr")
        if args.threads is not None:
            cmd += ["-t", str(args.threads)]
        if args.runtime_args:
            cmd.extend(args.runtime_args)

        return cmd

    def _spool_stdin(self, world_readable: bool) -> str:
        ensure_tmpdir(ActiveConfig())
        # A private (0700) directory keeps other host users out even when the file
        # itself must be world-readable for the container user.
        spool_dir = tempfile.mkdtemp(prefix="ramalama-transcribe-")
        path = os.path.join(spool_dir, "input.wav")
        try:
            with open(path, "wb") as spool:
                shutil.copyfileobj(sys.stdin.buffer, spool)
            if world_readable:
                # The container user must be able to read the bind-mounted file.
                os.chmod(path, 0o644)
        except BaseException:
            # The caller never learns the name if this fails, so remove it here.
            shutil.rmtree(spool_dir, ignore_errors=True)
            raise
        return path

    def _audio_mount(self, audio: str, args: TranscribeArgsType) -> str:
        mount_src = get_container_mount_path(audio)
        if "," in mount_src:
            raise ValueError(f"audio path must not contain a comma when running in a container: {audio}")
        return (
            f"--mount=type=bind,src={mount_src},destination={_audio_container_path(audio)},ro{_selinux_relabel(args)}"
        )

    def _transcribe_handler(self, args: TranscribeArgsType) -> None:
        audio = args.AUDIO
        spooled: Optional[str] = None
        try:
            if audio is None or audio == "-":
                if sys.stdin.isatty():
                    raise ValueError("transcribe requires an audio file, or audio piped to stdin")
                spooled = self._spool_stdin(bool(args.container))
                audio = spooled
            args.AUDIO = audio

            model = New(args.MODEL, args)
            model.ensure_model_exists(args)

            if isinstance(model, APITransport):
                raise NotImplementedError("transcribe is not supported for hosted API transports.")

            set_accel_env_vars()
            if args.container:
                if not args.dryrun:
                    config = ActiveConfig()
                    should_pull = config.pull in ["always", "missing", "newer"]
                    args.image = ensure_image(
                        config.engine, accel_image(config), should_pull=should_pull, quiet=args.quiet
                    )
                args.engine_args = [*(args.engine_args or []), self._audio_mount(audio, args)]

            model.execute_command(self.handle_subcommand("transcribe", cast(argparse.Namespace, args)), args)
        finally:
            if spooled is not None:
                # Best effort: exec_cmd ends in sys.exit() and Windows can keep
                # the file locked while the child process is still shutting down.
                shutil.rmtree(os.path.dirname(spooled), ignore_errors=True)
