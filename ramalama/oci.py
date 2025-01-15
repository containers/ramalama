import json
import os
import subprocess
import tempfile

import ramalama.annotations as annotations
from ramalama.model import Model, MODEL_TYPES
from ramalama.common import (
    engine_version,
    exec_cmd,
    MNT_FILE,
    perror,
    run_cmd,
)

prefix = "oci://"

ocilabeltype = "org.containers.type"
ociimage_raw = "org.containers.type=ai.image.model.raw"
ociimage_car = "org.containers.type=ai.image.model.car"


def engine_supports_manifest_attributes(engine):
    if not engine or engine == "" or engine == "docker":
        return False
    if engine == "podman" and engine_version(engine) < "5":
        return False
    return True


def list_manifests(args):
    if args.engine == "docker":
        return []

    conman_args = [
        args.engine,
        "images",
        "--filter",
        "manifest=true",
        "--format",
        '{"name":"oci://{{ .Repository }}:{{ .Tag }}","modified":"{{ .CreatedAt }}",\
        "size":"{{ .Size }}", "ID":"{{ .ID }}"},',
    ]
    output = run_cmd(conman_args, debug=args.debug).stdout.decode("utf-8").strip()
    if output == "":
        return []

    manifests = json.loads("[" + output[:-1] + "]")
    if not engine_supports_manifest_attributes(args.engine):
        return manifests

    models = []
    for manifest in manifests:
        conman_args = [
            args.engine,
            "manifest",
            "inspect",
            manifest["ID"],
        ]
        output = run_cmd(conman_args, debug=args.debug).stdout.decode("utf-8").strip()

        if output == "":
            continue
        inspect = json.loads(output)
        if 'manifests' not in inspect:
            continue
        if not inspect['manifests']:
            continue
        img = inspect['manifests'][0]
        if 'annotations' not in img:
            continue
        if annotations.AnnotationModel in img['annotations']:
            models += [
                {
                    "name": manifest["name"],
                    "modified": manifest["modified"],
                    "size": manifest["size"],
                }
            ]
    return models


def list_models(args):
    conman = args.engine
    if conman is None:
        return []

    conman_args = [
        conman,
        "images",
        "--filter",
        f"label={ocilabeltype}",
        "--format",
        '{"name":"oci://{{ .Repository }}:{{ .Tag }}","modified":"{{ .CreatedAt }}","size":"{{ .Size }}"},',
    ]
    output = run_cmd(conman_args, debug=args.debug).stdout.decode("utf-8").strip()
    if output == "":
        return []
    models = json.loads("[" + output[:-1] + "]")
    models += list_manifests(args)
    return models


