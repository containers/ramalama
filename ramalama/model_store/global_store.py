import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

import ramalama.oci
from ramalama.arg_types import EngineArgs
from ramalama.model_store.constants import DIRECTORY_NAME_BLOBS, DIRECTORY_NAME_REFS, DIRECTORY_NAME_SNAPSHOTS
from ramalama.model_store.reffile import RefFile


@dataclass
class ModelFile:
    name: str
    modified: float
    size: int
    is_partial: bool


class GlobalModelStore:
    def __init__(
        self,
        base_path: str,
    ):
        self._store_base_path = os.path.join(base_path, "store")

    @property
    def path(self) -> str:
        return self._store_base_path

    def list_models(self, engine: str, show_container: bool) -> Dict[str, List[ModelFile]]:
        models: Dict[str, List[ModelFile]] = {}

        for root, subdirs, _ in os.walk(self.path):
            if DIRECTORY_NAME_REFS in subdirs:
                ref_dir = os.path.join(root, DIRECTORY_NAME_REFS)
                for ref_file_name in os.listdir(ref_dir):
                    ref_file: RefFile = RefFile.from_path(os.path.join(ref_dir, ref_file_name))
                    model_path = root.replace(self.path, "").replace(os.sep, "", 1)

                    parts = model_path.split("/")
                    model_source = parts[0]
                    model_path_without_source = f"{os.sep}".join(parts[1:])

                    separator = ":///" if model_source == "file" else "://"  # Use ':///' for file URLs, '://' otherwise
                    tag = ref_file_name.replace(".json", "")
                    model_name = f"{model_source}{separator}{model_path_without_source}:{tag}"

                    collected_files = []
                    for snapshot_file in ref_file.filenames:
                        is_partially_downloaded = False
                        snapshot_file_path = os.path.join(root, DIRECTORY_NAME_SNAPSHOTS, ref_file.hash, snapshot_file)
                        if not os.path.exists(snapshot_file_path):
                            blobs_partial_file_path = os.path.join(
                                root, DIRECTORY_NAME_BLOBS, ref_file.hash + ".partial"
                            )
                            if not os.path.exists(blobs_partial_file_path):
                                continue

                            snapshot_file_path = blobs_partial_file_path
                            is_partially_downloaded = True

                        last_modified = os.path.getmtime(snapshot_file_path)
                        file_size = os.path.getsize(snapshot_file_path)
                        collected_files.append(
                            ModelFile(snapshot_file, last_modified, file_size, is_partially_downloaded)
                        )
                    models[model_name] = collected_files

        if show_container:
            oci_models = ramalama.oci.list_models(EngineArgs(engine=engine))
            for oci_model in oci_models:
                name, modified, size = (oci_model["name"], oci_model["modified"], oci_model["size"])
                # ramalama.oci.list_models provides modified as timestamp string, convert it to unix timestamp
                modified_unix = datetime.fromisoformat(modified).timestamp()
                models[name] = [ModelFile(name, modified_unix, size, is_partial=False)]

        return models

    # TODO:
    # iterating over all symlinks in snapshot dir, check valid
    def verify_snapshot(self):
        pass

    # TODO:
    # iterating over models and check
    #    1. for broken symlinks in snapshot dirs -> delete and update refs
    #    2. for blobs not reached by ref->snapshot chain -> delete
    #    3. for empty folders -> delete
    def cleanup(self):
        pass
