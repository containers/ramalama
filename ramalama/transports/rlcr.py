import hashlib
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

    def _build_docker_mount_command(self) -> str:
        """Builds a Docker-compatible mount string that mirrors Podman image mounts for model assets."""

        vol_hash = hashlib.sha256(self.model.encode()).hexdigest()[:12]
        volume = f"ramalama-models-{vol_hash}"
        src = f"src-{vol_hash}"

        # Ensure volume exists
        run_cmd([self.conman, "volume", "create", volume], ignore_stderr=True)

        # Fresh source container to export from
        run_cmd([self.conman, "rm", "-f", src], ignore_stderr=True)
        run_cmd([self.conman, "create", "--name", src, self.model])

        try:
            # Stream whole rootfs -> extract only models/<basename> into volume root
            export_cmd = [self.conman, "export", src]
            untar_cmd = [
                self.conman,
                "run",
                "--rm",
                "-i",
                "--mount",
                f"type=volume,src={volume},dst=/mnt",
                "busybox",
                "tar",
                "-C",
                "/mnt",
                "--strip-components=1",
                "-x",
                "-p",
                "-f",
                "-",
                f"models/{self._model_filename}",
            ]

            with (
                subprocess.Popen(export_cmd, stdout=subprocess.PIPE) as p_out,
                subprocess.Popen(untar_cmd, stdin=p_out.stdout) as p_in,
            ):
                p_out.stdout.close()
                rc_in = p_in.wait()
                rc_out = p_out.wait()
                if rc_in != 0 or rc_out != 0:
                    raise subprocess.CalledProcessError(rc_in or rc_out, untar_cmd if rc_in else export_cmd)
        finally:
            run_cmd([self.conman, "rm", "-f", src], ignore_stderr=True)

        # Mount the hydrated volume read-only in the MNT_DIR
        return f"--mount=type=volume,src={volume},dst={MNT_DIR},readonly"

    def setup_mounts(self, args):
        if args.dryrun:
            return

        if self.engine.use_podman:
            mount_cmd = f"--mount=type=image,src={self.model},destination={MNT_DIR},subpath=/models,rw=false"
        else:
            mount_cmd = self._build_docker_mount_command()

        self.engine.add([mount_cmd])
