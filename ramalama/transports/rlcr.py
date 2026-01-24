import os
import subprocess

from ramalama.common import MNT_DIR, run_cmd
from ramalama.transports.oci import OCI
from ramalama.transports.oci_artifact import download_oci_artifact


def find_model_file_in_image(conman: str, model: str) -> str | None:
    """Inspect the OCI image to find model file location"""
    # First try to get from label
    try:
        cmd = [
            conman,
            "image",
            "inspect",
            "--format={{index .Config.Labels \"com.ramalama.model.file.location\"}}",
            model,
        ]
        result = run_cmd(cmd)
        model_file = result.stdout.decode('utf-8').strip()

        if model_file and model_file != '<no value>':
            return model_file
    except subprocess.CalledProcessError:
        pass

    # Fallback: try to find .gguf files in /models directory
    try:
        cmd = [conman, "run", "--rm", model, "ls", "/models"]
        result = run_cmd(cmd)
        files = result.stdout.decode('utf-8').strip().split('\n')

        # Look for .gguf files
        gguf_files = [f for f in files if f.endswith('.gguf')]
        if gguf_files:
            return gguf_files[0]  # Return first .gguf file found
    except subprocess.CalledProcessError:
        pass

    return None


class RamalamaContainerRegistry(OCI):
    def __init__(self, model: str, *args, **kwargs):
        super().__init__(f"rlcr.io/ramalama/{model}", *args, **kwargs)
        self._model_type = 'oci'
        self._artifact_downloaded = self._has_artifact_snapshot()
        if not self._artifact_downloaded:
            self._artifact_downloaded = super().exists()

    def pull(self, args):
        try:
            return super().pull(args)
        except subprocess.CalledProcessError as exc:
            if getattr(args, "dryrun", False):
                raise
            if self._attempt_artifact_pull(args):
                return
            raise exc

    def _attempt_artifact_pull(self, args) -> bool:
        return self._attempt_http_fetch(args)

    def _attempt_http_fetch(self, args) -> bool:
        registry, reference, _ = self._target_decompose(self.model)

        success = False
        previous_store = self._model_store
        self._model_store = None
        store = self.model_store
        try:
            _, cached_files, complete = store.get_cached_files(self.model_tag)
            if complete and cached_files:
                success = True
            else:
                success = download_oci_artifact(
                    registry=registry,
                    reference=reference,
                    model_store=store,
                    model_tag=self.model_tag,
                    args=args,
                )
        finally:
            self._model_store = store if success else previous_store

        if success:
            self._artifact_downloaded = True
        return success

    def _has_artifact_snapshot(self) -> bool:
        try:
            _, cached_files, complete = self.model_store.get_cached_files(self.model_tag)
            return complete and bool(cached_files)
        except Exception:
            return False

    def exists(self) -> bool:
        if self._artifact_downloaded or self._has_artifact_snapshot():
            self._artifact_downloaded = True
            return True
        return super().exists()

    def _get_entry_model_path(self, *args, **kwargs) -> str:
        if self._artifact_downloaded:
            original_model_type = self._model_type
            self._model_type = 'rlcr'
            try:
                return super()._get_entry_model_path(*args, **kwargs)
            finally:
                self._model_type = original_model_type

        model_filename = find_model_file_in_image(self.conman, self.model)
        if model_filename:
            model_basename = os.path.basename(model_filename)
            return os.path.join(MNT_DIR, model_basename)
        return os.path.join(MNT_DIR, "model.file")

    def setup_mounts(self, args):
        if getattr(self, "_artifact_downloaded", False):
            original_model_type = self._model_type
            self._model_type = 'rlcr'
            try:
                return super().setup_mounts(args)
            finally:
                self._model_type = original_model_type
        return super().setup_mounts(args)
