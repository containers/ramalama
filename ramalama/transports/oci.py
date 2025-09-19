import os
import subprocess
import tempfile

import ramalama.annotations as annotations
from ramalama.common import exec_cmd, perror, run_cmd
from ramalama.oci_tools import engine_supports_manifest_attributes
from ramalama.transports.base import Transport

prefix = "oci://"

ociimage_raw = "org.containers.type=ai.image.model.raw"
ociimage_car = "org.containers.type=ai.image.model.car"


class OCI(Transport):
    type = "OCI"

    def __init__(self, model: str, model_store_path: str, conman: str, ignore_stderr: bool = False):
        super().__init__(model, model_store_path)

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
            content += f"FROM {args.carimage} AS builder\n"

        if has_gguf:
            content += (
                f"RUN mkdir -p /models/{model_name}; cd /models; ln -s {model_name}-{args.gguf}.gguf model.file\n"
            )
            for file in ref_file.files:
                blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
                blob_file_path = os.path.relpath(blob_file_path, source_model.model_store.blobs_directory)
                content += f"COPY {blob_file_path} /models/{model_name}/{file.name}\n"
            content += f"""
RUN convert_hf_to_gguf.py --outfile /{model_name}-f16.gguf /models/{model_name}
RUN llama-quantize /{model_name}-f16.gguf /models/{model_name}-{args.gguf}.gguf {args.gguf}
RUN ln -s /models/{model_name}-{args.gguf}.gguf model.file
RUN rm -rf /{model_name}-f16.gguf /models/{model_name}
"""
        else:
            name = ref_file.model_files[0].name if ref_file.model_files else model_name
            content += f"""RUN mkdir -p /models; cd /models; ln -s {model_name}/{name} model.file\n"""

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
                    blob_file_path = os.path.relpath(blob_file_path, source_model.model_store.blobs_directory)
                    content += f"COPY {blob_file_path} /models/{model_name}/{file.name}\n"
        elif not has_gguf:
            for file in ref_file.files:
                blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
                blob_file_path = os.path.relpath(blob_file_path, source_model.model_store.blobs_directory)
                content += f"COPY {blob_file_path} /models/{model_name}/{file.name}\n"

        content += f"LABEL {ociimage_car if is_car else ociimage_raw}\n"

        return content

    def build(self, source_model, args):
        # use blobs directory as context since paths in Containerfile are relative to it
        contextdir = source_model.model_store.blobs_directory
        content = self._generate_containerfile(source_model, args)
        if args.debug:
            perror(f"Containerfile: \n{content}")
        containerfile = tempfile.NamedTemporaryFile(prefix='RamaLama_Containerfile_', delete=False)

        # Open the file for writing.
        with open(containerfile.name, 'w') as c:
            c.write(content)
            c.flush()

        # ensure base image is available
        run_cmd([self.conman, "pull", args.carimage])

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
            "org.containers.type=''",
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
