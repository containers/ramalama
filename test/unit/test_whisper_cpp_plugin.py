import io
import os
import re
import stat
import sys
import tempfile
from argparse import Namespace
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from ramalama.cli import ArgumentParserWithDefaults
from ramalama.common import ContainerEntryPoint
from ramalama.path_utils import get_container_mount_path
from ramalama.plugins.runtimes.inference.whisper_cpp import WhisperCppConfig, WhisperCppPlugin
from ramalama.transports.base import Transport

WHISPER_IMAGE = "ghcr.io/ggml-org/whisper.cpp:main"
MODEL = "hf://ggerganov/whisper.cpp/ggml-base.en.bin"
MODEL_PATH = "/mnt/models/ggml-base.en.bin"


def make_config(images=None) -> MagicMock:
    config = MagicMock()
    config.images = images or {}
    return config


def make_transcribe_ns(
    AUDIO="a.wav",
    container=True,
    dryrun=False,
    engine="podman",
    selinux=False,
    language="auto",
    threads=None,
    translate=False,
    runtime_args=None,
) -> Namespace:
    return Namespace(
        MODEL=MODEL,
        AUDIO=AUDIO,
        container=container,
        dryrun=dryrun,
        engine=engine,
        selinux=selinux,
        language=language,
        threads=threads,
        translate=translate,
        runtime_args=runtime_args or [],
        engine_args=[],
        image=WHISPER_IMAGE,
        pull="never",
        quiet=True,
        noout=False,
    )


def make_serve_ns(
    container=True,
    dryrun=False,
    host="127.0.0.1",
    port="8080",
    language="auto",
    threads=None,
    runtime_args=None,
) -> Namespace:
    return Namespace(
        MODEL=MODEL,
        container=container,
        dryrun=dryrun,
        host=host,
        port=port,
        language=language,
        threads=threads,
        runtime_args=runtime_args or [],
    )


def make_model(entry_path=MODEL_PATH) -> MagicMock:
    model = MagicMock()
    model._get_entry_model_path.return_value = entry_path
    return model


class _FakeStdin:
    def __init__(self, data: bytes, tty: bool = False):
        self.buffer = io.BytesIO(data)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class TestWhisperCppConfig:
    def test_defaults(self):
        config = WhisperCppConfig()
        assert config.language == "auto"
        assert config.threads is None

    def test_coerces_threads(self):
        assert WhisperCppConfig(threads="8").threads == 8  # type: ignore[arg-type]

    def test_empty_language_falls_back_to_auto(self):
        assert WhisperCppConfig(language="").language == "auto"


