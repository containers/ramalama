"""Unit tests for runtime plugins (llama.cpp, vllm, mlx)."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from ramalama.cli import (
    configure_subcommands,
    create_argument_parser,
    default_image,
    default_rag_image,
)
from ramalama.common import ContainerEntryPoint, accel_image, version_tagged_image
from ramalama.compat import NamedTemporaryFile
from ramalama.config import DEFAULT_IMAGE, load_config
from ramalama.plugins.interface import InferenceRuntimePlugin
from ramalama.plugins.runtimes.inference.common import ContainerizedInferenceRuntimePlugin
from ramalama.plugins.runtimes.inference.llama_cpp import LlamaCppPlugin, get_available_backends
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

    @pytest.fixture(params=[False, True])
    def container_image_is_ggml(self, request):
        return request.param

    @pytest.fixture(autouse=True)
    def _patch_container_image_is_ggml(self, container_image_is_ggml):
        with patch.object(self.plugin, "_container_image_is_ggml", return_value=container_image_is_ggml):
            yield

    def test_name(self):
        assert self.plugin.name == "llama.cpp"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.New")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_serve_basic(self, mock_colorize, mock_new, container_image_is_ggml):
        mock_model = make_transport_model()
        mock_new.return_value = mock_model

        ns = make_ns(container=True, MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("serve", ns)

        expected_entry = "--server" if container_image_is_ggml else "llama-server"
        assert cmd[0] == expected_entry
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

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.New")
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

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.New")
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

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.New")
    def test_perplexity(self, mock_new, container_image_is_ggml):
        mock_model = make_transport_model()
        mock_new.return_value = mock_model

        ns = make_ns(ngl=20, threads=8, MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("perplexity", ns)

        expected_entry = "--perplexity" if container_image_is_ggml else "llama-perplexity"
        assert cmd[0] == expected_entry
        assert "--model" in cmd
        assert "-ngl" in cmd
        assert cmd[cmd.index("-ngl") + 1] == "20"
        assert "--threads" in cmd
        assert cmd[cmd.index("--threads") + 1] == "8"

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.New")
    def test_bench(self, mock_new, container_image_is_ggml):
        mock_model = make_transport_model()
        mock_new.return_value = mock_model

        ns = make_ns(ngl=30, MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("bench", ns)

        expected_entry = "--bench" if container_image_is_ggml else "llama-bench"
        assert cmd[0] == expected_entry
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

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.New")
    def test_convert(self, mock_new, container_image_is_ggml):
        mock_model = make_transport_model(model_name="mymodel")
        mock_new.return_value = mock_model

        ns = make_ns(MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("convert", ns)

        expected_entry = "--convert" if container_image_is_ggml else "convert_hf_to_gguf.py"
        assert cmd[0] == expected_entry
        assert "--outfile" in cmd
        assert "/output/mymodel.gguf" in cmd
        assert "/model" in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.New")
    def test_quantize(self, mock_new, container_image_is_ggml):
        mock_model = make_transport_model(model_name="mymodel")
        mock_new.return_value = mock_model

        ns = make_ns(gguf="Q4_K_M", MODEL="ollama://mymodel")
        cmd = self.plugin.handle_subcommand("quantize", ns)

        expected_entry = "--quantize" if container_image_is_ggml else "llama-quantize"
        assert cmd[0] == expected_entry
        assert "/model/mymodel.gguf" in cmd
        assert "/model/mymodel-Q4_K_M.gguf" in cmd
        assert "Q4_K_M" in cmd

    @patch("ramalama.plugins.runtimes.inference.llama_cpp_commands.should_colorize", return_value=False)
    def test_unsupported_command_raises(self, mock_colorize):
        ns = make_ns()
        with pytest.raises(NotImplementedError):
            self.plugin.handle_subcommand("unknown_cmd", ns)

    @patch("ramalama.plugins.runtimes.inference.llama_cpp.ensure_image")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp.Engine")
    def test_quantize_calls_ensure_image_when_not_dryrun(self, mock_engine_cls, mock_ensure_image):
        default_image = version_tagged_image("quay.io/ramalama/ramalama")
        mock_ensure_image.return_value = default_image
        mock_engine_cls.return_value = MagicMock()
        mock_source = MagicMock()
        mock_source.model_name = "mymodel"

        args = argparse.Namespace(
            dryrun=False,
            image=default_image,
            engine="podman",
            gguf="Q4_K_M",
            container=True,
            pull="missing",
        )
        with patch("ramalama.plugins.runtimes.inference.llama_cpp.ActiveConfig") as mock_cfg:
            mock_cfg.return_value.pull = "missing"
            self.plugin._quantize(mock_source, args, "/model_dir")

        mock_ensure_image.assert_called_once_with("podman", default_image, should_pull=True)

    @patch("ramalama.plugins.runtimes.inference.llama_cpp.ensure_image")
    @patch("ramalama.plugins.runtimes.inference.llama_cpp.Engine")
    def test_quantize_skips_ensure_image_on_dryrun(self, mock_engine_cls, mock_ensure_image):
        mock_engine_cls.return_value = MagicMock()
        mock_source = MagicMock()
        mock_source.model_name = "mymodel"

        args = argparse.Namespace(
            dryrun=True,
            image=version_tagged_image("quay.io/ramalama/ramalama"),
            engine="podman",
            gguf="Q4_K_M",
            container=True,
            pull="missing",
        )
        self.plugin._quantize(mock_source, args, "/model_dir")

        mock_ensure_image.assert_not_called()

    def test_get_container_image_cuda(self):
        config = MagicMock()
        config.backend = "auto"
        config.images.get.return_value = None
        image = self.plugin.get_container_image(config, "CUDA_VISIBLE_DEVICES")
        assert image == version_tagged_image("quay.io/ramalama/cuda")

    def test_get_container_image_no_gpu(self):
        config = MagicMock()
        config.backend = "auto"
        config.images.get.return_value = None
        config.default_image = version_tagged_image("quay.io/ramalama/ramalama")
        image = self.plugin.get_container_image(config, "")
        assert image == version_tagged_image("quay.io/ramalama/ramalama")

    def test_get_container_image_user_override(self):
        config = MagicMock()
        config.backend = "auto"
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

    @patch("ramalama.plugins.runtimes.inference.vllm.New")
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

        # RamalamaImages provides a default for CUDA without :latest tag
        image = self.plugin.get_container_image(config, "CUDA_VISIBLE_DEVICES")
        assert image == "docker.io/vllm/vllm-openai"

    def test_get_container_image_no_gpu(self):
        from unittest.mock import patch

        config = MagicMock()
        config.images.get.side_effect = lambda key, default=None: default

        with patch.dict("os.environ", {}, clear=True):
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

    @patch("ramalama.plugins.runtimes.inference.mlx.New")
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
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" not in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_llama_cpp_runtime_includes_rag_with_container(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "llama.cpp")
        monkeypatch.setattr(ActiveConfig(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_llama_cpp_runtime_excludes_rag_nocontainer(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "llama.cpp")
        monkeypatch.setattr(ActiveConfig(), "container", False)
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" not in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_vllm_runtime_excludes_rag_with_container(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "vllm")
        monkeypatch.setattr(ActiveConfig(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" not in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_vllm_runtime_excludes_rag_nocontainer(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "vllm")
        monkeypatch.setattr(ActiveConfig(), "container", False)
        parser = self._make_parser()
        configure_subcommands(parser)
        name_map = self._name_map(parser)
        assert "rag" not in name_map
        assert "run" in name_map
        assert "serve" in name_map

    def test_unknown_runtime_raises(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "no-such-runtime")
        parser = self._make_parser()
        with pytest.raises(ValueError, match="Unknown runtime: 'no-such-runtime'"):
            configure_subcommands(parser)

    def _subparser_option_strings(self, parser, subcommand):
        name_map = self._name_map(parser)
        subparser = name_map[subcommand]
        return {opt for action in subparser._actions for opt in action.option_strings}

    def test_llama_cpp_run_has_ngl(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "llama.cpp")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--ngl" in opts

    def test_mlx_run_no_ngl(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--ngl" not in opts

    def test_mlx_run_has_max_tokens(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--max-tokens" in opts

    def test_vllm_serve_has_max_model_len(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "vllm")
        monkeypatch.setattr(ActiveConfig(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--max-model-len" in opts

    def test_mlx_serve_no_max_model_len(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--max-model-len" not in opts

    def test_llama_cpp_serve_has_webui(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "llama.cpp")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--webui" in opts

    def test_mlx_serve_no_webui(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--webui" not in opts

    def test_mlx_run_has_ctx_size(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--ctx-size" in opts

    def test_mlx_run_has_keepalive(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "run")
        assert "--keepalive" in opts

    def test_all_runtimes_serve_has_temp(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        for runtime in ("llama.cpp", "mlx", "vllm"):
            monkeypatch.setattr(ActiveConfig(), "runtime", runtime)
            monkeypatch.setattr(ActiveConfig(), "container", True)
            parser = self._make_parser()
            configure_subcommands(parser)
            opts = self._subparser_option_strings(parser, "serve")
            assert "--temp" in opts, f"--temp missing for runtime {runtime}"

    def test_vllm_serve_has_api(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "vllm")
        monkeypatch.setattr(ActiveConfig(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--api" in opts

    def test_mlx_serve_no_api(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--api" not in opts

    def test_vllm_serve_has_generate(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "vllm")
        monkeypatch.setattr(ActiveConfig(), "container", True)
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--generate" in opts

    def test_mlx_serve_no_generate(self, monkeypatch):
        from ramalama.cli import configure_subcommands
        from ramalama.config import ActiveConfig

        monkeypatch.setattr(ActiveConfig(), "runtime", "mlx")
        parser = self._make_parser()
        configure_subcommands(parser)
        opts = self._subparser_option_strings(parser, "serve")
        assert "--generate" not in opts


# ---------------------------------------------------------------------------
# llama.cpp backend selection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "backend,gpu_env,expected_result",
    [
        # Auto mode: Vulkan for AMD and Intel, CUDA for NVIDIA
        ("auto", "HIP_VISIBLE_DEVICES", DEFAULT_IMAGE),  # AMD -> Vulkan -> ramalama image
        ("auto", "CUDA_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/cuda")),
        ("auto", "INTEL_VISIBLE_DEVICES", DEFAULT_IMAGE),  # Intel -> Vulkan -> ramalama image
        # Explicit Vulkan: works for AMD and Intel
        ("vulkan", "HIP_VISIBLE_DEVICES", DEFAULT_IMAGE),
        ("vulkan", "INTEL_VISIBLE_DEVICES", DEFAULT_IMAGE),
        # Explicit vendor backends
        ("rocm", "HIP_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/rocm")),
        ("cuda", "CUDA_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/cuda")),
        ("sycl", "INTEL_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/intel-gpu")),
        ("openvino", "INTEL_VISIBLE_DEVICES", "ghcr.io/ggml-org/llama.cpp:full-openvino"),
        # Force backend even with different GPU (warns but allows)
        ("rocm", "CUDA_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/rocm")),
        ("cuda", "HIP_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/cuda")),
        ("vulkan", "CUDA_VISIBLE_DEVICES", DEFAULT_IMAGE),  # Vulkan on NVIDIA (not in preferences, warns)
    ],
)
def test_backend_selection(backend: str, gpu_env: str, expected_result: str, monkeypatch):
    """Test that GPUs use the correct image based on backend config."""
    monkeypatch.setattr("ramalama.common.get_accel", lambda: "none")

    with NamedTemporaryFile('w', delete_on_close=False) as f:
        f.write(f"""\
