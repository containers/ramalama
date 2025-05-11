import os
import shutil

from ramalama.common import download_file, generate_sha256
from ramalama.huggingface import HuggingfaceRepository
from ramalama.model import Model
from ramalama.model_store import SnapshotFile, SnapshotFileType
from ramalama.modelscope import ModelScopeRepository


class LocalModelFile(SnapshotFile):
    def __init__(
        self,
        url,
        header,
        model_file_hash,
        name,
        should_show_progress=False,
        should_verify_checksum=False,
        required=True,
    ):
        super().__init__(
            url,
            header,
            model_file_hash,
            name,
            SnapshotFileType.Model,
            should_show_progress,
            should_verify_checksum,
            required,
        )

    def download(self, blob_file_path, snapshot_dir):
        if not os.path.exists(self.url):
            raise FileNotFoundError(f"No such file: '{self.url}'")
        # moving from the local location to blob directory so the model store "owns" the data
        shutil.copy(self.url, blob_file_path)
        return os.path.relpath(blob_file_path, start=snapshot_dir)


class URL(Model):
    def __init__(self, model, scheme):
        super().__init__(model)

        # Use the URL scheme as model type so we can distinguish
        # between the various types such as http, https and file
        self._model_type = scheme

        self.type = scheme
        split = self.model.rsplit("/", 1)
        self.directory = split[0].removeprefix("/") if len(split) > 1 else ""

    def extract_model_identifiers(self):
        model_name, model_tag, model_organization = super().extract_model_identifiers()

        parts = model_organization.split("/")
        if len(parts) > 2 and parts[-2] == "blob":
            model_organization = "/".join(parts[:-2])
            model_tag = parts[-1]

        # handling huggingface specific URLs for more precise identifiers
        if len(parts) > 2 and HuggingfaceRepository.REGISTRY_URL.endswith(parts[0]) and parts[-2] == "resolve":
            model_organization = "/".join(parts[:-2])
            model_tag = parts[-1]

        if len(parts) > 3 and parts[-3] == "file":
            model_organization = "/".join(parts[:-3])
            model_tag = parts[-1]

        # handling modelscope specific URLs for more precise identifiers
        if len(parts) > 2 and ModelScopeRepository.REGISTRY_URL.endswith(parts[0]) and parts[-2] == "resolve":
            model_organization = "/".join(parts[:-2])
            model_tag = parts[-1]

        return model_name, model_tag, model_organization

    def pull(self, args):
        if self.store is not None:
            return self._pull_with_model_store()

        model_path = self.model_path(args)
        directory_path = os.path.join(args.store, "repos", self.type, self.directory, self.filename)
        os.makedirs(directory_path, exist_ok=True)

        symlink_dir = os.path.dirname(model_path)
        os.makedirs(symlink_dir, exist_ok=True)

        target_path = os.path.join(directory_path, self.filename)

        if self.type == "file":
            if not os.path.exists(self.model):
                raise FileNotFoundError(f"{self.model} no such file")
            os.symlink(self.model, os.path.join(symlink_dir, self.filename))
            os.symlink(self.model, target_path)
        else:
            show_progress = not args.quiet
            url = self.type + "://" + self.model
            # Download the model file to the target path
            download_file(url, target_path, headers={}, show_progress=show_progress)
            relative_target_path = os.path.relpath(target_path, start=os.path.dirname(model_path))
            if self.check_valid_model_path(relative_target_path, model_path):
                # Symlink is already correct, no need to update it
                return model_path
            os.symlink(relative_target_path, model_path)

        return model_path

    def _pull_with_model_store(self):
        name, tag, _ = self.extract_model_identifiers()
        model_file_hash, _, all_files = self.store.get_cached_files(tag)
        if all_files:
            return self.store.get_snapshot_file_path(model_file_hash, name)

        files: list[SnapshotFile] = []
        snapshot_hash = generate_sha256(name)
        if self.type == "file":
            files.append(
                LocalModelFile(
                    url=self.model,  # model contains the full path here
                    header={},
                    model_file_hash=snapshot_hash,
                    name=name,
                    required=True,
                )
            )
        else:
            files.append(
                SnapshotFile(
                    url=f"{self.type}://{self.model}",
                    header={},
                    hash=snapshot_hash,
                    type=SnapshotFileType.Model,
                    name=name,
                    should_show_progress=True,
                    required=True,
                )
            )

        self.store.new_snapshot(tag, snapshot_hash, files)

        return self.store.get_snapshot_file_path(snapshot_hash, name)
