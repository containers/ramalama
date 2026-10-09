"""Unit tests for llama.cpp multi-model router mode."""

import argparse
import json
import platform
from unittest.mock import MagicMock, patch

import pytest
from test_inference_engine_plugins import make_ns

from ramalama.cli import ParsedGenerateInput, configure_subcommands
from ramalama.path_utils import normalize_host_path_for_container
from ramalama.plugins.runtimes.inference.common import enumerate_store_gguf_models
from ramalama.plugins.runtimes.inference.llama_cpp import ROUTER_NAME, LlamaCppPlugin

# ---------------------------------------------------------------------------
# enumerate_store_gguf_models
# ---------------------------------------------------------------------------


class TestEnumerateStoreGgufModels:
    def test_finds_gguf_models(self, tmp_path):
        from ramalama.model_store.reffile import StoreFileType

        store = MagicMock()
        store.path = str(tmp_path)

        model_dir = tmp_path / "huggingface" / "mymodel"
        (model_dir / "refs").mkdir(parents=True)
        (model_dir / "refs" / "latest.json").touch()
        (model_dir / "blobs").mkdir()
        (model_dir / "blobs" / "sha256-abc123").touch()

        sf = MagicMock()
        sf.hash = "sha256:abc123"
        sf.type = StoreFileType.GGUF_MODEL
        ref = MagicMock()
        ref.model_files = [sf]

        ref_cls = MagicMock()
        ref_cls.from_path = MagicMock(return_value=ref)
        models = enumerate_store_gguf_models(
            store,
            "refs",
            "blobs",
            ref_cls,
        )

        assert len(models) == 1
        assert models[0][0] == str(model_dir / "blobs" / "sha256-abc123")
        assert models[0][1].endswith(".gguf")

    def test_empty_store_returns_empty(self, tmp_path):
        store = MagicMock()
        store.path = str(tmp_path)
        tmp_path.mkdir(exist_ok=True)

        models = enumerate_store_gguf_models(
            store,
            "refs",
            "blobs",
            MagicMock,
        )
        assert models == []


# ---------------------------------------------------------------------------
# Router mode in _cmd_run
# ---------------------------------------------------------------------------


class TestRouterModeCmdRun:
    def setup_method(self):
        self.plugin = LlamaCppPlugin()

    @pytest.fixture(autouse=True)
    def _patch_container_image_is_ggml(self):
        with patch.object(self.plugin, "_container_image_is_ggml", return_value=False):
            yield

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_router_mode_has_models_dir_and_max(self, mock_colorize):
        ns = make_ns(container=True)
        ns.router_mode = True
        ns.models_max = 8
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--models-dir" in cmd
        assert cmd[cmd.index("--models-dir") + 1] == "/mnt/models"
        assert "--models-max" in cmd
        assert cmd[cmd.index("--models-max") + 1] == "8"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_router_mode_skips_single_model_flags(self, mock_colorize):
        ns = make_ns(container=True, ngl=-1)
        ns.router_mode = True
        ns.models_max = 4
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--model" not in cmd
        assert "--alias" not in cmd
        assert "-ngl" not in cmd


# ---------------------------------------------------------------------------
# _serve_router guard rails
# ---------------------------------------------------------------------------


class TestServeRouter:
    def setup_method(self):
        self.plugin = LlamaCppPlugin()

    def test_nocontainer_exits(self):
        args = argparse.Namespace(container=False)
        with pytest.raises(SystemExit):
            self.plugin._serve_router(args)

    @patch("ramalama.plugins.runtimes.inference.llama_cpp.enumerate_store_gguf_models", return_value=[])
    @patch.object(LlamaCppPlugin, "_migrate_store_ref_files")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp.set_accel_env_vars")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp.compute_serving_port", return_value="8080")
    def test_no_models_exits(self, mock_port, mock_accel, mock_migrate, mock_enum):
        args = argparse.Namespace(container=True, store="/fake/store", port="8080", MODEL=[])
        with pytest.raises(SystemExit):
            self.plugin._serve_router(args)


# ---------------------------------------------------------------------------
# --generate in router mode
# ---------------------------------------------------------------------------


