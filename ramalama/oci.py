import json
import os
import subprocess
import tempfile
from datetime import datetime

import ramalama.annotations as annotations
from ramalama.arg_types import EngineArgType
from ramalama.common import engine_version, exec_cmd, perror, run_cmd
from ramalama.model import Model

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


def list_manifests(args: EngineArgType):
    if args.engine == "docker":
        return []

    conman_args = [
        args.engine,
        "images",
        "--filter",
        "manifest=true",
        "--format",
        (
            '{"name":"oci://{{ .Repository }}:{{ .Tag }}","modified":"{{ .CreatedAt }}",        "size":{{ .VirtualSize'
            ' }}, "ID":"{{ .ID }}"},'
        ),
    ]
    output = run_cmd(conman_args).stdout.decode("utf-8").strip()
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
        output = run_cmd(conman_args).stdout.decode("utf-8").strip()

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


def list_models(args: EngineArgType):
    conman = args.engine
    if conman is None:
        return []

    # if engine is docker, size will be retrieved from the inspect command later
    # if engine is podman use "size":{{ .VirtualSize }}
    formatLine = '{"name":"oci://{{ .Repository }}:{{ .Tag }}","modified":"{{ .CreatedAt }}"'
    if conman == "podman":
        formatLine += ',"size":{{ .VirtualSize }}},'
    else:
        formatLine += ',"id":"{{ .ID }}"},'

    conman_args = [
        conman,
        "images",
        "--filter",
        f"label={ocilabeltype}",
        "--format",
        formatLine,
    ]
    output = run_cmd(conman_args).stdout.decode("utf-8").strip()
    if output == "":
        return []

    models = json.loads("[" + output[:-1] + "]")
    # exclude dangling images having no tag (i.e. <none>:<none>)
    models = [model for model in models if model["name"] != "oci://<none>:<none>"]

    # Grab the size from the inspect command
    if conman == "docker":
        # grab the size from the inspect command
        for model in models:
            conman_args = [conman, "image", "inspect", model["id"], "--format", "{{.Size}}"]
            output = run_cmd(conman_args).stdout.decode("utf-8").strip()
            # convert the number value from the string output
            model["size"] = int(output)
            # drop the id from the model
            del model["id"]

    models += list_manifests(args)
    for model in models:
        # Convert to ISO 8601 format
        parsed_date = datetime.fromisoformat(
            model["modified"].replace(" UTC", "").replace("+0000", "+00:00").replace(" ", "T")
        )
        model["modified"] = parsed_date.isoformat()

    return models


