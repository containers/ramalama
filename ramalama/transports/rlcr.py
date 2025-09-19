import os
import subprocess

from ramalama.common import MNT_DIR, run_cmd
from ramalama.transports.oci import OCI


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
    def __init__(self, *args, model: str, **kwargs):
        super().__init__(*args, model=f"rlcr.io/ramalama/{model}", **kwargs)
        self._model_type = 'oci'

    def _get_entry_model_path(self, *args, **kwargs) -> str:
        model_filename = find_model_file_in_image(self.conman, self.model)
        if model_filename:
            model_basename = os.path.basename(model_filename)
            return os.path.join(MNT_DIR, model_basename)
        return os.path.join(MNT_DIR, "model.file")