[ramalama]
backend = "{backend}"
            """)
        f.flush()

        env = {
            "RAMALAMA_CONFIG": f.name,
            gpu_env: "1",
        }

        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            with patch("ramalama.cli.ActiveConfig", return_value=config):
                default_image.cache_clear()
                default_rag_image.cache_clear()
                parser = create_argument_parser("test_backend")
                configure_subcommands(parser)
                assert accel_image(config) == expected_result


@pytest.mark.parametrize(
    "backend,gpu_env,expected_result",
    [
        # Auto mode on Windows: ROCm for AMD, CUDA for NVIDIA, sycl for Intel
        ("auto", "HIP_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/rocm")),  # AMD -> ROCm on Windows
        ("auto", "CUDA_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/cuda")),  # NVIDIA -> CUDA
        ("auto", "INTEL_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/intel-gpu")),  # Intel -> sycl
        # Explicit backends still work
        ("vulkan", "HIP_VISIBLE_DEVICES", DEFAULT_IMAGE),
        ("rocm", "HIP_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/rocm")),
        ("vulkan", "INTEL_VISIBLE_DEVICES", DEFAULT_IMAGE),
        ("sycl", "INTEL_VISIBLE_DEVICES", version_tagged_image("quay.io/ramalama/intel-gpu")),
        ("openvino", "INTEL_VISIBLE_DEVICES", "ghcr.io/ggml-org/llama.cpp:full-openvino"),
    ],
)
def test_backend_selection_windows(backend: str, gpu_env: str, expected_result: str, monkeypatch):
    """Test that Windows defaults to vendor-specific backends for AMD and Intel."""
    monkeypatch.setattr("ramalama.common.get_accel", lambda: "none")
    monkeypatch.setattr("ramalama.plugins.runtimes.inference.llama_cpp.platform.system", lambda: "Windows")

    with NamedTemporaryFile('w', delete_on_close=False) as f:
        f.write(f"""\
