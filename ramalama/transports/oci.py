import copy
import os
import shutil
import subprocess
import tempfile
from textwrap import dedent

import ramalama.annotations as annotations
from ramalama.common import exec_cmd, perror, run_cmd, set_accel_env_vars
from ramalama.engine import BuildEngine, Engine, dry_run
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