class TestWhisperCppPlugin:
    def setup_method(self):
        self.plugin = WhisperCppPlugin()

    def test_name_and_config_key(self):
        assert self.plugin.name == "whisper.cpp"
        assert self.plugin.config_key == "whisper_cpp"
        assert self.plugin.config_type is WhisperCppConfig

    def test_run_is_not_supported(self):
        with pytest.raises(NotImplementedError, match="does not support 'run'"):
            self.plugin.handle_subcommand("run", make_transcribe_ns())

    def test_registered_via_entry_point(self):
        from ramalama.plugins.loader import get_all_runtimes

        runtimes = get_all_runtimes()
        plugin = runtimes.get("whisper.cpp")
        if plugin is None:
            pytest.skip("whisper.cpp entry point is not installed (pip install -e .)")
        assert isinstance(plugin, WhisperCppPlugin)

    def test_transcribe_and_serve_are_registered(self):
        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        self.plugin.register_subcommands(subparsers)

        name_map = subparsers._name_parser_map
        assert "transcribe" in name_map
        assert "serve" in name_map
        assert "run" not in name_map

    def test_help_lists_transcribe_and_serve_without_run(self):
        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        self.plugin.register_subcommands(subparsers)

        help_text = parser.format_help()

        assert re.search(r"\btranscribe\b", help_text)
        assert re.search(r"\bserve\b", help_text)
        assert not re.search(r"\brun\b", help_text)

    def test_transcribe_parser_defaults(self):
        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        self.plugin.register_subcommands(subparsers)

        args = parser.parse_args(["transcribe", MODEL])

        assert args.func.__self__ is self.plugin
        assert args.MODEL == MODEL
        assert args.AUDIO is None
        assert args.language == "auto"
        assert args.threads is None
        assert args.translate is False
        assert not hasattr(args, "ctx_size")
        assert not hasattr(args, "max_tokens")

    def test_transcribe_parser_accepts_whisper_options(self):
        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        self.plugin.register_subcommands(subparsers)

        args = parser.parse_args(["transcribe", "--translate", "-l", "fr", "-t", "2", "--runtime-args=-np", MODEL])

        assert args.translate is True
        assert args.language == "fr"
        assert args.threads == 2
        assert args.runtime_args == "-np"

    def test_serve_parser_defaults(self):
        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        self.plugin.register_subcommands(subparsers)

        args = parser.parse_args(["serve", MODEL])

        assert args.func.__self__ is self.plugin
        assert args.MODEL == MODEL
        assert args.port
        assert args.host
        assert args.language == "auto"
        assert not hasattr(args, "ctx_size")
        assert not hasattr(args, "max_tokens")
        assert not hasattr(args, "api")
        assert not hasattr(args, "generate")

    @pytest.mark.parametrize("flags", [["--generate", "quadlet"], ["--api", "llama-stack"]])
    def test_serve_rejects_llama_stack_options(self, flags):
        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        self.plugin.register_subcommands(subparsers)

        assert parser.parse_args(["serve", MODEL]).MODEL == MODEL
        with pytest.raises(SystemExit):
            parser.parse_args(["serve", *flags, MODEL])

    def test_sandbox_parser_builds_with_whisper_runtime(self):
        from ramalama.cli import sandbox_parser

        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        with patch("ramalama.sandbox.get_runtime", return_value=self.plugin):
            sandbox_parser(subparsers)

        sandbox_parser_obj = subparsers._name_parser_map["sandbox"]
        sandbox_subparsers = next(a for a in sandbox_parser_obj._actions if hasattr(a, "_name_parser_map"))
        goose = sandbox_subparsers._name_parser_map["goose"]
        options = {opt for action in goose._actions for opt in action.option_strings}
        assert "--language" in options
        assert "--threads" in options
        assert "--port" in options
        assert "--host" in options
        assert "--ctx-size" not in options
        assert "--max-tokens" not in options

    def test_sandbox_parser_has_a_serving_port_for_whisper(self):
        from ramalama.cli import sandbox_parser

        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        with patch("ramalama.sandbox.get_runtime", return_value=self.plugin):
            sandbox_parser(subparsers)

        args = parser.parse_args(["sandbox", "goose"])

        assert args.port
        assert args.host

    def test_sandbox_without_a_model_reports_router_mode_is_unsupported(self):
        """The sandbox handler computes a serving port before it knows whether
        whisper.cpp can serve, so the port must exist on the namespace."""
        from ramalama.cli import sandbox_parser
        from ramalama.model_server import ModelServerError
        from ramalama.sandbox import Goose, run_sandbox

        parser = ArgumentParserWithDefaults()
        subparsers = parser.add_subparsers(dest="subcommand")
        with patch("ramalama.sandbox.get_runtime", return_value=self.plugin):
            sandbox_parser(subparsers)
        args = parser.parse_args(["sandbox", "goose"])
        args.container = True

        with (
            patch("ramalama.sandbox.get_runtime", return_value=self.plugin),
            patch("ramalama.sandbox.compute_serving_port", return_value="8080"),
            patch("ramalama.sandbox.list_server_models", side_effect=ModelServerError("no server")),
        ):
            with pytest.raises(ValueError, match="Router mode"):
                run_sandbox(args, Goose)  # type: ignore[arg-type]