class OCI(Model):
    def __init__(self, model, model_store_path, conman, ignore_stderr=False):
        super().__init__(model, model_store_path)

        self.type = "OCI"
        if not conman:
            raise ValueError("RamaLama OCI Images requires a container engine")

        self.conman = conman
        self.ignore_stderr = ignore_stderr

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
                "You must specify a registry for the model in the form "
                f"'oci://registry.acme.org/ns/repo:tag', got instead: {self.model}"
            )

        reference_dir = reference.replace(":", "/")
        return registry, reference, reference_dir

    def _generate_containerfile(self, source_model, args):
        # Generate the containerfile content
        # Keep this in sync with docs/ramalama-oci.5.md !
        is_car = args.type == "car"
        has_gguf = getattr(args, 'gguf', None) is not None
        content = ""

        model_name = source_model.model_name
        ref_file = source_model.model_store.get_ref_file(source_model.model_tag)

        if is_car:
            content += f"FROM {args.carimage}\n"
        else:
            content += f"FROM {args.carimage} as builder\n"

        if has_gguf:
            content += (
                f"RUN mkdir -p /models/{model_name}; cd /models; ln -s {model_name}-{args.gguf}.gguf model.file\n"
            )
            for file in ref_file.files:
                blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
                content += f"COPY {blob_file_path} /models/{model_name}/{file.name}\n"
            content += f"""
RUN convert_hf_to_gguf.py --outfile /{model_name}-f16.gguf /models/{model_name}
RUN llama-quantize /{model_name}-f16.gguf /models/{model_name}-{args.gguf}.gguf {args.gguf}
RUN ln -s /models/{model_name}-{args.gguf}.gguf model.file
RUN rm -rf /{model_name}-f16.gguf /models/{model_name}
"""
        else:
            content += f"RUN mkdir -p /models; cd /models; ln -s {model_name} model.file\n"

        if not is_car:
            content += "\nFROM scratch\n"
            content += "COPY --from=builder /models /models\n"

            if has_gguf:
                content += (
                    f"COPY --from=builder /models/{model_name}-{args.gguf}.gguf /models/{model_name}-{args.gguf}.gguf\n"
                )
            else:
                for file in ref_file.files:
                    blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
                    content += f"COPY {blob_file_path} /models/{model_name}/{file.name}\n"
        elif not has_gguf:
            for file in ref_file.files:
                blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
                content += f"COPY {blob_file_path} /models/{model_name}/{file.name}\n"

        content += f"LABEL {ociimage_car if is_car else ociimage_raw}\n"

        return content

    def build(self, source_model, args):
        # use topmost directory here since the paths provided by model store are absolute
        contextdir = "/"
        content = self._generate_containerfile(source_model, args)
        if args.debug:
            perror(f"Containerfile: \n{content}")
        containerfile = tempfile.NamedTemporaryFile(prefix='RamaLama_Containerfile_', delete=False)

        # Open the file for writing.
        with open(containerfile.name, 'w') as c:
            c.write(content)
            c.flush()

        build_cmd = [
            self.conman,
            "build",
            "--no-cache",
            "--network=none",
            "-q",
            "-f",
            containerfile.name,
        ]
        if os.path.basename(self.conman) == "podman":
            build_cmd += ["--layers=false"]
        build_cmd += [contextdir]
        imageid = (
            run_cmd(
                build_cmd,
            )
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
        run_cmd(cmd_args)

    def _create_manifest_without_attributes(self, target, imageid, args):
        # Create manifest list for target with imageid
        cmd_args = [
            self.conman,
            "manifest",
            "create",
            target,
            imageid,
        ]
        run_cmd(cmd_args)

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
        run_cmd(cmd_args)

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
        run_cmd(cmd_args, stdout=None)

    def _convert(self, source_model, args):
        perror(f"Converting {source_model.model_store.base_path} to {self.model_store.base_path} ...")
        try:
            run_cmd([self.conman, "manifest", "rm", self.model], ignore_stderr=True, stdout=None)
        except subprocess.CalledProcessError:
            pass
        perror(f"Building {self.model} ...")
        imageid = self.build(source_model, args)
        try:
            self._create_manifest(self.model, imageid, args)
        except subprocess.CalledProcessError as e:
            perror(
                f"""\
Failed to create manifest for OCI {self.model} : {e}
Tagging build instead"""
            )
            self.tag(imageid, self.model, args)

    def convert(self, source_model, args):
        self._convert(source_model, args)

    def push(self, source_model, args):
        target = self.model
        source = source_model.model

        perror(f"Pushing {self.model} ...")
        conman_args = [self.conman, "push"]
        if args.authfile:
            conman_args.extend([f"--authfile={args.authfile}"])
        if str(args.tlsverify).lower() == "false":
            conman_args.extend([f"--tls-verify={args.tlsverify}"])
        conman_args.extend([target])
        if source != target:
            self._convert(source_model, args)
        try:
            run_cmd(conman_args)
        except subprocess.CalledProcessError as e:
            perror(f"Failed to push OCI {target} : {e}")
            raise e

    def pull(self, args):
        if not args.engine:
            raise NotImplementedError("OCI images require a container engine like Podman or Docker")

        conman_args = [args.engine, "pull"]
        if args.quiet:
            conman_args.extend(['--quiet'])
        else:
            # Write message to stderr
            perror(f"Downloading {self.model} ...")
        if str(args.tlsverify).lower() == "false":
            conman_args.extend([f"--tls-verify={args.tlsverify}"])
        if args.authfile:
            conman_args.extend([f"--authfile={args.authfile}"])
        conman_args.extend([self.model])
        run_cmd(conman_args, ignore_stderr=self.ignore_stderr)

    def remove(self, args, ignore_stderr=False):
        if self.conman is None:
            raise NotImplementedError("OCI Images require a container engine")

        try:
            conman_args = [self.conman, "manifest", "rm", self.model]
            run_cmd(conman_args, ignore_stderr=self.ignore_stderr)
        except subprocess.CalledProcessError:
            conman_args = [self.conman, "rmi", f"--force={args.ignore}", self.model]
            run_cmd(conman_args, ignore_stderr=self.ignore_stderr)

    def exists(self) -> bool:
        if self.conman is None:
            return False

        conman_args = [self.conman, "image", "inspect", self.model]
        try:
            run_cmd(conman_args, ignore_stderr=self.ignore_stderr)
            return True
        except Exception:
            return False
