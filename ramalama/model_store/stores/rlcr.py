import subprocess
import tempfile
from ramalama.oci import OCI
from ramalama.common import MNT_DIR, run_cmd


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
            # Remove /models/ prefix if present
            return model_file
    except subprocess.CalledProcessError:
        pass

    # Fallback: inspect container filesystem for .gguf files
    try:
        cmd = [conman, "run", "--rm", model, "ls", "/models"]
        result = run_cmd(cmd)
        model_files = result.stdout.decode('utf-8').strip().split('\n')
        model_files = (f for f in model_files if f.strip().endswith('.gguf'))
        for model_file in model_files:
            return model_file.strip()
        return None
    except subprocess.CalledProcessError:
        pass

    return None


class RamalamaContainerRegistry(OCI):
    def __init__(self, *args, model: str, **kwargs):
        super().__init__(*args, model=f"rlcr.io/ramalama/{model}", **kwargs)
        self._model_type = 'oci'

    def _setup_mounts_podman(self):
        model_filename = find_model_file_in_image(self.conman, self.model)

        if model_filename:
            # Mount the image and create model.file symlink using init command
            self.engine.add([
                f"--mount=type=image,src={self.model},destination={MNT_DIR},subpath=/models,rw=false",
                "--init-command",
                f"ln -sf {model_filename} {MNT_DIR}/model.file",
            ])
        else:
            # Fallback to standard OCI mounting if no model file found
            self.engine.add([f"--mount=type=image,src={self.model},destination={MNT_DIR},subpath=/models,rw=false"])

    def _setup_mounts_docker(self):
        """Setup mounts for Docker using volumes-from pattern"""
        model_filename = find_model_file_in_image(self.conman, self.model)

        data_container_name = f"ramalama-data-{self.model_name}-{self.model_tag}"

        try:
            run_cmd([self.conman, "rm", "-f", data_container_name], ignore_stderr=True)
        except subprocess.CalledProcessError:
            pass

        # Create data volume container first - volume will be mounted as /mnt in runtime container
        create_cmd = [self.conman, "create", "--name", data_container_name, "--volume", "/mnt", "busybox", "true"]
        run_cmd(create_cmd)

        # Create temp container from model image to access its files
        temp_container = f"temp-{data_container_name}"
        temp_cmd = [self.conman, "create", "--name", temp_container, self.model]
        run_cmd(temp_cmd)

        try:
            # Use busybox to copy files from temp container to data volume via docker cp
            # First, copy files from model container to a busybox container with shared volume
            busybox_cmd = [
                self.conman,
                "run",
                "--rm",
                "--volumes-from",
                data_container_name,
                "busybox",
                "sh",
                "-c",
                f"mkdir -p {MNT_DIR}",
            ]
            run_cmd(busybox_cmd)

            # Create temp dir for intermediate copy
            with tempfile.TemporaryDirectory() as temp_dir:
                # Copy from container to temp dir
                cp_cmd = [self.conman, "cp", f"{temp_container}:/models/.", temp_dir]
                run_cmd(cp_cmd)

                # Copy from temp dir to data volume using busybox
                copy_final_cmd = [
                    self.conman,
                    "run",
                    "--rm",
                    "--volumes-from",
                    data_container_name,
                    "-v",
                    f"{temp_dir}:/temp",
                    "busybox",
                    "sh",
                    "-c",
                    f"cp -r /temp/* {MNT_DIR}/ && ln -sf {model_filename} {MNT_DIR}/model.file",
                ]
                run_cmd(copy_final_cmd)

        finally:
            run_cmd([self.conman, "rm", temp_container])

        # Add volumes-from only - we'll handle the symlink in the data container setup
        self.engine.add([f"--volumes-from={data_container_name}"])

    def setup_mounts(self, args):
        if args.dryrun:
            return

        if self.engine.use_podman:
            self._setup_mounts_podman()
        else:
            self._setup_mounts_docker()

        return None