class TestWhisperCppImages:
    def setup_method(self):
        self.plugin = WhisperCppPlugin()

    @pytest.fixture(autouse=True)
    def _x86_64(self, monkeypatch):
        monkeypatch.setattr("ramalama.plugins.runtimes.inference.whisper_cpp.platform.machine", lambda: "x86_64")

    def test_default_image_is_fully_tagged(self):
        assert self.plugin.get_container_image(make_config(), "") == WHISPER_IMAGE

    @pytest.mark.parametrize(
        "gpu_type,expected",
        [
            ("CUDA_VISIBLE_DEVICES", "ghcr.io/ggml-org/whisper.cpp:main-cuda"),
            ("INTEL_VISIBLE_DEVICES", "ghcr.io/ggml-org/whisper.cpp:main-intel"),
            ("MUSA_VISIBLE_DEVICES", "ghcr.io/ggml-org/whisper.cpp:main-musa"),
            ("GGML_VK_VISIBLE_DEVICES", "ghcr.io/ggml-org/whisper.cpp:main-vulkan"),
        ],
    )
    def test_gpu_images(self, gpu_type, expected):
        assert self.plugin.get_container_image(make_config(), gpu_type) == expected

    def test_hip_uses_vulkan_image_with_warning(self):
        with patch("ramalama.plugins.runtimes.inference.whisper_cpp.logger.warning") as warning:
            image = self.plugin.get_container_image(make_config(), "HIP_VISIBLE_DEVICES")

        assert image == "ghcr.io/ggml-org/whisper.cpp:main-vulkan"
        assert warning.called
        assert "ROCm" in warning.call_args.args[0]

    def test_unknown_gpu_falls_back_to_default(self):
        assert self.plugin.get_container_image(make_config(), "ASCEND_VISIBLE_DEVICES") == WHISPER_IMAGE

    def test_config_override_for_detected_gpu(self):
        config = make_config({"WHISPER_CUDA_VISIBLE_DEVICES": "custom/whisper:cuda"})
        assert self.plugin.get_container_image(config, "CUDA_VISIBLE_DEVICES") == "custom/whisper:cuda"

    def test_config_override_for_any_gpu(self):
        config = make_config({"WHISPER": "custom/whisper:any"})
        assert self.plugin.get_container_image(config, "CUDA_VISIBLE_DEVICES") == "custom/whisper:any"

    def test_arm64_host_uses_arm64_image(self, monkeypatch):
        monkeypatch.setattr("ramalama.plugins.runtimes.inference.whisper_cpp.platform.machine", lambda: "aarch64")
        assert self.plugin.get_container_image(make_config(), "") == "ghcr.io/ggml-org/whisper.cpp:main-arm64"

    def test_arm64_vulkan_uses_vulkan_arm64_image(self, monkeypatch):
        monkeypatch.setattr("ramalama.plugins.runtimes.inference.whisper_cpp.platform.machine", lambda: "arm64")
        image = self.plugin.get_container_image(make_config(), "GGML_VK_VISIBLE_DEVICES")
        assert image == "ghcr.io/ggml-org/whisper.cpp:main-vulkan-arm64"

    def test_arm64_hip_uses_vulkan_arm64_image(self, monkeypatch):
        monkeypatch.setattr("ramalama.plugins.runtimes.inference.whisper_cpp.platform.machine", lambda: "arm64")
        image = self.plugin.get_container_image(make_config(), "HIP_VISIBLE_DEVICES")
        assert image == "ghcr.io/ggml-org/whisper.cpp:main-vulkan-arm64"


class TestTranscribeCommand:
    def setup_method(self):
        self.plugin = WhisperCppPlugin()

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_container_command(self, mock_new):
        mock_new.return_value = make_model()

        cmd = self.plugin.handle_subcommand("transcribe", make_transcribe_ns())

        assert isinstance(cmd[0], ContainerEntryPoint)
        assert cmd[0].entrypoint == "whisper-cli"
        assert cmd[cmd.index("-m") + 1] == MODEL_PATH
        assert cmd[cmd.index("-m") + 2] == "-f"
        assert cmd[cmd.index("-f") + 1] == "/mnt/audio/input.wav"
        assert cmd[cmd.index("-otxt") + 1] == "-of"
        assert cmd[cmd.index("-of") + 1] == "-"
        assert "-np" in cmd
        assert cmd[cmd.index("-l") + 1] == "auto"
        mock_new.return_value._get_entry_model_path.assert_called_once_with(True, False, False)

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_nocontainer_command(self, mock_new):
        mock_new.return_value = make_model(entry_path="/models/ggml-base.en.bin")

        cmd = self.plugin.handle_subcommand("transcribe", make_transcribe_ns(container=False))

        assert type(cmd[0]) is str
        assert cmd[0] == "whisper-cli"
        assert cmd[cmd.index("-m") + 1] == "/models/ggml-base.en.bin"
        assert cmd[cmd.index("-f") + 1] == "a.wav"
        mock_new.return_value._get_entry_model_path.assert_called_once_with(False, False, False)

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_whisper_options_and_runtime_args(self, mock_new):
        mock_new.return_value = make_model()

        cmd = self.plugin.handle_subcommand(
            "transcribe",
            make_transcribe_ns(language="fr", threads=4, translate=True, runtime_args=["--no-timestamps"]),
        )

        assert cmd[cmd.index("-l") + 1] == "fr"
        assert cmd[cmd.index("-t") + 1] == "4"
        assert "-tr" in cmd
        assert cmd[-1] == "--no-timestamps"


