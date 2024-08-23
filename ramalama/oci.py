import os
import re
import subprocess

from ramalama.model import Model
from ramalama.common import run_cmd, container_manager, exec_cmd


class OCI(Model):
    def __init__(self, model):
        super().__init__(model.removeprefix("oci://").removeprefix("docker://"))
        self.type = "OCI"

    def login(self, args):
        conman_args = [self.conman, "login"]
        conman_args.extend(args)
        conman_args.append(self.model)
        return exec_cmd(conman_args)

    def logout(self, registry, args):
        conman_args = [self.conman, "logout"]
        conman_args.extend(args)
        conman_args.append(self.model)
        return exec_cmd(conman_args)

    def _target_decompose(self):
        # Remove the prefix and extract target details
        try:
            registry, reference = self.model.split('/', 1)
        except:
            raise KeyError(
                f"You must specify a registry for the model in the form 'oci://registry.acme.org/ns/repo:tag', got instead: {self.model}")

        reference_dir = reference.replace(":", "/")
        return target, registry, reference, reference_dir

    def push(self, store, target):
        _, registry, _, reference_dir = self._target_decompose(self.model)
        target = re.sub(r'^oci://', '', target)

        # Validate the model exists locally
        local_model_path = os.path.join(
            store, 'models/oci', registry, reference_dir)
        if not os.path.exists(local_model_path):
            raise KeyError(
                f"Model {self.model} not found locally. Cannot push.")

        model_file = Path(local_model_path).resolve()
        try:
            # Push the model using omlmd, using cwd the model's file parent directory
            run_cmd(["omlmd", "push", target, str(model_file),
                     "--empty-metadata"], cwd=model_file.parent)
        except subprocess.CalledProcessError as e:
            perror(f"Failed to push model to OCI: {e}")
            raise e
        return local_model_path

    def pull(self, store):
        try:
            registry, reference = self.model.split('/', 1)
        except:
            registry = "docker.io"
            reference = self.model

        reference_dir = reference.replace(":", "/")
        outdir = f"{store}/repos/oci/{registry}/{reference_dir}"
        print(f"Downloading {self.model}...")
        # note: in the current way ramalama is designed, cannot do Helper(OMLMDRegistry()).pull(target, outdir) since cannot use modules/sdk, can use only cli bindings from pip installs
        run_cmd(["omlmd", "pull", self.model, "--output", outdir])
        ggufs = [file for file in os.listdir(outdir) if file.endswith('.gguf')]
        if len(ggufs) != 1:
            raise KeyError(
                f"Error: Unable to identify .gguf file in: {outdir}")

        directory = f"{store}/models/oci/{registry}/{reference_dir}"
        os.makedirs(directory, exist_ok=True)
        symlink_path = f"{directory}/{ggufs[0]}"
        relative_target_path = os.path.relpath(
            f"{outdir}/{ggufs[0]}",
            start=os.path.dirname(symlink_path)
        )
        if os.path.exists(symlink_path) and os.readlink(symlink_path) == relative_target_path:
            # Symlink is already correct, no need to update it
            return symlink_path

        run_cmd(["ln", "-sf", relative_target_path, symlink_path])

        return symlink_path
