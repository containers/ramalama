import os
import subprocess
import sys

from ramalama.model import Model
from ramalama.common import run_cmd, exec_cmd, perror, available


class OCI(Model):
    def __init__(self, model):
        super().__init__(model.removeprefix("oci://").removeprefix("docker://"))
        self.type = "OCI"
        if available("omlmd"):
            self.omlmd = "omlmd"
        else:
            for i in sys.path:
                self.omlmd = f"{i}/../../../bin/omlmd"
                if os.path.exists(self.omlmd):
                    break
            raise """\
OCI models requires the omlmd module.
This module can be installed via PyPi tools like pip, pip3, pipx or via
distribution package managers like dnf or apt. Example:
pip install omlmd
"""

    def login(self, args):
        conman_args = [self.conman, "login"]
        if args.username:
            conman_args.extend(["--username", args.username])
        if args.password:
            conman_args.extend(["--password", args.password])
        if args.passwordstdin:
            conman_args.append("--password-stdin")
        conman_args.append(args.TRANSPORT)
        return exec_cmd(conman_args)

    def logout(self, args):
        conman_args = [self.conman, "logout"]
        conman_args.append(self.model)
        return exec_cmd(conman_args)

    def _target_decompose(self, model):
        # Remove the prefix and extract target details
        try:
            registry, reference = model.split("/", 1)
        except Exception:
            raise KeyError(
                f"You must specify a registry for the model in the form "
                f"'oci://registry.acme.org/ns/repo:tag', got instead: {self.model}"
            )

        reference_dir = reference.replace(":", "/")
        return registry, reference, reference_dir

    def push(self, source, args):
        target = args.TARGET.strip("oci://")
        tregistry, _, treference_dir = self._target_decompose(target)

        try:
            # Push the model using omlmd, using cwd the model's file parent directory

            run_cmd([self.omlmd, "push", target, source, "--empty-metadata"])
        except subprocess.CalledProcessError as e:
            perror(f"Failed to push model to OCI: {e}")
            raise e

    def pull(self, args):
        try:
            registry, reference = self.model.split("/", 1)
        except Exception:
            registry = "docker.io"
            reference = self.model

        reference_dir = reference.replace(":", "/")
        outdir = f"{args.store}/repos/oci/{registry}/{reference_dir}"
        print(f"Downloading {self.model}...")
        # note: in the current way RamaLama is designed, cannot do Helper(OMLMDRegistry()).pull(target, outdir)
        # since cannot use modules/sdk, can use only cli bindings from pip installs
        run_cmd([self.omlmd, "pull", self.model, "--output", outdir])
        ggufs = [file for file in os.listdir(outdir) if file.endswith(".gguf")]
        if len(ggufs) != 1:
            raise KeyError(f"unable to identify .gguf file in: {outdir}")

        directory = f"{args.store}/models/oci/{registry}/{reference_dir}"
        os.makedirs(directory, exist_ok=True)
        symlink_path = f"{directory}/{ggufs[0]}"
        relative_target_path = os.path.relpath(f"{outdir}/{ggufs[0]}", start=os.path.dirname(symlink_path))
        if os.path.exists(symlink_path) and os.readlink(symlink_path) == relative_target_path:
            # Symlink is already correct, no need to update it
            return symlink_path

        run_cmd(["ln", "-sf", relative_target_path, symlink_path])

        return symlink_path

    def symlink_path(self, args):
        registry, reference = self.model.split("/", 1)
        reference_dir = reference.replace(":", "/")
        path = f"{args.store}/models/oci/{registry}/{reference_dir}"

        if os.path.isfile(path):
            return path

        ggufs = [file for file in os.listdir(path) if file.endswith(".gguf")]
        if len(ggufs) != 1:
            raise KeyError(f"unable to identify .gguf file in: {path}")

        return f"{path}/{ggufs[0]}"