class TestServeCommand:
    def setup_method(self):
        self.plugin = WhisperCppPlugin()

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_container_command(self, mock_new):
        mock_new.return_value = make_model()

        cmd = self.plugin.handle_subcommand("serve", make_serve_ns(port="8080"))

        assert isinstance(cmd[0], ContainerEntryPoint)
        assert cmd[0].entrypoint == "whisper-server"
        assert cmd[cmd.index("-m") + 1] == MODEL_PATH
        assert cmd[cmd.index("--host") + 1] == "::"
        assert cmd[cmd.index("--port") + 1] == "8080"
        assert cmd[cmd.index("-l") + 1] == "auto"
        mock_new.return_value._get_entry_model_path.assert_called_once_with(True, False, False)

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_nocontainer_command_uses_the_configured_host(self, mock_new):
        mock_new.return_value = make_model(entry_path="/models/ggml-base.en.bin")

        cmd = self.plugin.handle_subcommand("serve", make_serve_ns(container=False, host="0.0.0.0", port="9000"))

        assert cmd[0] == "whisper-server"
        assert cmd[cmd.index("-m") + 1] == "/models/ggml-base.en.bin"
        assert cmd[cmd.index("--host") + 1] == "0.0.0.0"
        assert cmd[cmd.index("--port") + 1] == "9000"
        mock_new.return_value._get_entry_model_path.assert_called_once_with(False, False, False)

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_whisper_options_and_runtime_args(self, mock_new):
        mock_new.return_value = make_model()

        cmd = self.plugin.handle_subcommand(
            "serve", make_serve_ns(language="fr", threads=4, runtime_args=["--beam-size", "2"])
        )

        assert cmd[cmd.index("-l") + 1] == "fr"
        assert cmd[cmd.index("-t") + 1] == "4"
        assert cmd[-2:] == ["--beam-size", "2"]

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_container_serve_entrypoint_reaches_the_engine_command(self, mock_new):
        model = make_model()
        engine = Mock()
        engine.exec_args = ["podman", "run", "--rm"]
        engine.add = lambda newargs: engine.exec_args.extend(newargs)
        engine.add_container_image = lambda image, cmd: engine.exec_args.extend([image, *cmd])
        model.engine = engine
        model.setup_container = Mock()
        model.setup_mounts = Mock()
        mock_new.return_value = model
        args = make_serve_ns(dryrun=True)
        args.image = WHISPER_IMAGE

        cmd = self.plugin.handle_subcommand("serve", args)
        Transport.exec_model_in_container(model, cmd, args)

        assert "--entrypoint=whisper-server" in engine.exec_args
        assert engine.exec_args.index("--entrypoint=whisper-server") < engine.exec_args.index(WHISPER_IMAGE)
        assert engine.exec_args[engine.exec_args.index("--port") + 1] == "8080"
        assert engine.exec_args[engine.exec_args.index("--host") + 1] == "::"

    @patch("ramalama.transports.base.set_accel_env_vars")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_sandbox_style_serve_nonblocking_emits_the_entrypoint(self, mock_new, _accel):
        model = make_model()
        model.get_container_name.return_value = "whisper"
        engine = Mock()
        engine.exec_args = ["podman", "run", "--rm"]
        engine.add = lambda newargs: engine.exec_args.extend(newargs)
        engine.add_container_image = lambda image, cmd: engine.exec_args.extend([image, *cmd])
        model.engine = engine
        model.setup_container = Mock()
        model.setup_mounts = Mock()
        mock_new.return_value = model
        args = make_serve_ns(dryrun=True)
        args.image = WHISPER_IMAGE

        cmd = self.plugin.handle_subcommand("serve", args)
        Transport.serve_nonblocking(model, args, cmd)

        assert "--entrypoint=whisper-server" in engine.exec_args
        assert engine.exec_args.index("--entrypoint=whisper-server") < engine.exec_args.index(WHISPER_IMAGE)
        assert engine.exec_args[engine.exec_args.index(WHISPER_IMAGE) + 1] == "-m"

    def test_serve_nonblocking_drops_a_bare_entrypoint_placeholder(self):
        model = make_model()
        engine = Mock()
        engine.exec_args = ["podman", "run", "--rm"]
        engine.add = lambda newargs: engine.exec_args.extend(newargs)
        engine.add_container_image = lambda image, cmd: engine.exec_args.extend([image, *cmd])
        model.engine = engine
        model.setup_container = Mock()
        model.setup_mounts = Mock()
        model.get_container_name.return_value = "vllm"
        args = make_serve_ns(dryrun=True)
        args.image = WHISPER_IMAGE

        Transport.serve_nonblocking(model, args, [ContainerEntryPoint(), "serve", "model"])

        assert not any(arg.startswith("--entrypoint") for arg in engine.exec_args)
        assert engine.exec_args[engine.exec_args.index(WHISPER_IMAGE) + 1 :] == ["serve", "model"]


