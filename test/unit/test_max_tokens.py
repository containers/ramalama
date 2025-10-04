from types import SimpleNamespace
from unittest.mock import Mock, patch

from ramalama.model import Model


class TestMaxTokensIntegration:
    """Test max_tokens parameter integration across different runtimes"""

    def setup_method(self):
        self.base_args = SimpleNamespace(
            container=False,
            generate=False,
            dryrun=True,  # Enable dry run to avoid path lookups
            runtime_args=[],
            debug=False,
            context=2048,
            temp="0.8",
            cache_reuse=256,
            port="8080",
            host="localhost",
            seed=None,
            max_tokens=512,  # Test value
            thinking=True,  # Add missing attribute
        )

    def test_llama_cpp_max_tokens_parameter(self):
        """Test that max_tokens is mapped to -n for llama.cpp"""
        model = Model("test", "test")
        model.model = "test_model"
        model.draft_model = None  # Initialize draft_model attribute

        exec_args = model.llama_serve(self.base_args)

        # Check that -n parameter is added with correct value
        assert "-n" in exec_args
        n_index = exec_args.index("-n")
        assert exec_args[n_index + 1] == "512"

    def test_llama_cpp_no_max_tokens_when_zero(self):
        """Test that -n parameter is not added when max_tokens is 0"""
        args = SimpleNamespace(**vars(self.base_args))
        args.max_tokens = 0

        model = Model("test", "test")
        model.model = "test_model"
        model.draft_model = None

        exec_args = model.llama_serve(args)

        # Check that -n parameter is not added
        assert "-n" not in exec_args

    @patch('ramalama.transports.base.Transport._get_entry_model_path')
    def test_mlx_max_tokens_parameter(self, mock_get_path):
        """Test that max_tokens is mapped to --max-tokens for MLX"""
        mock_get_path.return_value = "/test/model/path"
        model = Model("test", "test")

        exec_args = model._build_mlx_exec_args("server", self.base_args)

        # Check that --max-tokens parameter is added with correct value
        assert "--max-tokens" in exec_args
        max_tokens_index = exec_args.index("--max-tokens")
        assert exec_args[max_tokens_index + 1] == "512"

    @patch('ramalama.transports.base.Transport._get_entry_model_path')
    def test_mlx_context_mapped_to_max_kv_size(self, mock_get_path):
        """Test that context is mapped to --max-kv-size for MLX (not --max-tokens)"""
        mock_get_path.return_value = "/test/model/path"
        model = Model("test", "test")

        exec_args = model._build_mlx_exec_args("server", self.base_args)

        # Check that context is mapped to --max-kv-size, not --max-tokens
        assert "--max-kv-size" in exec_args
        max_kv_size_index = exec_args.index("--max-kv-size")
        assert exec_args[max_kv_size_index + 1] == "2048"

    @patch('ramalama.model.Model._get_entry_model_path')
    def test_vllm_max_tokens_parameter(self, mock_get_path):
        """Test that max_tokens is mapped to --max-tokens for vLLM"""
        mock_get_path.return_value = "/test/model/path"
        model = Model("test", "test")

        exec_args = model.vllm_serve(self.base_args)

        # Check that --max-tokens parameter is added with correct value
        assert "--max-tokens" in exec_args
        max_tokens_index = exec_args.index("--max-tokens")
        assert exec_args[max_tokens_index + 1] == "512"

    @patch('ramalama.model.Model._get_entry_model_path')
    def test_vllm_no_max_tokens_when_zero(self, mock_get_path):
        """Test that --max-tokens parameter is not added when max_tokens is 0"""
        mock_get_path.return_value = "/test/model/path"
        args = SimpleNamespace(**vars(self.base_args))
        args.max_tokens = 0

        model = Model("test", "test")

        exec_args = model.vllm_serve(args)

        # Check that --max-tokens parameter is not added
        assert "--max-tokens" not in exec_args

    def test_runtime_args_still_work(self):
        """Test that existing runtime_args functionality is preserved"""
        args = SimpleNamespace(**vars(self.base_args))
        args.runtime_args = ["--custom-arg", "custom-value"]

        model = Model("test", "test")
        model.model = "test_model"
        model.draft_model = None

        exec_args = model.llama_serve(args)

        # Check that both max_tokens and runtime_args are present
        assert "-n" in exec_args
        assert "--custom-arg" in exec_args
        assert "custom-value" in exec_args

    def test_daemon_command_factory_llama_cpp_max_tokens(self):
        """Test that daemon command factory handles max_tokens for llama.cpp"""
        from ramalama.daemon.service.command_factory import CommandFactory

        # Create a mock model
        mock_model = Mock()
        mock_model._get_entry_model_path.return_value = "/test/model/path"
        mock_model._get_mmproj_path.return_value = None
        mock_model._get_chat_template_path.return_value = None
        mock_model.model_name = "test_model"

        request_args = {
            "max_tokens": 256,
            "ctx_size": 2048,
            "temp": "0.8",
            "ngl": -1,
            "threads": 4,
            "runtime_args": [],
            "debug": False,
            "webui": "",
            "thinking": False,
            "seed": "",
        }

        factory = CommandFactory(mock_model, "llama.cpp", 8080, "/tmp/log", request_args)
        exec_args = factory._build_llama_serve_command()

        # Check that -n parameter is added with correct value
        assert "-n" in exec_args
        n_index = exec_args.index("-n")
        assert exec_args[n_index + 1] == "256"
