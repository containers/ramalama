import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ramalama import oci_tools
from ramalama.arg_types import EngineArgs
from ramalama.model_store.constants import DIRECTORY_NAME_BLOBS, DIRECTORY_NAME_REFS, DIRECTORY_NAME_SNAPSHOTS
from ramalama.model_store.reffile import RefJSONFile, migrate_reffile_to_refjsonfile


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
        self._store_base_path = Path(os.path.join(base_path, "store"))

    @property
    def path(self) -> Path:
        return self._store_base_path

    def list_models(self, engine: str, show_container: bool) -> Dict[str, List[ModelFile]]:
        models: Dict[str, List[ModelFile]] = {}

        for root, subdirs, _ in os.walk(self.path):
            if DIRECTORY_NAME_REFS in subdirs:
                ref_dir = Path(root).joinpath(DIRECTORY_NAME_REFS)
                for ref_file_name in os.listdir(ref_dir):
                    ref_file_path = ref_dir.joinpath(ref_file_name)
                    ref_file = migrate_reffile_to_refjsonfile(
                        ref_file_path, Path(root).joinpath(DIRECTORY_NAME_SNAPSHOTS)
                    )
                    if ref_file is None:
                        ref_file = RefJSONFile.from_path(ref_file_path)

                    model_path = root.replace(f"{self.path}", "").replace(os.sep, "", 1)

                    parts = model_path.split(os.sep)
                    model_source = parts[0]
                    model_path_without_source = "/".join(parts[1:])

                    separator = ":///" if model_source == "file" else "://"  # Use ':///' for file URLs, '://' otherwise
                    tag = ref_file_name.replace(".json", "")
                    model_name = f"{model_source}{separator}{model_path_without_source}:{tag}"

                    collected_files = []
                    for snapshot_file in ref_file.files:
                        is_partially_downloaded = False
                        snapshot_file_path = Path(root).joinpath(
                            DIRECTORY_NAME_SNAPSHOTS, ref_file.hash, snapshot_file.name
                        )
                        if not snapshot_file_path.exists():
                            blobs_partial_file_path = Path(root).joinpath(
                                DIRECTORY_NAME_BLOBS, ref_file.hash + ".partial"
                            )
                            if not blobs_partial_file_path.exists():
                                continue

                            snapshot_file_path = blobs_partial_file_path
                            is_partially_downloaded = True

                        last_modified = os.path.getmtime(snapshot_file_path)
                        file_size = os.path.getsize(snapshot_file_path)
                        collected_files.append(
                            ModelFile(snapshot_file.name, last_modified, file_size, is_partially_downloaded)
                        )
                    models[model_name] = collected_files

        if show_container:
            oci_models = oci_tools.list_models(EngineArgs(engine=engine))
            for oci_model in oci_models:
                name, modified, size = (oci_model["name"], oci_model["modified"], oci_model["size"])
                # oci_tools.list_models provides modified as timestamp string, convert it to unix timestamp
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