[ramalama]
backend = "{backend}"
            """)
        f.flush()

        env = {
            "RAMALAMA_CONFIG": f.name,
            gpu_env: "1",
        }

        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            with patch("ramalama.cli.ActiveConfig", return_value=config):
                default_image.cache_clear()
                default_rag_image.cache_clear()
                parser = create_argument_parser("test_backend_windows")
                configure_subcommands(parser)
                assert accel_image(config) == expected_result


@pytest.mark.parametrize(
    "gpu_env,backend,expected_image",
    [
        # AMD GPU: vLLM should use ROCm image regardless of backend
        ("HIP_VISIBLE_DEVICES", "auto", "docker.io/vllm/vllm-openai-rocm:latest"),
        ("HIP_VISIBLE_DEVICES", "vulkan", "docker.io/vllm/vllm-openai-rocm:latest"),
        ("HIP_VISIBLE_DEVICES", "rocm", "docker.io/vllm/vllm-openai-rocm:latest"),
        # NVIDIA GPU: vLLM uses standard CUDA image
        ("CUDA_VISIBLE_DEVICES", "auto", "docker.io/vllm/vllm-openai:latest"),
        ("CUDA_VISIBLE_DEVICES", "cuda", "docker.io/vllm/vllm-openai:latest"),
        # Intel GPU: vLLM uses Intel-specific image regardless of backend
        ("INTEL_VISIBLE_DEVICES", "auto", "docker.io/intel/vllm:latest"),
        ("INTEL_VISIBLE_DEVICES", "vulkan", "docker.io/intel/vllm:latest"),
        ("INTEL_VISIBLE_DEVICES", "sycl", "docker.io/intel/vllm:latest"),
    ],
)
def test_vllm_backend_image_selection(gpu_env: str, backend: str, expected_image: str, monkeypatch):
    """Test that vLLM uses correct images based on detected GPU, not backend selection."""
    monkeypatch.setattr("ramalama.common.get_accel", lambda: "none")

    with NamedTemporaryFile('w', delete_on_close=False) as f:
        f.write(f"""\
