import copy
import json
import os
import shutil
import subprocess
import tempfile
from textwrap import dedent
from typing import Tuple

import ramalama.annotations as annotations
from ramalama.common import MNT_DIR, engine_version, exec_cmd, perror, run_cmd, set_accel_env_vars
from ramalama.engine import BuildEngine, Engine, dry_run
from ramalama.oci_tools import engine_supports_manifest_attributes
from ramalama.transports.base import NoRefFileFound, Transport

prefix = "oci://"

ociimage_raw = "org.containers.type=ai.image.model.raw"
ociimage_car = "org.containers.type=ai.image.model.car"


class OCI(Transport):
    type = "OCI"

    def __init__(self, model: str, model_store_path: str, conman: str, ignore_stderr: bool = False):
        super().__init__(model, model_store_path)

        if ":" not in self.model:
            self.model = f"{self.model}:latest"

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

    def _convert_to_gguf(self, outdir, source_model, args):
        with tempfile.TemporaryDirectory(prefix="RamaLama_convert_src_") as srcdir:
            ref_file = source_model.model_store.get_ref_file(source_model.model_tag)
            for file in ref_file.files:
                blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
                shutil.copyfile(blob_file_path, os.path.join(srcdir, file.name))
            engine = Engine(args)
            engine.add_volume(srcdir, "/model")
            engine.add_volume(outdir.name, "/output", opts="rw")
            args.model = source_model
            engine.add_args(args.rag_image)
            # import here to avoid circular references
            from ramalama.command.factory import assemble_command

            engine.add_args(*assemble_command(args))
            if args.dryrun:
                engine.dryrun()
            else:
                engine.run()
        return self._quantize(source_model, args, outdir.name)

    def _quantize(self, source_model, args, model_dir):
        engine = Engine(args)
        engine.add_volume(model_dir, "/model", opts="rw")
        engine.add_args(args.image)
        # import here to avoid circular references
        from ramalama.command.factory import assemble_command

        args = copy.copy(args)
        args.subcommand = "quantize"
        engine.add_args(*assemble_command(args))
        if args.dryrun:
            engine.dryrun()
        else:
            engine.run()
        return f"{source_model.model_name}-{args.gguf}.gguf"

    def build_image(self, cfile, contextdir, args):
        if args.type == "car":
            parent = args.carimage
            label = ociimage_car
        else:
            parent = "scratch"
            label = ociimage_raw
        footer = dedent(
            f"""
            FROM {parent}
            LABEL {label}
            COPY --from=build /data/ /
            """
        ).strip()
        full_cfile = cfile + "\n\n" + footer + "\n"
        if args.debug:
            perror(f"Containerfile: \n{full_cfile}")
        engine = BuildEngine(args)
        return engine.build_containerfile(full_cfile, contextdir)

    def _gguf_containerfile(self, model_file_name, args):
        return dedent(
            f"""
            FROM {args.carimage} AS build
            COPY {model_file_name} /data/models/{model_file_name}
            RUN ln -s {model_file_name} /data/models/model.file
            """
        ).strip()

    def _generate_containerfile(self, source_model, args):
        # Generate the containerfile content
        # Keep this in sync with docs/ramalama-oci.5.md !
        is_car = args.type == "car"
        is_raw = args.type == "raw"
        if args.type == "artifact":
            raise TypeError("artifact handling should not generate containerfiles.")
        if not is_car and not is_raw:
            raise ValueError(f"argument --type: invalid choice: '{args.type}' (choose from artifact,  car, raw)")
        content = [f"FROM {args.carimage} AS build"]
        model_name = source_model.model_name
        ref_file = source_model.model_store.get_ref_file(source_model.model_tag)

        for file in ref_file.files:
            blob_file_path = source_model.model_store.get_blob_file_path(file.hash)
            blob_file_path = os.path.relpath(blob_file_path, source_model.model_store.blobs_directory)
            content.append(f"COPY {blob_file_path} /data/models/{model_name}/{file.name}")
        name = ref_file.model_files[0].name if ref_file.model_files else model_name
        content.append(f"RUN ln -s {model_name}/{name} /data/models/model.file")

        return "\n".join(content)

    def build(self, source_model, args):
        gguf_dir = None
        if getattr(args, "gguf", None):
            perror("Converting to gguf ...")
            gguf_dir = tempfile.TemporaryDirectory(prefix="RamaLama_convert_", delete=False)
            contextdir = gguf_dir.name
            model_file_name = self._convert_to_gguf(gguf_dir, source_model, args)
            content = self._gguf_containerfile(model_file_name, args)
        else:
            # use blobs directory as context since paths in Containerfile are relative to it
            contextdir = source_model.model_store.blobs_directory
            content = self._generate_containerfile(source_model, args)
        try:
            return self.build_image(content, contextdir, args)
        finally:
            if gguf_dir:
                gguf_dir.cleanup()

    def tag(self, imageid, target, args):
        # Tag imageid with target
        cmd_args = [
            self.conman,
            "tag",
            imageid,
            target,
        ]
        if args.dryrun:
            dry_run(cmd_args)
        else:
            run_cmd(cmd_args)

    def _rm_artifact(self, ignore):
        rm_cmd = [
            self.conman,
            "artifact",
            "rm",
        ]
        if ignore:
            rm_cmd.append("--ignore")
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
            if self.conman == "podman" and engine_version("podman") >= "5.7.0":
                cmd.append("--replace")
            cmd.extend(["--type", annotations.ArtifactTypeModelManifest])
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
        if args.dryrun:
            dry_run(cmd_args)
        else:
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
        if args.dryrun:
            dry_run(cmd_args)
        else:
            run_cmd(cmd_args)

        # Annotate manifest list
        cmd_args = [
            self.conman,
            "manifest",
            "annotate",
            "--annotation",
            f"{annotations.AnnotationModel}=true",
            "--annotation",
            ociimage_car if args.type == "car" else ociimage_raw,
            "--annotation",
            f"{annotations.AnnotationTitle}={args.SOURCE}",
            target,
            imageid,
        ]
        if args.dryrun:
            dry_run(cmd_args)
        else:
            run_cmd(cmd_args, stdout=None)

    def _convert(self, source_model, args):
        set_accel_env_vars()
        perror(
            f"Converting {source_model.model_store.model_name} ({source_model.model_store.model_type}) to "
            f"{self.model_store.model_name} ({self.model_store.model_type}) ..."
        )
        try:
            rm_cmd = [self.conman, "manifest", "rm", self.model]
            if args.dryrun:
                dry_run(rm_cmd)
            else:
                run_cmd(rm_cmd, ignore_stderr=True, stdout=None)
        except subprocess.CalledProcessError:
            pass
        if args.type == "artifact":
            perror(f"Creating Artifact {self.model} ...")
            self._create_artifact(source_model, self.model, args)
            return

        perror(f"Building {self.model} ...")
        imageid = self.build(source_model, args)
        if args.dryrun:
            imageid = "a1b2c3d4e5f6"
        try:
            self._create_manifest(self.model, imageid, args)
        except subprocess.CalledProcessError as e:
            perror(
                f"""\
Failed to create manifest for OCI {self.model} : {e}
Tagging build instead
                """
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
            run_cmd(conman_args, ignore_stderr=self.ignore_stderr)
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

    def remove(self, args) -> bool:
        if self.conman is None:
            raise NotImplementedError("OCI Images require a container engine")

        try:
            conman_args = [self.conman, "manifest", "rm", self.model]
            run_cmd(conman_args, ignore_stderr=True)
        except subprocess.CalledProcessError:
            try:
                conman_args = [self.conman, "rmi", f"--force={args.ignore}", self.model]
                run_cmd(conman_args, ignore_stderr=True)
            except subprocess.CalledProcessError:
                try:
                    self._rm_artifact(args.ignore)
                except subprocess.CalledProcessError:
                    raise KeyError(f"Model '{self.model}' not found")
        return True

    def exists(self) -> bool:
        if self.conman is None:
            return False

        conman_args = [self.conman, "image", "inspect", self.model]
        try:
            run_cmd(conman_args, ignore_stderr=True)
            return True
        except Exception:
            conman_args = [self.conman, "artifact", "inspect", self.model]
            try:
                run_cmd(conman_args, ignore_stderr=True)
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
    ) -> Tuple[str, str]:
        out = super().inspect(show_all, show_all_metadata, get_field, dryrun, as_json)
        if as_json:
            out_data = json.loads(out)
        else:
            out_data = out
        conman_args = [self.conman, "image", "inspect", self.model]
        oci_type = "Image"
        try:
            inspect_output = run_cmd(conman_args, ignore_stderr=True).stdout.decode('utf-8').strip()
            # podman image inspect returns a list of objects
            inspect_data = json.loads(inspect_output)
            if as_json and inspect_data:
                out_data.update(inspect_data[0])
        except Exception as e:
            conman_args = [self.conman, "artifact", "inspect", self.model]
            try:
                inspect_output = run_cmd(conman_args, ignore_stderr=True).stdout.decode('utf-8').strip()

                # podman artifact inspect returns a single object
                if as_json:
                    out_data.update(json.loads(inspect_output))
                oci_type = "Artifact"
            except Exception:
                raise e

        if as_json:
            return json.dumps(out_data), oci_type
        return out_data, oci_type

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
        if as_json:
            print(out)
        else:
            print(f"{out}   Type: {type}")

    def is_artifact(self) -> bool:
        try:
            _, oci_type = self._inspect()
        except (NoRefFileFound, subprocess.CalledProcessError):
            return False
        return oci_type == "Artifact"

    def mount_cmd(self):
        if self.artifact:
            return f"--mount=type=artifact,src={self.model},destination={MNT_DIR}"
        else:
            return f"--mount=type=image,src={self.model},destination={MNT_DIR},subpath=/models,rw=false"
