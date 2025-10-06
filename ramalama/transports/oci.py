import os
import subprocess
import tempfile

import ramalama.annotations as annotations
from ramalama.common import MNT_DIR, exec_cmd, perror, run_cmd
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
        self.artifact = self.is_artifact()

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
        is_raw = args.type == "raw"
        if args.type == "artifact":
            raise TypeError("artifact handling should not generate containerfiles.")
        if not is_car and not is_raw:
            raise ValueError(f"argument --type: invalid choice: '{args.type}' (choose from artifact,  car, raw)")
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

    def _rm_artifact(self, ignore) -> None:
        rm_cmd = [
            self.conman,
            "artifact",
            "rm",
            self.model,
        ]
        if ignore:
            rm_cmd.extend("--ignore")
        rm_cmd.append(self.model)

        run_cmd(
            rm_cmd,
            ignore_all=True,
        )

    def _add_artifact(self, create, name, path, file_name) -> None:
        cmd = [
            self.conman,
            "artifact",
            "add",
            "--annotation",
            f"org.opencontainers.image.title={file_name}",
        ]
        if create:
            cmd.extend(["--replace", "--type", annotations.ArtifactTypeModelManifest])
        else:
            cmd.extend(["--append"])

        cmd.extend([self.model, path])
        run_cmd(
            cmd,
            ignore_stderr=True,
        )

    def _create_artifact(self, source_model, target, args) -> None:
        model_name = source_model.model_name
        ref_file = source_model.model_store.get_ref_file(source_model.model_tag)
        name = ref_file.model_files[0].name if ref_file.model_files else model_name
        create = True
        for file in ref_file.files:
            blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
            self._add_artifact(create, name, blob_file_path, file.name)
            create = False

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
        try:
            run_cmd([self.conman, "manifest", "rm", self.model], ignore_stderr=True, stdout=None)
        except subprocess.CalledProcessError:
            pass
        if args.type == "artifact":
            perror(f"Creating Artifact {self.model} ...")
            self._create_artifact(source_model, self.model, args)
            return

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

        conman_args = [self.conman, "push"]
        type = "image"
        if args.type == "artifact":
            type = args.type
            conman_args.insert(1, "artifact")

        perror(f"Pushing {type} {self.model} ...")
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
            try:
                if args.type != "artifact":
                    perror(f"Pushing artifact {self.model} ...")
                    conman_args.insert(1, "artifact")
                    run_cmd(conman_args)
            except subprocess.CalledProcessError:
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
            try:
                conman_args = [self.conman, "rmi", f"--force={args.ignore}", self.model]
                run_cmd(conman_args, ignore_stderr=self.ignore_stderr)
            except subprocess.CalledProcessError:
                self._rm_artifact(args.ignore)

    def exists(self) -> bool:
        if self.conman is None:
            return False

        conman_args = [self.conman, "image", "inspect", self.model]
        try:
            run_cmd(conman_args, ignore_stderr=self.ignore_stderr)
            return True
        except Exception:
            conman_args = [self.conman, "artifact", "inspect", self.model]
            try:
                run_cmd(conman_args, ignore_stderr=self.ignore_stderr)
                return True
            except Exception:
                return False

    def _inspect(
        self,
        show_all: bool = False,
        show_all_metadata: bool = False,
        get_field: str = "",
        as_json: bool = False,
        dryrun: bool = False,
    ) -> (str, str):
        out = super().get_inspect(show_all, show_all_metadata, get_field, dryrun)
        conman_args = [self.conman, "image", "inspect", self.model]
        type = "Image"
        try:
            out += run_cmd(conman_args, ignore_stderr=True).stdout.decode('utf-8').strip()
        except Exception as e:
            conman_args = [self.conman, "artifact", "inspect", self.model]
            try:
                out += run_cmd(conman_args, ignore_stderr=True).stdout.decode('utf-8').strip()
                type = "Artifact"
            except Exception:
                raise e

        return out, type

    def artifact_name(self) -> str:
        conman_args = [
            self.conman,
            "artifact",
            "inspect",
            "--format",
            '{{index  .Manifest.Annotations "org.opencontainers.image.title" }}',
            self.model,
        ]

        return run_cmd(conman_args, ignore_stderr=True).stdout.decode('utf-8').strip()

    def inspect(
        self,
        show_all: bool = False,
        show_all_metadata: bool = False,
        get_field: str = "",
        as_json: bool = False,
        dryrun: bool = False,
    ) -> None:
        out, type = self._inspect(show_all, show_all_metadata, get_field, as_json, dryrun)
        print(f"OCI {type}")
        print(out)

    def is_artifact(self) -> bool:
        _, type = self._inspect()
        return type == "Artifact"

    def mount_cmd(self):
        if self.artifact:
            return f"--mount=type=artifact,src={self.model},destination={MNT_DIR}"
        else:
            return f"--mount=type=image,src={self.model},destination={MNT_DIR},subpath=/models,rw=false"
