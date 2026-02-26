"""Unit tests for runtime plugins (llama.cpp, vllm, mlx)."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from ramalama.common import ContainerEntryPoint
from ramalama.plugins.interface import InferenceRuntimePlugin
from ramalama.plugins.runtimes.inference.common import ContainerizedInferenceRuntimePlugin
from ramalama.plugins.runtimes.inference.llama_cpp import LlamaCppPlugin
from ramalama.plugins.runtimes.inference.mlx import MlxPlugin
from ramalama.plugins.runtimes.inference.vllm import VllmPlugin


def make_ns(
    container=True,
    ngl=-1,
    threads=4,
    temp=0.8,
    seed=None,
    ctx_size=0,
    cache_reuse=256,
    max_tokens=0,
    port="8080",
    host="0.0.0.0",
    logfile=None,
    debug=False,
    webui="on",
    thinking=True,
    model_draft=None,
    runtime_args=None,
    gguf=None,
    dryrun=False,
    generate=None,
    MODEL=None,
) -> argparse.Namespace:
    ns = argparse.Namespace(
        container=container,
        ngl=ngl,
        threads=threads,
        temp=temp,
        seed=seed,
        ctx_size=ctx_size,
        cache_reuse=cache_reuse,
        max_tokens=max_tokens,
        port=port,
        host=host,
        logfile=logfile,
        debug=debug,
        webui=webui,
        thinking=thinking,
        model_draft=model_draft,
        runtime_args=runtime_args or [],
        gguf=gguf,
        dryrun=dryrun,
        generate=generate,
    )
    if MODEL is not None:
        ns.MODEL = MODEL
    return ns


def make_rag_gen_ns(
    debug=False,
    format="qdrant",
    ocr=False,
    paths=None,
    urls=None,
    inputdir="/input",
) -> argparse.Namespace:
    return argparse.Namespace(
        debug=debug,
        format=format,
        ocr=ocr,
        PATHS=paths,
        urls=urls,
        inputdir=inputdir,
    )


def make_rag_ns(
    debug=False,
    port="9090",
    model_host="host.containers.internal",
    model_port="8080",
) -> argparse.Namespace:
    return argparse.Namespace(
        debug=debug,
        port=port,
        model_host=model_host,
        model_port=model_port,
    )


def make_transport_model(
    model_path="/mnt/models/model.file",
    alias="mymodel",
    mmproj_path=None,
    chat_template_path=None,
    model_name="mymodel",
    draft_model=None,
):
    model = MagicMock()
    model.model_alias = alias
    model.model_name = model_name
    model._get_entry_model_path.return_value = model_path
    model._get_mmproj_path.return_value = mmproj_path
    model._get_chat_template_path.return_value = chat_template_path
    model.draft_model = draft_model
    return model


class TestLlamaCppPlugin:
    def setup_method(self):
        self.plugin = LlamaCppPlugin()

    def test_name(self):
        assert self.plugin.name == "llama.cpp"

    @patch("ramalama.transports.transport_factory.New")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_basic(self, mock_colorize, mock_new):
        mock_model = make_transport_model()
        mock_new.return_value = mock_model

        ns = make_ns(container=True, MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert cmd[0] == "llama-server"
        assert "--host" in cmd
        assert cmd[cmd.index("--host") + 1] == "0.0.0.0"
        assert "--port" in cmd
        assert cmd[cmd.index("--port") + 1] == "8080"
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "/mnt/models/model.file"
        assert "--no-warmup" in cmd
        assert "--jinja" in cmd
        assert "--alias" in cmd
        assert "-ngl" in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_nocontainer_uses_configured_host(self, mock_colorize):
        ns = make_ns(container=False, host="127.0.0.1")
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--host" in cmd
        assert cmd[cmd.index("--host") + 1] == "127.0.0.1"

    @patch("ramalama.transports.transport_factory.New")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_with_mmproj(self, mock_colorize, mock_new):
        mock_model = make_transport_model(mmproj_path="/mnt/models/mmproj.file")
        mock_new.return_value = mock_model

        ns = make_ns(MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--mmproj" in cmd
        assert "--no-jinja" in cmd
        assert "--jinja" not in cmd
        assert "--chat-template-file" not in cmd

    @patch("ramalama.transports.transport_factory.New")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_with_chat_template(self, mock_colorize, mock_new):
        mock_model = make_transport_model(chat_template_path="/mnt/models/chat_template.file")
        mock_new.return_value = mock_model

        ns = make_ns(MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--chat-template-file" in cmd
        assert "--jinja" in cmd
        assert "--no-jinja" not in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_thinking_disabled(self, mock_colorize):
        ns = make_ns(thinking=False)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--reasoning-budget" in cmd
        assert cmd[cmd.index("--reasoning-budget") + 1] == "0"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_thinking_enabled(self, mock_colorize):
        ns = make_ns(thinking=True)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--reasoning-budget" not in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_ctx_size(self, mock_colorize):
        ns = make_ns(ctx_size=4096)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--ctx-size" in cmd
        assert cmd[cmd.index("--ctx-size") + 1] == "4096"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_ctx_size_zero_not_added(self, mock_colorize):
        ns = make_ns(ctx_size=0)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--ctx-size" not in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_webui_off(self, mock_colorize):
        ns = make_ns(webui="off")
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--no-webui" in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_webui_on_not_added(self, mock_colorize):
        ns = make_ns(webui="on")
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--no-webui" not in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_ngl_positive(self, mock_colorize):
        ns = make_ns(ngl=40)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "-ngl" in cmd
        assert cmd[cmd.index("-ngl") + 1] == "40"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_ngl_negative_uses_999(self, mock_colorize):
        ns = make_ns(ngl=-1)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "-ngl" in cmd
        assert cmd[cmd.index("-ngl") + 1] == "999"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_max_tokens(self, mock_colorize):
        ns = make_ns(max_tokens=512)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "-n" in cmd
        assert cmd[cmd.index("-n") + 1] == "512"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_max_tokens_zero_not_added(self, mock_colorize):
        ns = make_ns(max_tokens=0)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "-n" not in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=True)
    def test_serve_log_colors(self, mock_colorize):
        ns = make_ns()
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--log-colors" in cmd
        assert cmd[cmd.index("--log-colors") + 1] == "on"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.os.getenv", return_value="192.168.1.1:50052")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_rpc_nodes(self, mock_colorize, mock_getenv):
        ns = make_ns()
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--rpc" in cmd
        assert cmd[cmd.index("--rpc") + 1] == "192.168.1.1:50052"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_runtime_args(self, mock_colorize):
        ns = make_ns(runtime_args=["--extra", "flag"])
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--extra" in cmd
        assert "flag" in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_seed(self, mock_colorize):
        ns = make_ns(seed=42)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--seed" in cmd
        assert cmd[cmd.index("--seed") + 1] == "42"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_debug(self, mock_colorize):
        ns = make_ns(debug=True)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "-v" in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_run_same_as_serve(self, mock_colorize):
        ns = make_ns()
        assert self.plugin.handle_subcommand("serve", ns) == self.plugin.handle_subcommand("run", ns)

    @patch("ramalama.transports.transport_factory.New")
    def test_perplexity(self, mock_new):
        mock_model = make_transport_model()
        mock_new.return_value = mock_model

        ns = make_ns(ngl=20, threads=8, MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("perplexity", ns)

        assert cmd[0] == "llama-perplexity"
        assert "--model" in cmd
        assert "-ngl" in cmd
        assert cmd[cmd.index("-ngl") + 1] == "20"
        assert "--threads" in cmd
        assert cmd[cmd.index("--threads") + 1] == "8"

    @patch("ramalama.transports.transport_factory.New")
    def test_bench(self, mock_new):
        mock_model = make_transport_model()
        mock_new.return_value = mock_model

        ns = make_ns(ngl=30, MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("bench", ns)

        assert cmd[0] == "llama-bench"
        assert "--model" in cmd
        assert "-ngl" in cmd
        assert "-o" in cmd
        assert cmd[cmd.index("-o") + 1] == "json"

    def test_rag_generate(self):
        ns = make_rag_gen_ns(format="qdrant", paths=["/some/path"], inputdir="/input")
        cmd = self.plugin.handle_subcommand("rag", ns)

        assert cmd[0] == "doc2rag"
        assert "--format" in cmd
        assert cmd[cmd.index("--format") + 1] == "qdrant"
        assert "/output" in cmd
        assert "/input" in cmd

    def test_rag_generate_with_debug(self):
        ns = make_rag_gen_ns(debug=True)
        cmd = self.plugin.handle_subcommand("rag", ns)

        assert "--debug" in cmd

    def test_rag_generate_with_ocr(self):
        ns = make_rag_gen_ns(ocr=True)
        cmd = self.plugin.handle_subcommand("rag", ns)

        assert "--ocr" in cmd

    def test_rag_generate_with_urls(self):
        ns = make_rag_gen_ns(urls=["http://example.com", "http://other.com"])
        cmd = self.plugin.handle_subcommand("rag", ns)

        assert "http://example.com" in cmd
        assert "http://other.com" in cmd

    def test_run_rag(self):
        # RAG routing is internal: _cmd_run dispatches to _cmd_run_rag when args.rag is set
        ns = make_rag_ns(port="9090", model_host="host.containers.internal", model_port="8080")
        ns.rag = "some/path"
        cmd = self.plugin.handle_subcommand("run", ns)

        assert cmd[0] == "rag_framework"
        assert "serve" in cmd
        assert "--port" in cmd
        assert cmd[cmd.index("--port") + 1] == "9090"
        assert "--model-host" in cmd
        assert cmd[cmd.index("--model-host") + 1] == "host.containers.internal"
        assert "--model-port" in cmd
        assert "/rag/vector.db" in cmd

    def test_serve_rag_same_as_run_rag(self):
        # _cmd_serve = _cmd_run, so both dispatch to _cmd_run_rag when args.rag is set
        ns = make_rag_ns()
        ns.rag = "some/path"
        assert self.plugin.handle_subcommand("run", ns) == self.plugin.handle_subcommand("serve", ns)

    @patch("ramalama.transports.transport_factory.New")
    def test_convert(self, mock_new):
        mock_model = make_transport_model(model_name="mymodel")
        mock_new.return_value = mock_model

        ns = make_ns(MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("convert", ns)

        assert cmd[0] == "convert_hf_to_gguf.py"
        assert "--outfile" in cmd
        assert "/output/mymodel.gguf" in cmd
        assert "/model" in cmd

    @patch("ramalama.transports.transport_factory.New")
    def test_quantize(self, mock_new):
        mock_model = make_transport_model(model_name="mymodel")
        mock_new.return_value = mock_model

        ns = make_ns(gguf="Q4_K_M", MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("quantize", ns)

        assert cmd[0] == "llama-quantize"
        assert "/model/mymodel.gguf" in cmd
        assert "/model/mymodel-Q4_K_M.gguf" in cmd
        assert "Q4_K_M" in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_unsupported_command_raises(self, mock_colorize):
        ns = make_ns()
        with pytest.raises(NotImplementedError):
            self.plugin.handle_subcommand("unknown_cmd", ns)

    def test_get_container_image_cuda(self):
        config = MagicMock()
        config.images.get.return_value = None
        image = self.plugin.get_container_image(config, "CUDA_VISIBLE_DEVICES")
        assert image == "quay.io/ramalama/cuda:latest"

    def test_get_container_image_no_gpu(self):
        config = MagicMock()
        config.images.get.return_value = None
        config.default_image = "quay.io/ramalama/ramalama"
        image = self.plugin.get_container_image(config, "")
        assert image == "quay.io/ramalama/ramalama:latest"

    def test_get_container_image_user_override(self):
        config = MagicMock()
        config.images.get.side_effect = lambda key, default=None: {
            "CUDA_VISIBLE_DEVICES": "custom/cuda:v1.0",
        }.get(key, default)
        image = self.plugin.get_container_image(config, "CUDA_VISIBLE_DEVICES")
        assert image == "custom/cuda:v1.0"


class TestVllmPlugin:
    def setup_method(self):
        self.plugin = VllmPlugin()

    def test_name(self):
        assert self.plugin.name == "vllm"

    @patch("ramalama.transports.transport_factory.New")
    def test_serve_in_container(self, mock_new):
        mock_model = make_transport_model()
        mock_new.return_value = mock_model

        ns = make_ns(container=True, MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert isinstance(cmd[0], ContainerEntryPoint)
        assert "--model" in cmd
        assert "--served-model-name" in cmd
        assert "--port" in cmd

    def test_serve_nocontainer(self):
        ns = make_ns(container=False)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert cmd[0] == "python3"
        assert cmd[1] == "-m"
        assert cmd[2] == "vllm.entrypoints.openai.api_server"

    def test_serve_no_max_model_len_when_unset(self):
        ns = make_ns(ctx_size=0)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--max-model-len" not in cmd

    def test_serve_custom_ctx_size(self):
        ns = make_ns(ctx_size=8192)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--max-model-len" in cmd
        assert cmd[cmd.index("--max-model-len") + 1] == "8192"

    def test_serve_temperature(self):
        ns = make_ns(temp=0.5)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--temperature" in cmd
        assert cmd[cmd.index("--temperature") + 1] == "0.5"

    def test_serve_seed(self):
        ns = make_ns(seed=123)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--seed" in cmd
        assert cmd[cmd.index("--seed") + 1] == "123"

    def test_serve_seed_not_added_when_none(self):
        ns = make_ns(seed=None)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--seed" not in cmd

    def test_serve_runtime_args(self):
        ns = make_ns(runtime_args=["--tensor-parallel-size", "2"])
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--tensor-parallel-size" in cmd
        assert "2" in cmd

    def test_run_same_as_serve(self):
        ns = make_ns()
        assert self.plugin.handle_subcommand("serve", ns) == self.plugin.handle_subcommand("run", ns)

    def test_get_container_image_with_gpu(self):
        config = MagicMock()
        config.images.get.side_effect = lambda key, default=None: {
            "VLLM_CUDA_VISIBLE_DEVICES": "docker.io/vllm/vllm-openai:cuda",
        }.get(key, default)

        image = self.plugin.get_container_image(config, "CUDA_VISIBLE_DEVICES")
        assert image == "docker.io/vllm/vllm-openai:cuda"

    def test_get_container_image_fallback(self):
        config = MagicMock()
        config.images.get.side_effect = lambda key, default=None: default

        image = self.plugin.get_container_image(config, "CUDA_VISIBLE_DEVICES")
        assert image == "docker.io/vllm/vllm-openai:latest"

    def test_get_container_image_no_gpu(self):
        config = MagicMock()
        config.images.get.side_effect = lambda key, default=None: default

        image = self.plugin.get_container_image(config, "")
        assert image == "docker.io/vllm/vllm-openai:latest"

    def test_get_container_image_with_tag_not_modified(self):
        config = MagicMock()
        config.images.get.side_effect = lambda key, default=None: "docker.io/vllm/vllm-openai:v0.5.0"

        image = self.plugin.get_container_image(config, "")
        assert image == "docker.io/vllm/vllm-openai:v0.5.0"

    def test_unsupported_command_raises(self):
        ns = make_ns()
        with pytest.raises(NotImplementedError):
            self.plugin.handle_subcommand("bench", ns)

    def test_rag_command_unsupported(self):
        ns = make_rag_gen_ns()
        with pytest.raises(NotImplementedError):
            self.plugin.handle_subcommand("rag", ns)


class TestMlxPlugin:
    def setup_method(self):
        self.plugin = MlxPlugin()

    def test_name(self):
        assert self.plugin.name == "mlx"

    @patch("ramalama.transports.transport_factory.New")
    def test_serve_basic(self, mock_new):
        mock_model = make_transport_model()
        mock_new.return_value = mock_model

        ns = make_ns(temp=0.7, port="8080", host="0.0.0.0", MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert cmd[0] == "mlx_lm.server"
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "/mnt/models/model.file"
        assert "--temp" in cmd
        assert "--port" in cmd

    def test_serve_with_max_tokens(self):
        ns = make_ns(max_tokens=2048)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--max-tokens" in cmd
        assert cmd[cmd.index("--max-tokens") + 1] == "2048"

    def test_serve_max_tokens_zero_not_added(self):
        ns = make_ns(max_tokens=0)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--max-tokens" not in cmd

    def test_serve_seed(self):
        ns = make_ns(seed=99)
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--seed" in cmd
        assert cmd[cmd.index("--seed") + 1] == "99"

    def test_serve_runtime_args(self):
        ns = make_ns(runtime_args=["--verbose"])
        cmd = self.plugin.handle_subcommand("serve", ns)

        assert "--verbose" in cmd

    def test_run_same_as_serve(self):
        ns = make_ns()
        assert self.plugin.handle_subcommand("serve", ns) == self.plugin.handle_subcommand("run", ns)

    @patch('ramalama.plugins.runtimes.inference.mlx.platform.system', return_value='Darwin')
    @patch('ramalama.plugins.runtimes.inference.mlx.platform.machine', return_value='arm64')
    def test_post_process_args_forces_nocontainer(self, _machine, _system):
        args = argparse.Namespace(container=True)
        self.plugin.post_process_args(args)
        assert args.container is False

    @patch('ramalama.plugins.runtimes.inference.mlx.platform.system', return_value='Darwin')
    @patch('ramalama.plugins.runtimes.inference.mlx.platform.machine', return_value='arm64')
    def test_post_process_args_keeps_nocontainer(self, _machine, _system):
        args = argparse.Namespace(container=False)
        self.plugin.post_process_args(args)
        assert args.container is False

    def test_no_container_image_override(self):
        config = MagicMock()
        assert self.plugin.get_container_image(config, "cuda") is None

    def test_unsupported_command_raises(self):
        ns = make_ns()
        with pytest.raises(NotImplementedError):
            self.plugin.handle_subcommand("bench", ns)

    def test_is_inference_runtime_plugin_not_containerized(self):
        assert isinstance(self.plugin, InferenceRuntimePlugin)
        assert not isinstance(self.plugin, ContainerizedInferenceRuntimePlugin)


class TestPluginClassHierarchy:
    """Verify the class hierarchy for all runtime plugins."""

    def test_llama_cpp_is_containerized(self):
        assert isinstance(LlamaCppPlugin(), ContainerizedInferenceRuntimePlugin)

    def test_vllm_is_containerized(self):
        assert isinstance(VllmPlugin(), InferenceRuntimePlugin)
        assert isinstance(VllmPlugin(), ContainerizedInferenceRuntimePlugin)

    def test_mlx_is_not_containerized(self):
        assert isinstance(MlxPlugin(), InferenceRuntimePlugin)
        assert not isinstance(MlxPlugin(), ContainerizedInferenceRuntimePlugin)


class TestConfigureSubcommandsFiltering:
    """Verify configure_subcommands() only registers subcommands for the selected runtime."""

    def _make_parser(self):
        from ramalama.cli import ArgumentParserWithDefaults

        return ArgumentParserWithDefaults()

    def _name_map(self, parser):
        return next(a for a in parser._actions if hasattr(a, "_name_parser_map"))._name_parser_map

    def test_mlx_runtime_excludes_rag(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" not in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_llama_cpp_runtime_includes_rag_with_container(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "llama.cpp")
        monkeypatch.setattr(get_config(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_llama_cpp_runtime_excludes_rag_nocontainer(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "llama.cpp")
        monkeypatch.setattr(get_config(), "container", False)
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" not in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_vllm_runtime_excludes_rag_with_container(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "vllm")
        monkeypatch.setattr(get_config(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" not in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_vllm_runtime_excludes_rag_nocontainer(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "vllm")
        monkeypatch.setattr(get_config(), "container", False)
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" not in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_unknown_runtime_raises(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "no-such-runtime")
        parser = self._make_parser()
        with pytest.raises(ValueError, match="Unknown runtime: 'no-such-runtime'"):
            configure_subcommands(parser)

    def _subparser_option_strings(self, parser, subcommand):
        name_map = self._name_map(parser)
        subparser = name_map[subcommand]
        return {opt for action in subparser._actions for opt in action.option_strings}

    def test_llama_cpp_run_has_ngl(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "llama.cpp")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--ngl" in opts

    def test_mlx_run_no_ngl(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--ngl" not in opts

    def test_mlx_run_has_max_tokens(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--max-tokens" in opts

    def test_vllm_serve_has_max_model_len(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "vllm")
        monkeypatch.setattr(get_config(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--max-model-len" in opts

    def test_mlx_serve_no_max_model_len(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--max-model-len" not in opts

    def test_llama_cpp_serve_has_webui(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "llama.cpp")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--webui" in opts

    def test_mlx_serve_no_webui(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--webui" not in opts

    def test_mlx_run_has_ctx_size(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--ctx-size" in opts

    def test_mlx_run_has_keepalive(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--keepalive" in opts

    def test_all_runtimes_serve_has_temp(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        for runtime in ("llama.cpp", "mlx", "vllm"):
            monkeypatch.setattr(get_config(), "runtime", runtime)
            monkeypatch.setattr(get_config(), "container", True)
            parser = self._make_parser()
            configure_subcommands(parser)
            opts = self._subparser_option_strings(parser, "serve")
            assert "--temp" in opts, f"--temp missing for runtime {runtime}"

    def test_vllm_serve_has_api(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "vllm")
        monkeypatch.setattr(get_config(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--api" in opts

    def test_mlx_serve_no_api(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--api" not in opts

    def test_vllm_serve_has_generate(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "vllm")
        monkeypatch.setattr(get_config(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--generate" in opts

    def test_mlx_serve_no_generate(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import get_config

        monkeypatch.setattr(get_config(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--generate" not in opts