def make_health_conn(status: int) -> MagicMock:
    conn = MagicMock()
    conn.getresponse.return_value = Namespace(status=status, reason="reason")
    return conn


class TestServeReadyCheck:
    def setup_method(self):
        self.plugin = WhisperCppPlugin()

    def test_200_is_ready(self):
        conn = make_health_conn(200)

        assert self.plugin.service_ready_check(conn, Namespace(container=True, name="whisper")) is True
        conn.request.assert_called_once_with("GET", "/health")

    @pytest.mark.parametrize("status", [503, 404])
    def test_other_statuses_are_not_ready(self, status):
        conn = make_health_conn(status)

        assert self.plugin.service_ready_check(conn, Namespace(container=False)) is False

    def test_default_timeout_is_unchanged(self):
        assert self.plugin.service_ready_check_timeout == 180


class TestTranscribeHandler:
    def setup_method(self):
        self.plugin = WhisperCppPlugin()

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.set_accel_env_vars")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_container_mount_has_fixed_destination_and_relabel(self, mock_new, _accel):
        mock_new.return_value = make_model()
        args = make_transcribe_ns(dryrun=True, selinux=True)

        self.plugin._transcribe_handler(args)

        expected = f"--mount=type=bind,src={get_container_mount_path('a.wav')},destination=/mnt/audio/input.wav,ro,z"
        assert args.engine_args == [expected]

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.set_accel_env_vars")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_mount_has_no_relabel_for_docker(self, mock_new, _accel):
        mock_new.return_value = make_model()
        args = make_transcribe_ns(dryrun=True, engine="docker", selinux=True)

        self.plugin._transcribe_handler(args)

        assert args.engine_args[0].endswith(",ro")

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.set_accel_env_vars")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_nocontainer_passes_the_host_path(self, mock_new, _accel):
        mock_new.return_value = make_model(entry_path="/models/model.bin")
        args = make_transcribe_ns(container=False, dryrun=True)
        seen: dict[str, Any] = {}
        mock_new.return_value.execute_command.side_effect = lambda cmd, _args: seen.update(cmd=cmd)

        self.plugin._transcribe_handler(args)

        assert seen["cmd"][seen["cmd"].index("-f") + 1] == "a.wav"
        assert args.engine_args == []

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.set_accel_env_vars")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.ensure_image")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.accel_image", return_value=WHISPER_IMAGE)
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.ActiveConfig")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_container_run_resolves_and_pulls_the_image(
        self, mock_new, mock_config, _accel_image, mock_ensure_image, _accel
    ):
        mock_new.return_value = make_model()
        mock_config.return_value.engine = "podman"
        mock_config.return_value.pull = "missing"
        args = make_transcribe_ns(dryrun=False)

        self.plugin._transcribe_handler(args)

        mock_ensure_image.assert_called_once_with("podman", WHISPER_IMAGE, should_pull=True, quiet=True)

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.set_accel_env_vars")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_api_transport_is_rejected(self, mock_new, _accel):
        from ramalama.transports.api import APITransport

        mock_new.return_value = MagicMock(spec=APITransport)
        args = make_transcribe_ns(dryrun=True, container=False)

        with pytest.raises(NotImplementedError, match="hosted API transports"):
            self.plugin._transcribe_handler(args)

    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.set_accel_env_vars")
    @patch("ramalama.plugins.runtimes.inference.whisper_cpp.New")
    def test_dryrun_entrypoint_reaches_the_engine_command(self, mock_new, _accel):
        model = make_model()
        engine = Mock()
        engine.exec_args = ["podman", "run", "--rm"]
        engine.add = lambda newargs: engine.exec_args.extend(newargs)
        engine.add_container_image = lambda image, cmd: engine.exec_args.extend([image, *cmd])
        model.engine = engine
        model.setup_container = Mock()
        model.setup_mounts = Mock()
        model.execute_command.side_effect = lambda cmd, args: Transport.exec_model_in_container(model, cmd, args)
        mock_new.return_value = model
        args = make_transcribe_ns(dryrun=True)

        self.plugin._transcribe_handler(args)

        assert "--entrypoint=whisper-cli" in engine.exec_args
        assert engine.exec_args.index("--entrypoint=whisper-cli") < engine.exec_args.index(WHISPER_IMAGE)
        assert "/mnt/audio/input.wav" in engine.exec_args


