from types import SimpleNamespace

from ramalama.common import check_metal, check_nvidia
from ramalama.config import CONFIG
from ramalama.model_factory import CLASS_MODEL_TYPES


class CommandFactory:

    def __init__(
        self, model: CLASS_MODEL_TYPES, runtime: str, assigned_port: int, log_path: str, request_args: dict[str, str]
    ):
        self.model = model
        self.runtime = runtime
        self.assigned_port = assigned_port
        self.log_path = log_path
        self.request_args = request_args

    def build(self) -> list[str]:
        self._set_defaults()

        if self.runtime == "vllm":
            exec_args = self._build_vllm_serve_command()
        elif self.runtime == "mlx":
            exec_args = self._build_mlx_serve_command()
        else:
            exec_args = self._build_llama_serve_command()

        if self.request_args.get("seed"):
            exec_args += ["--seed", self.request_args.get("seed")]

        return exec_args

    def _set_defaults(self):
        if "ctx_size" not in self.request_args:
            self.request_args["ctx_size"] = CONFIG.ctx_size

        if "temp" not in self.request_args:
            self.request_args["temp"] = CONFIG.temp

        if "ngl" not in self.request_args:
            self.request_args["ngl"] = CONFIG.ngl

        if "threads" not in self.request_args:
            self.request_args["threads"] = CONFIG.threads

        if "runtime_args" not in self.request_args:
            self.request_args["runtime_args"] = []

        if "debug" not in self.request_args:
            self.request_args["debug"] = False

        if "webui" not in self.request_args:
            self.request_args["webui"] = ""

        if "thinking" not in self.request_args:
            self.request_args["thinking"] = False

        if "seed" not in self.request_args:
            self.request_args["seed"] = ""

    def _build_vllm_serve_command(self) -> list[str]:
        raise NotImplementedError("VLLM serve command building is not implemented yet.")

    def _build_mlx_serve_command(self) -> list[str]:
        raise NotImplementedError("MLX serve command building is not implemented yet.")

    def _build_llama_serve_command(self) -> list[str]:
        cmd = ["llama-server", "--host", "0.0.0.0", "--port", f"{self.assigned_port}", "--log-file", self.log_path]
        cmd += [
            "--model",
            self.model._get_entry_model_path(False, False, False),
            "--no-warmup",
        ]

        if self.request_args.get("thinking"):
            cmd += ["--reasoning-budget", "0"]

        mmproj_path = self.model._get_mmproj_path(False, False, False)
        if mmproj_path:
            cmd += ["--mmproj", mmproj_path]
        else:
            cmd += ["--jinja"]

            chat_template_path = self.model._get_chat_template_path(False, False, False)
            if chat_template_path:
                cmd += ["--chat-template-file", chat_template_path]

        cmd += [
            "--alias",
            self.model.model_name,
            "--ctx-size",
            f"{self.request_args.get('ctx_size')}",
            "--temp",
            f"{self.request_args.get('temp')}",
            "--cache-reuse",
            "256",
        ]
        cmd += self.request_args.get("runtime_args")

        if self.request_args.get("debug"):
            cmd += ["-v"]

        if self.request_args.get("webui") == "off":
            cmd.extend(["--no-webui"])

        if check_nvidia() or check_metal(SimpleNamespace({"container": False})):
            cmd.extend(["--flash-attn"])

        # gpu arguments
        ngl = self.request_args.get("ngl")
        if ngl < 0:
            ngl = 999
        cmd.extend(["-ngl", f"{ngl}"])
        threads = self.request_args.get("threads")
        cmd.extend(["--threads", str(threads)])

        return cmd