class OCI(Model):
    def __init__(self, model, conman):
        super().__init__(model.removeprefix(prefix).removeprefix("docker://"))
        for t in MODEL_TYPES:
            if self.model.startswith(t + "://"):
                raise ValueError(f"{model} invalid: Only OCI Model types supported")
        self.type = "OCI"
        self.conman = conman

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
        if args.REGISTRY:
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

    def build(self, source, target, args):
        print(f"Building {target}...")
        src = os.path.realpath(source)
        contextdir = os.path.dirname(src)
        model = os.path.basename(src)
        model_name = os.path.basename(source)
        model_raw = f"""\
FROM {args.image} as builder
RUN mkdir -p /models; cd /models; ln -s {model_name} model.file

FROM scratch
COPY --from=builder /models /models
COPY {model} /models/{model_name}
LABEL {ociimage_raw}
"""
        model_car = f"""\
FROM {args.carimage}
RUN mkdir -p /models; cd /models; ln -s {model_name} model.file
COPY {model} /models/{model_name}
LABEL {ociimage_car}
"""

        containerfile = tempfile.NamedTemporaryFile(prefix='RamaLama_Containerfile_', delete=False)
        # Open the file for writing.
        with open(containerfile.name, 'w') as c:
            if args.type == "car":
                c.write(model_car)
            else:
                c.write(model_raw)
        imageid = (
            run_cmd([self.conman, "build", "--no-cache", "-q", "-f", containerfile.name, contextdir], debug=args.debug)
            .stdout.decode("utf-8")
            .strip()
        )
        return imageid

    def tag(self, imageid, target, args):
        # Tag imageid with target
        cmd_args = [
            self.conman,
            "tag",
            imageid,
            target,
        ]
        run_cmd(cmd_args, debug=args.debug)

    def _create_manifest_without_attributes(self, target, imageid, args):
        # Create manifest list for target with imageid
        cmd_args = [
            self.conman,
            "manifest",
            "create",
            target,
            imageid,
        ]
        run_cmd(cmd_args, debug=args.debug)

    def _create_manifest(self, target, imageid, args):
        if not engine_supports_manifest_attributes(args.engine):
            return self._create_manifest_without_attributes(target, imageid, args)

        # Create manifest list for target with imageid
        cmd_args = [
            self.conman,
            "manifest",
            "create",
            target,
            imageid,
        ]
        run_cmd(cmd_args, debug=args.debug)

        # Annotate manifest list
        cmd_args = [
            self.conman,
            "manifest",
            "annotate",
            "--annotation",
            f"{annotations.AnnotationModel}=true",
            "--annotation",
            f"{ocilabeltype}=''",
            "--annotation",
            f"{annotations.AnnotationTitle}=args.SOURCE",
            target,
            imageid,
        ]
        run_cmd(cmd_args, stdout=None, debug=args.debug)

    def _convert(self, source, target, args):
        print(f"Converting {source} to {target}...")
        try:
            run_cmd([self.conman, "manifest", "rm", target], ignore_stderr=True, stdout=None, debug=args.debug)
        except subprocess.CalledProcessError:
            pass
        imageid = self.build(source, target, args)
        try:
            self._create_manifest(target, imageid, args)
        except subprocess.CalledProcessError as e:
            perror(
                f"""\
Failed to create manifest for OCI {target} : {e}
Tagging build instead"""
            )
            self.tag(imageid, target, args)

    def convert(self, source, args):
        target = self.model.removeprefix(prefix)
        source = source.removeprefix(prefix)
        self._convert(source, target, args)

    def push(self, source, args):
        target = self.model.removeprefix(prefix)
        source = source.removeprefix(prefix)
        print(f"Pushing {target}...")
        conman_args = [self.conman, "push"]
        if args.authfile:
            conman_args.extend([f"--authfile={args.authfile}"])
        if str(args.tlsverify).lower() == "false":
            conman_args.extend([f"--tls-verify={args.tlsverify}"])
        conman_args.extend([target])
        if source != target:
            self._convert(source, target, args)
        try:
            run_cmd(conman_args, debug=args.debug)
        except subprocess.CalledProcessError as e:
            perror(f"Failed to push OCI {target} : {e}")
            raise e

    def pull(self, args):
        print(f"Downloading {self.model}...")
        if not args.engine:
            raise NotImplementedError("OCI images require a container engine like Podman or Docker")

        conman_args = [args.engine, "pull"]
        if str(args.tlsverify).lower() == "false":
            conman_args.extend([f"--tls-verify={args.tlsverify}"])
        if args.authfile:
            conman_args.extend([f"--authfile={args.authfile}"])
        conman_args.extend([self.model])
        run_cmd(conman_args, debug=args.debug)
        return MNT_FILE

    def _registry_reference(self):
        try:
            registry, reference = self.model.split("/", 1)
            return registry, reference
        except Exception:
            return "docker.io", self.model

    def model_path(self, args):
        registry, reference = self._registry_reference()
        reference_dir = reference.replace(":", "/")
        path = f"{args.store}/models/oci/{registry}/{reference_dir}"

        if os.path.isfile(path):
            return path

        ggufs = [file for file in os.listdir(path) if file.endswith(".gguf")]
        if len(ggufs) != 1:
            raise KeyError(f"unable to identify .gguf file in: {path}")

        return f"{path}/{ggufs[0]}"

    def remove(self, args, ignore_stderr=False):
        try:
            super().remove(args)
            return
        except FileNotFoundError:
            pass

        if self.conman is None:
            raise NotImplementedError("OCI Images require a container engine")

        try:
            conman_args = [self.conman, "manifest", "rm", self.model]
            run_cmd(conman_args, debug=args.debug, ignore_stderr=ignore_stderr)
        except subprocess.CalledProcessError:
            conman_args = [self.conman, "rmi", f"--force={args.ignore}", self.model]
            run_cmd(conman_args, debug=args.debug, ignore_stderr=ignore_stderr)

    def exists(self, args):
        try:
            model_path = self.model_path(args)
            if os.path.exists(model_path):
                return model_path
        except FileNotFoundError:
            pass

        if self.conman is None:
            return None

        conman_args = [self.conman, "image", "inspect", self.model]
        try:
            run_cmd(conman_args, debug=args.debug)
            return self.model
        except Exception:
            return None