class TestTranscribeStdin:
    def setup_method(self):
        self.plugin = WhisperCppPlugin()

    @pytest.fixture
    def spool_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        monkeypatch.setattr("ramalama.plugins.runtimes.inference.whisper_cpp.ensure_tmpdir", lambda *_: None)
        return tmp_path

    @pytest.fixture(autouse=True)
    def _no_accel(self):
        with patch("ramalama.plugins.runtimes.inference.whisper_cpp.set_accel_env_vars"):
            yield

    def _run(self, monkeypatch, audio, execute, container=True):
        monkeypatch.setattr(sys, "stdin", _FakeStdin(b"RIFFfake", tty=False))
        args = make_transcribe_ns(AUDIO=audio, dryrun=True, container=container)
        model = make_model()
        model.execute_command.side_effect = execute
        with patch("ramalama.plugins.runtimes.inference.whisper_cpp.New", return_value=model):
            self.plugin._transcribe_handler(args)
        return args

    def test_omitted_audio_is_spooled_from_stdin(self, monkeypatch, spool_dir):
        seen: dict[str, Any] = {}

        def execute(cmd, args):
            seen["path"] = args.AUDIO
            seen["data"] = open(args.AUDIO, "rb").read()
            seen["cmd"] = cmd
            seen["mode"] = stat.S_IMODE(os.stat(args.AUDIO).st_mode)

        self._run(monkeypatch, None, execute)

        assert seen["data"] == b"RIFFfake"
        assert os.path.dirname(os.path.dirname(seen["path"])) == str(spool_dir)
        assert seen["cmd"][seen["cmd"].index("-f") + 1] == "/mnt/audio/input.wav"
        if sys.platform != "win32":
            assert seen["mode"] == 0o644
        assert not list(spool_dir.glob("ramalama-transcribe-*"))

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
    @pytest.mark.parametrize("container, expected", [(False, 0o600), (True, 0o644)])
    def test_spool_mode_depends_on_container(self, monkeypatch, spool_dir, container, expected):
        seen: dict[str, Any] = {}

        def execute(cmd, args):
            seen["mode"] = stat.S_IMODE(os.stat(args.AUDIO).st_mode)

        self._run(monkeypatch, None, execute, container=container)

        assert seen["mode"] == expected

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
    def test_spool_directory_is_private(self, monkeypatch, spool_dir):
        seen: dict[str, Any] = {}

        def execute(cmd, args):
            seen["mode"] = stat.S_IMODE(os.stat(os.path.dirname(args.AUDIO)).st_mode)

        self._run(monkeypatch, None, execute, container=True)

        assert seen["mode"] == 0o700

    def test_spool_is_removed_when_chmod_fails(self, monkeypatch, spool_dir):
        def broken_chmod(*_):
            raise PermissionError("chmod denied")

        monkeypatch.setattr(os, "chmod", broken_chmod)
        monkeypatch.setattr(sys, "stdin", _FakeStdin(b"RIFFfake", tty=False))
        args = make_transcribe_ns(AUDIO=None, dryrun=True, container=True)

        with patch("ramalama.plugins.runtimes.inference.whisper_cpp.New") as mock_new:
            with pytest.raises(PermissionError):
                self.plugin._transcribe_handler(args)

        mock_new.assert_not_called()
        assert not list(spool_dir.glob("ramalama-transcribe-*"))

    def test_dash_reads_audio_from_stdin(self, monkeypatch, spool_dir):
        seen: dict[str, Any] = {}

        def execute(cmd, args):
            seen["path"] = args.AUDIO

        self._run(monkeypatch, "-", execute)

        assert seen["path"].endswith(".wav")
        assert not list(spool_dir.glob("ramalama-transcribe-*"))

    def test_spool_is_removed_on_error(self, monkeypatch, spool_dir):
        def execute(cmd, args):
            raise RuntimeError("transcription failed")

        with pytest.raises(RuntimeError, match="transcription failed"):
            self._run(monkeypatch, None, execute)

        assert not list(spool_dir.glob("ramalama-transcribe-*"))

    def test_spool_is_removed_on_keyboard_interrupt(self, monkeypatch, spool_dir):
        def execute(cmd, args):
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            self._run(monkeypatch, None, execute)

        assert not list(spool_dir.glob("ramalama-transcribe-*"))

    def test_omitted_audio_on_a_tty_is_a_usage_error(self, monkeypatch, spool_dir):
        monkeypatch.setattr(sys, "stdin", _FakeStdin(b"", tty=True))
        args = make_transcribe_ns(AUDIO=None, dryrun=True)

        with patch("ramalama.plugins.runtimes.inference.whisper_cpp.New") as mock_new:
            with pytest.raises(ValueError, match="audio file"):
                self.plugin._transcribe_handler(args)

        mock_new.assert_not_called()
        assert not list(spool_dir.glob("ramalama-transcribe-*"))

    def test_spool_is_removed_when_the_stdin_copy_is_interrupted(self, monkeypatch, spool_dir):
        class _InterruptedBuffer:
            def read(self, *_):
                raise KeyboardInterrupt

        stdin = _FakeStdin(b"", tty=False)
        stdin.buffer = _InterruptedBuffer()
        monkeypatch.setattr(sys, "stdin", stdin)
        args = make_transcribe_ns(AUDIO=None, dryrun=True)

        with patch("ramalama.plugins.runtimes.inference.whisper_cpp.New") as mock_new:
            with pytest.raises(KeyboardInterrupt):
                self.plugin._transcribe_handler(args)

        mock_new.assert_not_called()
        assert not list(spool_dir.glob("ramalama-transcribe-*"))

    def test_comma_in_audio_path_is_rejected_in_a_container(self, monkeypatch, spool_dir):
        args = make_transcribe_ns(AUDIO="rec,01.wav", dryrun=True)

        with patch("ramalama.plugins.runtimes.inference.whisper_cpp.New", return_value=make_model()):
            with pytest.raises(ValueError, match="comma"):
                self.plugin._transcribe_handler(args)


def test_bin_model_resolves_under_the_container_model_dir(tmp_path):
    from ramalama.transports.url import URL

    model_file = tmp_path / "ggml-base.en.bin"
    model_file.write_bytes(b"not a real model")
    store = tmp_path / "store"
    store.mkdir()
    model = URL(str(model_file), str(store), "file")
    model.pull(Namespace(verify=False))

    assert model._get_entry_model_path(True, False, False) == "/mnt/models/ggml-base.en.bin"
