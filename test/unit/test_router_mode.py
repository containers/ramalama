"""Unit tests for llama.cpp multi-model router mode."""

import argparse
import json
from unittest.mock import MagicMock, patch

import pytest
from test_inference_engine_plugins import make_ns

from ramalama.cli import configure_subcommands
from ramalama.plugins.runtimes.inference.common import enumerate_store_gguf_models
from ramalama.plugins.runtimes.inference.llama_cpp import LlamaCppPlugin

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
