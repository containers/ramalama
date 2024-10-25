import os
import subprocess
import sys
import tempfile

from ramalama.model import Model
from ramalama.common import run_cmd, exec_cmd, perror, available

prefix = "oci://"


class OCI(Model):
    def __init__(self, model, conman):
        super().__init__(model.removeprefix(prefix).removeprefix("docker://"))
        self.type = "OCI"
        self.conman = conman
        if available("omlmd"):
            self.omlmd = "omlmd"
        else:
            for i in sys.path:
                self.omlmd = f"{i}/../../../bin/omlmd"
                if os.path.exists(self.omlmd):
                    break
            raise NotImplementedError(
                """\
OCI models requires the omlmd module.
This module can be installed via PyPi tools like pip, pip3, pipx or via
distribution package managers like dnf or apt. Example:
pip install omlmd
"""
            )

    def login(self, args):
        conman_args = [self.conman, "login"]
        if str(args.tlsverify).lower() == "false":
            conman_args.extend([f"--tls-verify={args.tlsverify}"])
        if args.authfile:
            conman_args.extend([f"--authfile={args.authfile}"])
        if args.username:
            conman_args.extend([f"--username={args.username}"])
        if args.password:
            conman_args.extend([f"--password={args.password}"])
        if args.passwordstdin:
            conman_args.append("--password-stdin")
        conman_args.append(args.REGISTRY.removeprefix(prefix))
        return exec_cmd(conman_args, debug=args.debug)

    def logout(self, args):
        conman_args = [self.conman, "logout"]
        conman_args.append(self.model)
        return exec_cmd(conman_args, debug=args.debug)

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

    def _build(self, source, target, args):
        print(f"Building {target}...")
        src = os.path.realpath(source)
        model_name = os.path.basename(source)
        contextdir = os.path.dirname(src)
        model = os.path.basename(src)
        containerfile = tempfile.NamedTemporaryFile(prefix='RamaLama_Containerfile_', delete=False)
        # Open the file for writing.
        with open(containerfile.name, 'w') as c:
            c.write(
                f"""\
FROM {args.image} as builder
RUN mkdir -p /run/model; cd /run/model; ln -s {model_name} model.file

FROM scratch
COPY --from=builder /run/model /
COPY {model} /{model_name}
"""
            )
        run_cmd(
            [self.conman, "build", "-t", target, "-f", containerfile.name, contextdir], stdout=None, debug=args.debug
        )

    def push(self, source, args):
        target = self.model.removeprefix(prefix)
        source = source.removeprefix(prefix)
        if source != target:
            try:
                self._build(source, target, args)
                try:
                    print(f"Pushing {target}...")
                    run_cmd([self.conman, "push", target])
                    return
                except subprocess.CalledProcessError as e:
                    perror(f"Failed to push {source} model to OCI: {e}")
                    raise e
            except subprocess.CalledProcessError:
                pass
        try:
            print(f"Pushing {target}...")
            run_cmd([self.conman, "push", source, target])
        except subprocess.CalledProcessError as e:
            perror(f"Failed to push {source} model to OCI {target}: {e}")
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
