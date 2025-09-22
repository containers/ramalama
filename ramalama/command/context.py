import argparse
import os
from typing import Optional

from ramalama.common import check_metal, check_nvidia
from ramalama.console import should_colorize
from ramalama.transports.transport_factory import CLASS_MODEL_TYPES, New


class RamalamaArgsContext:

    def __init__(self):
        self.host: Optional[str] = None
        self.port: Optional[int] = None
        self.thinking: Optional[bool] = None
        self.ctx_size: Optional[int] = None
        self.cache_reuse: Optional[int] = None
        self.temp: Optional[float] = None
        self.debug: Optional[bool] = None
        self.webui: Optional[bool] = None
        self.ngl: Optional[int] = None
        self.threads: Optional[int] = None
        self.logfile: Optional[str] = None
        self.container: Optional[bool] = None
        self.model_draft: Optional[str] = None
        self.seed: Optional[int] = None
        self.runtime_args: Optional[str] = None

    @staticmethod
    def from_argparse(args: argparse.Namespace) -> "RamalamaArgsContext":
        ctx = RamalamaArgsContext()
        ctx.host = getattr(args, "host", None)
        ctx.port = getattr(args, "port", None)
        ctx.thinking = getattr(args, "thinking", None)
        ctx.ctx_size = getattr(args, "context", None)
        ctx.temp = getattr(args, "temp", None)
        ctx.debug = getattr(args, "debug", None)
        ctx.webui = getattr(args, "webui", None)
        ctx.ngl = getattr(args, "ngl", None)
        ctx.threads = getattr(args, "threads", None)
        ctx.logfile = getattr(args, "logfile", None)
        ctx.container = getattr(args, "container", None)
        ctx.model_draft = getattr(args, "model_draft", None)
        ctx.seed = getattr(args, "seed", None)
        ctx.runtime_args = getattr(args, "runtime_args", None)
        ctx.cache_reuse = getattr(args, "cache_reuse", None)
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


class RamalamaFuncContext:

    def __init__(self, is_container: bool):
        self.is_container = is_container

    def check_nvidia(self) -> bool:
        return check_nvidia() is not True

    def check_metal(self) -> bool:
        return check_metal(argparse.Namespace(**{"container": self.is_container}))

    def should_colorize(self) -> bool:
        return should_colorize()

    def get_rpc_nodes(self) -> Optional[str]:
        return os.getenv("RAMALAMA_LLAMACPP_RPC_NODES", None)


class RamalamaCommandContext:

    def __init__(self, args: RamalamaArgsContext, model: RamalamaModelContext, func: RamalamaFuncContext):
        self.args = args
        self.model = model
        self.func = func

    @staticmethod
    def from_argparse(cli_args: argparse.Namespace) -> "RamalamaCommandContext":
        args = RamalamaArgsContext.from_argparse(cli_args)
        should_generate = hasattr(cli_args, "generate")
        dry_run = getattr(cli_args, "dryrun", False)
        is_container = getattr(cli_args, "container", True)
        model = RamalamaModelContext(New(cli_args.MODEL, cli_args), is_container, should_generate, dry_run)
        func = RamalamaFuncContext(is_container)
        return RamalamaCommandContext(args, model, func)
