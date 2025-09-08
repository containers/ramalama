import os
import subprocess
import warnings

from ramalama.common import MNT_DIR, run_cmd
from ramalama.transports.oci import OCI


def find_model_file_in_image(conman: str, model: str) -> str:
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

    warnings.warn("Could not find model file in image metadata. Using default model location")
    return "/models/model.file"


class RamalamaContainerRegistry(OCI):
    def __init__(self, *args, model: str, **kwargs):
        super().__init__(*args, model=f"rlcr.io/ramalama/{model}", **kwargs)
        self._model_type = 'oci'
        self._src_image_path = find_model_file_in_image(self.conman, self.model)
        self._model_filename = os.path.basename(self._src_image_path)
        self._model_entrypoint = os.path.join(MNT_DIR, self._model_filename)

    def _get_entry_model_path(self, *args, **kwargs) -> str:
        return self._model_entrypoint