[ramalama]
backend = "{backend}"
runtime = "vllm"
            """)
        f.flush()

        env = {
            "RAMALAMA_CONFIG": f.name,
            gpu_env: "1",
        }

        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            with patch("ramalama.cli.ActiveConfig", return_value=config):
                default_image.cache_clear()
                default_rag_image.cache_clear()
                parser = create_argument_parser("test_vllm")
                configure_subcommands(parser)
                assert accel_image(config) == expected_image


def test_backend_incompatibility_warning(monkeypatch):
    """Test that warnings are issued for incompatible backend selections."""
    monkeypatch.setattr("ramalama.common.get_accel", lambda: "none")

    with NamedTemporaryFile('w', delete_on_close=False) as f:
        f.write("""\
[ramalama]
backend = "cuda"
            """)
        f.flush()

        env = {
            "RAMALAMA_CONFIG": f.name,
            "HIP_VISIBLE_DEVICES": "1",  # AMD GPU detected, but CUDA backend requested
        }

        with patch.dict("os.environ", env, clear=True):
            config = load_config()
            with patch("ramalama.cli.ActiveConfig", return_value=config):
                default_image.cache_clear()
                default_rag_image.cache_clear()
                parser = create_argument_parser("test_backend_warning")
                configure_subcommands(parser)

                with patch("ramalama.plugins.runtimes.inference.llama_cpp.logger.warning") as mock_warning:
                    result = accel_image(config)
                    assert result == version_tagged_image("quay.io/ramalama/cuda")
                    mock_warning.assert_called_once()
                    call_args = mock_warning.call_args[0][0]
                    assert "may not be compatible" in call_args
                    assert "HIP GPU" in call_args


@pytest.mark.parametrize(
    "gpu_env,expected_backends",
    [
        ("HIP_VISIBLE_DEVICES", ["auto", "vulkan", "rocm"]),  # AMD
        ("CUDA_VISIBLE_DEVICES", ["auto", "cuda"]),  # NVIDIA
        ("INTEL_VISIBLE_DEVICES", ["auto", "vulkan", "sycl", "openvino"]),  # Intel (Vulkan preferred)
        ("ASAHI_VISIBLE_DEVICES", ["auto", "vulkan"]),  # Asahi
        (None, ["auto", "vulkan"]),  # No GPU
    ],
)
def test_get_available_backends(gpu_env: str | None, expected_backends: list[str], monkeypatch):
    """Test that available backends are correctly returned based on detected GPU."""
    monkeypatch.setattr("ramalama.common.get_accel", lambda: "none")

    env = {}
    if gpu_env:
        env[gpu_env] = "1"

    with patch.dict("os.environ", env, clear=True):
        assert get_available_backends() == expected_backends


@pytest.mark.parametrize(
    "gpu_env,expected_backends",
    [
        ("HIP_VISIBLE_DEVICES", ["auto", "rocm", "vulkan"]),  # AMD: ROCm preferred on Windows
        ("CUDA_VISIBLE_DEVICES", ["auto", "cuda"]),  # NVIDIA: same on all platforms
        ("INTEL_VISIBLE_DEVICES", ["auto", "sycl", "vulkan", "openvino"]),  # Intel: sycl preferred on Windows
        (None, ["auto", "vulkan"]),  # No GPU: same on all platforms
    ],
)
def test_get_available_backends_windows(gpu_env: str | None, expected_backends: list[str], monkeypatch):
    """Test that available backends on Windows prefer vendor-specific backends."""
    monkeypatch.setattr("ramalama.common.get_accel", lambda: "none")
    monkeypatch.setattr("ramalama.plugins.runtimes.inference.llama_cpp.platform.system", lambda: "Windows")

    env = {}
    if gpu_env:
        env[gpu_env] = "1"

    with patch.dict("os.environ", env, clear=True):
        assert get_available_backends() == expected_backends
