import copy
import re
from typing import Callable, Tuple, Union
from urllib.parse import urlparse

from ramalama.arg_types import StoreArgs
from ramalama.common import rm_until_substring
from ramalama.config import CONFIG
from ramalama.huggingface import Huggingface
from ramalama.model import MODEL_TYPES, SPLIT_MODEL_RE, is_split_file_model
from ramalama.modelscope import ModelScope
from ramalama.oci import OCI
from ramalama.ollama import Ollama
from ramalama.url import URL


class ModelFactory:
    def __init__(
        self,
        model: str,
        args: StoreArgs,
        transport: str = "ollama",
        ignore_stderr: bool = False,
        no_children: bool = False,
    ):
        self.model = model
        self.store_path = args.store
        self.transport = transport
        self.engine = args.engine
        self.ignore_stderr = ignore_stderr
        self.container = args.container

        self.model_cls: type[Union[Huggingface, ModelScope, Ollama, OCI, URL]]
        self.create: Callable[[], Union[Huggingface, ModelScope, Ollama, OCI, URL]]
        self.model_cls, self.create = self.detect_model_model_type()

        self.pruned_model = self.prune_model_input()
        self.draft_model = None
        if getattr(args, 'model_draft', None):
            dm_args = copy.deepcopy(args)
            dm_args.model_draft = None
            self.draft_model = ModelFactory(args.model_draft, dm_args, ignore_stderr=True).create()
        if (not no_children) and is_split_file_model(model):
            sm_args = copy.deepcopy(args)
            sm_args.model_draft = None
            if is_split_file_model(model):
                match = re.match(SPLIT_MODEL_RE, model)
                path_part = match[1]
                filename_base = match[2]
                total_parts = int(match[3])
                # the model will be nr=1 (first) the child will be the higher numbers
                self.split_model = {}

                self.mnt_path = f"{filename_base}-00001-of-{total_parts:05d}.gguf"
                for i in range(total_parts - 1):
                    i_off = i + 2
                    src_file = f"{path_part}/{filename_base}-{i_off:05d}-of-{total_parts:05d}.gguf"
                    dst_file = f"{filename_base}-{i_off:05d}-of-{total_parts:05d}.gguf"
                    self.split_model[dst_file] = ModelFactory(
                        src_file, sm_args, ignore_stderr=True, no_children=True
                    ).create()

    def detect_model_model_type(
        self,
    ) -> Tuple[type[Union[Huggingface, Ollama, OCI, URL]], Callable[[], Union[Huggingface, Ollama, OCI, URL]]]:
        for prefix in ["huggingface://", "hf://", "hf.co/"]:
            if self.model.startswith(prefix):
                return Huggingface, self.create_huggingface
        for prefix in ["modelscope://", "ms://"]:
            if self.model.startswith(prefix):
                return ModelScope, self.create_modelscope
        for prefix in ["ollama://", "ollama.com/library/"]:
            if self.model.startswith(prefix):
                return Ollama, self.create_ollama
        for prefix in ["oci://", "docker://"]:
            if self.model.startswith(prefix):
                return OCI, self.create_oci
        for prefix in ["http://", "https://", "file://"]:
            if self.model.startswith(prefix):
                return URL, self.create_url
        if self.transport == "huggingface":
            return Huggingface, self.create_huggingface
        if self.transport == "modelscope":
            return ModelScope, self.create_modelscope
        if self.transport == "ollama":
            return Ollama, self.create_ollama
        if self.transport == "oci":
            return OCI, self.create_oci

        raise KeyError(f'transport "{self.transport}" not supported. Must be oci, huggingface, modelscope, or ollama.')

    def prune_model_input(self) -> str:
        # remove protocol from model input
        pruned_model_input = rm_until_substring(self.model, "://")

        if self.model_cls == Huggingface:
            pruned_model_input = rm_until_substring(pruned_model_input, "hf.co/")
        elif self.model_cls == ModelScope:
            pruned_model_input = rm_until_substring(pruned_model_input, "modelscope.cn/")
        elif self.model_cls == Ollama:
            pruned_model_input = rm_until_substring(pruned_model_input, "ollama.com/library/")

        return pruned_model_input

    def validate_oci_model_input(self):
        if self.model.startswith("oci://") or self.model.startswith("docker://"):
            return

        for t in MODEL_TYPES:
            if self.model.startswith(t + "://"):
                raise ValueError(f"{self.model} invalid: Only OCI Model types supported")

    def create_huggingface(self) -> Huggingface:
        model = Huggingface(self.pruned_model, self.store_path)
        model.draft_model = self.draft_model
        return model

    def create_modelscope(self) -> ModelScope:
        model = ModelScope(self.pruned_model, self.store_path)
        model.draft_model = self.draft_model
        return model

    def create_ollama(self) -> Ollama:
        model = Ollama(self.pruned_model, self.store_path)
        model.draft_model = self.draft_model
        return model

    def create_oci(self) -> OCI:
        if not self.container:
            raise ValueError("OCI containers cannot be used with the --nocontainer option.")

        self.validate_oci_model_input()
        model = OCI(self.pruned_model, self.store_path, self.engine, self.ignore_stderr)
        model.draft_model = self.draft_model
        return model

    def create_url(self) -> URL:
        model = URL(self.pruned_model, self.store_path, urlparse(self.model).scheme)
        model.draft_model = self.draft_model
        if getattr(self, 'split_model', None):
            model.split_model = self.split_model
            model.mnt_path = self.mnt_path
        return model


def New(name, args, transport: str = None) -> ModelFactory:
    if transport is None:
        transport = CONFIG.transport
    return ModelFactory(name, args, transport=transport).create()


def Serve(name, args):
    model = New(name, args)
    try:
        model.serve(args)
    except KeyError as e:
        try:
            args.quiet = True
            model = ModelFactory(name, args, ignore_stderr=True).create_oci()
            model.serve(args)
        except Exception:
            raise e
