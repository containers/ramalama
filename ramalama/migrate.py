#
# Utility for migrating from the old to the new model store
#
import os
import shutil

from ramalama.common import generate_sha256
from ramalama.model import MODEL_TYPES
from ramalama.model_factory import ModelFactory
from ramalama.model_store import GlobalModelStore, SnapshotFile, SnapshotFileType


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class ModelStoreImport:
    def __init__(self, store_path: str):
        self.store_path = store_path
        self._old_model_path = os.path.join(store_path, "models")
        self._old_repo_path = os.path.join(store_path, "repos")
        self._global_store = GlobalModelStore(self.store_path)

    class LocalModelFile(SnapshotFile):
        def __init__(
            self, url, header, hash, name, should_show_progress=False, should_verify_checksum=False, required=True
        ):
            super().__init__(
                url, header, hash, name, SnapshotFileType.Model, should_show_progress, should_verify_checksum, required
            )

        def download(self, blob_file_path, snapshot_dir):
            if not os.path.exists(self.url):
                raise FileNotFoundError(f"No such file: '{self.url}'")
            # moving from the local location to blob directory so the model store "owns" the data
            shutil.copy(self.url, blob_file_path)
            return os.path.relpath(blob_file_path, start=snapshot_dir)

    def import_all(self):
        if not os.path.exists(self._old_model_path):
            return

        print("Starting importing AI models to new store ...")
        for root, _, files in os.walk(self._old_model_path):
            if not files:
                continue

            try:
                # reconstruct the cli model input
                model = root.replace(self._old_model_path, "")
                model = model.replace(os.sep, "", 1)
                if model.startswith("file/"):
                    model = model.replace("/", ":///", 1)
                else:
                    model = model.replace("/", "://", 1)

                if model in MODEL_TYPES:
                    model = ""

                for file in files:
                    m = ModelFactory(
                        os.path.join(model, file),
                        args=dotdict(
                            {
                                "store": self.store_path,
                                "use_model_store": True,
                                "engine": "podman",
                                "container": True,
                            }
                        ),
                    ).create()
                    _, model_tag, _ = m.extract_model_identifiers()
                    _, _, all = m.store.get_cached_files(model_tag)
                    if all:
                        print(f"Already imported: {root}/{file}")
                        continue

                    filename = file
                    # remove ":" symbol and model tag from name
                    if filename.endswith(f":{model_tag}"):
                        filename = filename.replace(f":{model_tag}", "")

                    snapshot_hash = generate_sha256(filename)
                    old_model_path = os.path.join(root, filename)

                    snapshot_files: list[SnapshotFile] = []
                    snapshot_files.append(
                        ModelStoreImport.LocalModelFile(
                            url=old_model_path,
                            header={},
                            hash=snapshot_hash,
                            name=filename,
                            required=True,
                        )
                    )

                    m.store.new_snapshot(model_tag, snapshot_hash, snapshot_files)
                    print(f"Imported {old_model_path} -> {m.store.get_snapshot_file_path(snapshot_hash, filename)}")

            except Exception as ex:
                print(f"Failed to import {root}: {ex}")

        if os.path.exists(self._old_model_path):
            try:
                shutil.rmtree(self._old_model_path)
            except Exception as ex:
                print(f"Failed to remove old model directory: {ex}")
        if os.path.exists(self._old_repo_path):
            try:
                shutil.rmtree(self._old_repo_path)
            except Exception as ex:
                print(f"Failed to remove old blob directory: {ex}")
