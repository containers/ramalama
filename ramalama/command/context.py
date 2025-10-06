import argparse
import os
from typing import Optional

from ramalama.common import check_metal, check_nvidia
from ramalama.console import should_colorize
from ramalama.transports.transport_factory import CLASS_MODEL_TYPES, New


class RamalamaArgsContext:

    def __init__(self):
        self.cache_reuse: Optional[int] = None
        self.container: Optional[bool] = None
        self.ctx_size: Optional[int] = None
        self.debug: Optional[bool] = None
        self.host: Optional[str] = None
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
        return f"{self.model.model_organization}/{self.model.model_name}"

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
        if hasattr(self.model, "draft_model"):
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

    def __init__(self, args: RamalamaArgsContext, model: RamalamaModelContext, host: RamalamaHostContext):
        self.args = args
        self.model = model
        self.host = host

    @staticmethod
    def from_argparse(cli_args: argparse.Namespace) -> "RamalamaCommandContext":
        args = RamalamaArgsContext.from_argparse(cli_args)
        should_generate = hasattr(cli_args, "generate")
        dry_run = getattr(cli_args, "dryrun", False)
        is_container = getattr(cli_args, "container", True)
        model = RamalamaModelContext(New(cli_args.MODEL, cli_args), is_container, should_generate, dry_run)
        host = RamalamaHostContext(
            is_container,
            check_nvidia() is None,
            check_metal(argparse.Namespace(**{"container": is_container})),
            should_colorize(),
            os.getenv("RAMALAMA_LLAMACPP_RPC_NODES", None),
        )
        return RamalamaCommandContext(args, model, host)
