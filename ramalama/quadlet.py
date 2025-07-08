import os
import shlex
from typing import Optional, Tuple

from ramalama.common import MNT_DIR, RAG_DIR, get_accel_env_vars
from ramalama.file import UnitFile


class Quadlet:
    def __init__(
        self,
        model_name: str,
        model_paths: Tuple[str, str],
        chat_template_paths: Optional[Tuple[str, str]],
        args,
        exec_args,
    ):
        self.src_model_path, self.dest_model_path = model_paths
        self.src_chat_template_path, self.dest_chat_template_path = (
            chat_template_paths if chat_template_paths is not None else ("", "")
        )

        self.ai_image = model_name
        self.src_model_path = self.src_model_path.removeprefix("oci://")
        if getattr(args, "name", None):
            self.name = args.name
        else:
            self.name = model_name

        self.args = args
        self.exec_args = exec_args
        self.image = args.image
        self.rag = ""
        self.rag_name = ""
        if args.rag:
            self.rag = args.rag.removeprefix("oci://")
            self.rag_name = os.path.basename(self.rag) + "-rag"

    def kube(self) -> UnitFile:
        return kube(self.name, f"RamaLama {self.name} Kubernetes YAML - AI Model Service")

    def generate(self) -> list[UnitFile]:
        files = []

        container_file_name = f"{self.name}.container"
        print(f"Generating quadlet file: {container_file_name}")

        quadlet_file = UnitFile(container_file_name)
        quadlet_file.add("Unit", "Description", f"RamaLama {self.name} AI Model Service")
        quadlet_file.add("Unit", "After", "local-fs.target")
        quadlet_file.add("Container", "AddDevice", "-/dev/accel")
        quadlet_file.add("Container", "AddDevice", "-/dev/dri")
        quadlet_file.add("Container", "AddDevice", "-/dev/kfd")
        quadlet_file.add("Container", "Image", f"{self.image}")
        quadlet_file.add("Container", "RunInit", "true")
        quadlet_file.add("Container", "Environment", "HOME=/tmp")

        exec_cmd = shlex.join(self.exec_args)
        quadlet_file.add("Container", "Exec", f"{exec_cmd}")

        if getattr(self.args, "privileged", False):
            quadlet_file.add("Container", "PodmanArgs", "--privileged")
        else:
            quadlet_file.add("Container", "SecurityLabelDisable", "true")
            if not getattr(self.args, "nocapdrop", False):
                quadlet_file.add("Container", "DropCapability", "all")
                quadlet_file.add("Container", "NoNewPrivileges", "true")

        self._gen_chat_template_volume(quadlet_file)
        self._gen_env(quadlet_file)
        self._gen_name(quadlet_file)
        self._gen_port(quadlet_file)

        volume_files = self._gen_model_volume(quadlet_file)
        files.extend(volume_files)
        rag_files = self._gen_rag_volume(quadlet_file)
        files.extend(rag_files)

        # Start by default on boot
        quadlet_file.add("Install", "WantedBy", "multi-user.target default.target")
        files.append(quadlet_file)

        return files

    def _gen_chat_template_volume(self, quadlet_file: UnitFile):
        if os.path.exists(self.src_chat_template_path):
            quadlet_file.add(
                "Container",
                "Mount",
                f"type=bind,src={self.src_chat_template_path},target={self.dest_chat_template_path},ro,Z",
            )

    def _gen_env(self, quadlet_file: UnitFile):
        env_var_string = ""
        for k, v in get_accel_env_vars().items():
            quadlet_file.add("Container", "Environment", f"{k}={v}")
        for e in self.args.env:
            quadlet_file.add("Container", "Environment", f"{e}")
        return env_var_string

    def _gen_image(self, name, image):
        image_file_name = f"{name}.image"
        print(f"Generating quadlet file: {image_file_name} ")
        image_file = UnitFile(image_file_name)
        image_file.add("Image", "Image", f"{image}")
        return image_file

    def _gen_name(self, quadlet_file: UnitFile):
        if getattr(self.args, "name", None):
            quadlet_file.add("Container", "ContainerName", f"{self.args.name}")

    def _gen_model_volume(self, quadlet_file: UnitFile):
        files: list[UnitFile] = []

        if os.path.exists(self.src_model_path):
            quadlet_file.add(
                "Container", "Mount", f"type=bind,src={self.src_model_path},target={self.dest_model_path},ro,Z"
            )
            return files

        volume_file_name = f"{self.name}.volume"
        print(f"Generating quadlet file: {volume_file_name} ")

        volume_file = UnitFile(volume_file_name)
        volume_file.add("Volume", "Driver", "image")
        volume_file.add("Volume", "Image", f"{self.name}.image")
        files.append(volume_file)

        files.append(self._gen_image(self.name, self.ai_image))

        quadlet_file.add(
            "Container",
            "Mount",
            f"type=image,source={self.ai_image},destination={MNT_DIR},subpath=/models,readwrite=false",
        )
        return files

    def _gen_port(self, quadlet_file: UnitFile):
        if getattr(self.args, "port", "") != "":
            quadlet_file.add("Container", "PublishPort", f"{self.args.port}:{self.args.port}")

    def _gen_rag_volume(self, quadlet_file: UnitFile):
        files: list[UnitFile] = []

        if not getattr(self.args, "rag", None):
            return files

        rag_volume_file_name = f"{self.rag_name}.volume"
        print(f"Generating quadlet file: {rag_volume_file_name} ")

        volume_file = UnitFile(rag_volume_file_name)
        volume_file.add("Volume", "Driver", "image")
        volume_file.add("Volume", "Image", f"{self.rag_name}.image")
        files.append(volume_file)

        files.append(self._gen_image(self.rag_name, self.rag))

        quadlet_file.add("Container", "Mount", f"type=image,source={self.rag},destination={RAG_DIR},readwrite=false")
        return files


def kube(name, description) -> UnitFile:
    file_name = f"{name}.kube"
    print(f"Generating quadlet file: {file_name}")

    file = UnitFile(file_name)
    file.add("Unit", "Description", description)
    file.add("Unit", "After", "local-fs.target")
    file.add("Kube", "Yaml", f"{name}.yaml")
    # Start by default on boot
    file.add("Install", "WantedBy", "multi-user.target default.target")

    return file