class TestRouterModeGenerate:
    def setup_method(self):
        self.plugin = LlamaCppPlugin()

    @staticmethod
    def _make_args(tmp_path, gen_type, name="router"):
        blobs = []
        for model_name in ("first", "second"):
            blob = tmp_path / f"sha256-{model_name}"
            blob.write_bytes(b"GGUF")
            blobs.append((str(blob), f"{model_name}.gguf"))

        args = make_ns(container=True, MODEL=[], generate=ParsedGenerateInput(gen_type, str(tmp_path)))
        args.store = str(tmp_path / "store")
        args.name = name
        args.image = "quay.io/ramalama/ramalama:latest"
        args.env = []
        args.add_to_unit = None
        args.privileged = False
        args.nocapdrop = False
        args.rag = None
        args.models_max = 4
        return args, blobs

    def _generate(self, tmp_path, gen_type, name="router"):
        args, blobs = self._make_args(tmp_path, gen_type, name)
        with (
            patch("ramalama.plugins.runtimes.inference.llama_cpp.compute_serving_port", return_value="8080"),
            patch("ramalama.plugins.runtimes.inference.llama_cpp.set_accel_env_vars"),
            patch.object(LlamaCppPlugin, "_migrate_store_ref_files"),
            patch.object(LlamaCppPlugin, "_container_image_is_ggml", return_value=False),
            patch("ramalama.plugins.runtimes.inference.llama_cpp.enumerate_store_gguf_models", return_value=blobs),
            patch.object(LlamaCppPlugin, "_build_router_engine") as mock_engine,
        ):
            self.plugin._serve_router(args)

        # The whole point of --generate is that the server is never started.
        mock_engine.assert_not_called()
        return blobs

    def test_quadlet_mounts_every_model(self, tmp_path):
        blobs = self._generate(tmp_path, "quadlet")

        content = (tmp_path / "router.container").read_text()
        assert "--models-dir /mnt/models" in content
        for host_path, container_name in blobs:
            assert f"Mount=type=bind,src={host_path},target=/mnt/models/{container_name},ro,Z" in content

    def test_kube_mounts_every_model(self, tmp_path):
        blobs = self._generate(tmp_path, "kube")

        content = (tmp_path / "router.yaml").read_text()
        for i, (host_path, container_name) in enumerate(blobs):
            assert (
                f"mountPath: /mnt/models/{container_name}\n          name: model-{i}\n          readOnly: true"
                in content
            )
            expected_host_path = normalize_host_path_for_container(host_path)
            if platform.system() == "Windows":
                # Kube._gen_path_volume works around containers/podman#16704.
                expected_host_path = '/mnt' + expected_host_path
            assert f"path: {expected_host_path}\n        name: model-{i}" in content

    def test_quadlet_kube_writes_both_files(self, tmp_path):
        self._generate(tmp_path, "quadlet/kube")

        assert (tmp_path / "router.yaml").exists()
        assert "Yaml=router.yaml" in (tmp_path / "router.kube").read_text()

    def test_compose_mounts_every_model(self, tmp_path):
        blobs = self._generate(tmp_path, "compose")

        content = (tmp_path / "docker-compose.yaml").read_text()
        for host_path, container_name in blobs:
            expected_host_path = normalize_host_path_for_container(host_path)
            assert f'- "{expected_host_path}:/mnt/models/{container_name}:ro"' in content

    def test_defaults_name_when_unnamed(self, tmp_path):
        self._generate(tmp_path, "quadlet", name=None)

        assert (tmp_path / f"{ROUTER_NAME}.container").exists()


# ---------------------------------------------------------------------------
# service_ready_check router mode
# ---------------------------------------------------------------------------


class TestServiceReadyCheckRouterMode:
    def setup_method(self):
        self.plugin = LlamaCppPlugin()

    def test_router_mode_ready_with_any_model(self):
        conn = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"models": [{"name": "some-model"}]}).encode()
        conn.getresponse.return_value = mock_response

        result = self.plugin.service_ready_check(conn, argparse.Namespace(MODEL=[]))
        assert result is True

    def test_router_mode_not_ready_with_no_models(self):
        conn = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"models": []}).encode()
        conn.getresponse.return_value = mock_response

        result = self.plugin.service_ready_check(conn, argparse.Namespace(MODEL=[]))
        assert result is False


# ---------------------------------------------------------------------------
# Subcommand arg registration for router mode
# ---------------------------------------------------------------------------


class TestRouterModeSubcommandArgs:
    def test_llama_cpp_serve_has_models_max(self, monkeypatch):
        from ramalama.cli import ArgumentParserWithDefaults
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "llama.cpp")
        parser = ArgumentParserWithDefaults()
        configure_subcommands(parser)
        name_map = next(a for a in parser._actions if hasattr(a, "_name_parser_map"))._name_parser_map
        serve_parser = name_map["serve"]
        opts = {opt for action in serve_parser._actions for opt in action.option_strings}
        assert "--models-max" in opts

    def test_llama_cpp_serve_model_accepts_multiple(self, monkeypatch):
        from ramalama.cli import ArgumentParserWithDefaults
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "llama.cpp")
        parser = ArgumentParserWithDefaults()
        configure_subcommands(parser)
        name_map = next(a for a in parser._actions if hasattr(a, "_name_parser_map"))._name_parser_map
        serve_parser = name_map["serve"]
        model_action = next(a for a in serve_parser._actions if "MODEL" in getattr(a, "dest", ""))
        assert model_action.nargs == "*"
