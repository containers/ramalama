import argparse
import os
from typing import Optional

from ramalama.common import check_metal, check_nvidia
from ramalama.console import should_colorize
from ramalama.transports.transport_factory import CLASS_MODEL_TYPES, New


class RamalamaArgsContext:
    def __init__(self) -> None:
        self.cache_reuse: Optional[int] = None
        self.container: Optional[bool] = None
        self.ctx_size: Optional[int] = None
        self.debug: Optional[bool] = None
        self.host: Optional[str] = None
        self.gguf: Optional[str] = None
        self.logfile: Optional[str] = None
        self.max_tokens: Optional[int] = None
        self.model_draft: Optional[str] = None
        self.ngl: Optional[int] = None
        self.port: Optional[int] = None
        self.runtime_args: Optional[str] = None
        self.seed: Optional[int] = None
        self.temp: Optional[float] = None
        self.thinking: Optional[bool] = None
        self.threads: Optional[int] = None
        self.webui: Optional[bool] = None

    @staticmethod
    def from_argparse(args: argparse.Namespace) -> "RamalamaArgsContext":
        ctx = RamalamaArgsContext()
        ctx.cache_reuse = getattr(args, "cache_reuse", None)
        ctx.container = getattr(args, "container", None)
        ctx.ctx_size = getattr(args, "context", None)
        ctx.debug = getattr(args, "debug", None)
        ctx.host = getattr(args, "host", None)
        ctx.gguf = getattr(args, "gguf", None)
        ctx.logfile = getattr(args, "logfile", None)
        ctx.max_tokens = getattr(args, "max_tokens", None)
        ctx.model_draft = getattr(args, "model_draft", None)
        ctx.ngl = getattr(args, "ngl", None)
        ctx.port = getattr(args, "port", None)
        ctx.runtime_args = getattr(args, "runtime_args", None)
        ctx.seed = getattr(args, "seed", None)
        ctx.temp = getattr(args, "temp", None)
        ctx.thinking = getattr(args, "thinking", None)
        ctx.threads = getattr(args, "threads", None)
        ctx.webui = getattr(args, "webui", None)
        return ctx


class RamalamaRagGenArgsContext:
    def __init__(self) -> None:
        self.debug: bool | None = None
        self.format: str | None = None
        self.ocr: bool | None = None
        self.inputdir: str | None = None
        self.paths: list[str] | None = None
        self.urls: list[str] | None = None

    @staticmethod
    def from_argparse(args: argparse.Namespace) -> "RamalamaRagGenArgsContext":
        ctx = RamalamaRagGenArgsContext()
        ctx.debug = getattr(args, "debug", None)
        ctx.format = getattr(args, "format", None)
        ctx.ocr = getattr(args, "ocr", None)
        ctx.inputdir = getattr(args, "inputdir", None)
        ctx.paths = getattr(args, "PATHS", None)
        ctx.urls = getattr(args, "urls", None)
        return ctx


class RamalamaRagArgsContext:
    def __init__(self) -> None:
        self.debug: bool | None = None
        self.port: str | None = None
        self.model_host: str | None = None
        self.model_port: str | None = None

    @staticmethod
    def from_argparse(args: argparse.Namespace) -> "RamalamaRagArgsContext":
        ctx = RamalamaRagArgsContext()
        ctx.debug = getattr(args, "debug", None)
        ctx.port = getattr(args, "port", None)
        ctx.model_host = getattr(args, "model_host", None)
        ctx.model_port = getattr(args, "model_port", None)
        return ctx


class RamalamaModelContext:
    def __init__(self, model: CLASS_MODEL_TYPES, is_container: bool, should_generate: bool, dry_run: bool):
        self.model = model
        self.is_container = is_container
        self.should_generate = should_generate
        self.dry_run = dry_run

    @property
    def name(self) -> str:
        return f"{self.model.model_name}:{self.model.model_tag}"

    @property
    def alias(self) -> str:
        return self.model.model_alias

    @property
    def model_path(self) -> str:
        return self.model._get_entry_model_path(self.is_container, self.should_generate, self.dry_run)

    @property
    def mmproj_path(self) -> Optional[str]:
        return self.model._get_mmproj_path(self.is_container, self.should_generate, self.dry_run)

    @property
    def chat_template_path(self) -> Optional[str]:
        return self.model._get_chat_template_path(self.is_container, self.should_generate, self.dry_run)

    @property
    def draft_model_path(self) -> str:
        if getattr(self.model, "draft_model", None):
            assert self.model.draft_model
            return self.model.draft_model._get_entry_model_path(self.is_container, self.should_generate, self.dry_run)
        return ""


class RamalamaHostContext:
    def __init__(
        self, is_container: bool, uses_nvidia: bool, uses_metal: bool, should_colorize: bool, rpc_nodes: Optional[str]
    ):
        self.is_container = is_container
        self.uses_nvidia = uses_nvidia
        self.uses_metal = uses_metal
        self.should_colorize = should_colorize
        self.rpc_nodes = rpc_nodes


class RamalamaCommandContext:
    def __init__(
        self,
        args: RamalamaArgsContext | RamalamaRagGenArgsContext | RamalamaRagArgsContext,
        model: RamalamaModelContext | None,
        host: RamalamaHostContext,
    ):
        self.args = args
        self.model = model
        self.host = host

    @staticmethod
    def from_argparse(cli_args: argparse.Namespace) -> "RamalamaCommandContext":
        args: RamalamaArgsContext | RamalamaRagGenArgsContext | RamalamaRagArgsContext
        if cli_args.subcommand == "rag":
            args = RamalamaRagGenArgsContext.from_argparse(cli_args)
        elif cli_args.subcommand in ("run --rag", "serve --rag"):
            args = RamalamaRagArgsContext.from_argparse(cli_args)
        else:
            args = RamalamaArgsContext.from_argparse(cli_args)
        should_generate = getattr(cli_args, "generate", None) is not None
        dry_run = getattr(cli_args, "dryrun", False)
        is_container = getattr(cli_args, "container", True)
        if hasattr(cli_args, "MODEL"):
            model = RamalamaModelContext(New(cli_args.MODEL, cli_args), is_container, should_generate, dry_run)
        elif hasattr(cli_args, "model"):
            model = cli_args.model
        else:
            model = None

        host = RamalamaHostContext(
            is_container,
            check_nvidia() is not None,
            check_metal(argparse.Namespace(**{"container": is_container})),
            should_colorize(),
            os.getenv("RAMALAMA_LLAMACPP_RPC_NODES", None),
        )
        return RamalamaCommandContext(args, model, host)
