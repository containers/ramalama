import os
from typing import Optional, Tuple

from ramalama.common import MNT_DIR, RAG_DIR, genname, get_accel_env_vars
from ramalama.file import PlainFile
from ramalama.version import version


class Kube:
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

        self.src_model_path = self.src_model_path.removeprefix("oci://")

        self.ai_image = model_name
        if getattr(args, "name", None):
            self.name = args.name
        else:
            self.name = genname()

        self.args = args
        self.exec_args = exec_args
        self.image = args.image

    def _gen_volumes(self):
        mounts = f"""\
        volumeMounts:
        - mountPath: {MNT_DIR}
          subPath: /models
          name: model"""

        volumes = """
      volumes:"""

        if os.path.exists(self.src_model_path):
            volumes += self._gen_path_volume()
        else:
            volumes += self._gen_oci_volume()

        if self.args.rag:
            m, v = self._gen_rag_volume()
            mounts += m
            volumes += v

        if os.path.exists(self.src_chat_template_path):
            volumes += self._gen_chat_template_volume()

        m, v = self._gen_devices()
        mounts += m
        volumes += v
        return mounts + volumes

    def _gen_devices(self):
        mounts = ""
        volumes = ""
        for dev in ["dri", "kfd"]:
            if os.path.exists("/dev/" + dev):
                mounts += f"""
        - mountPath: /dev/{dev}
          name: {dev}"""
                volumes += f"""
      - hostPath:
          path: /dev/{dev}
        name: {dev}"""
        return mounts, volumes

    def _gen_path_volume(self):
        return f"""
      - hostPath:
          path: {self.src_model_path}
        name: model"""

    def _gen_oci_volume(self):
        return f"""
      - image:
          reference: {self.ai_image}
          pullPolicy: IfNotPresent
        name: model"""

    def _gen_rag_volume(self):
        mounts = f"""
        - mountPath: {RAG_DIR}
          name: rag"""

        volumes = f"""
      - image:
          reference: {self.args.rag}
          pullPolicy: IfNotPresent
        name: rag"""

        return mounts, volumes

    def _gen_chat_template_volume(self):
        return f"""
      - hostPath:
          path: {self.src_chat_template_path}
        name: chat_template"""

    def __gen_ports(self):
        if not hasattr(self.args, "port"):
            return ""

        p = self.args.port.split(":", 2)
        ports = f"""\
        ports:
        - containerPort: {p[0]}"""
        if len(p) > 1:
            ports += f"""
          hostPort: {p[1]}"""

        return ports

    @staticmethod
    def __gen_env_vars():
        env_vars = get_accel_env_vars()

        if not env_vars:
            return ""

        env_spec = """\
        env:"""

        for k, v in env_vars.items():
            env_spec += f"""
        - name: {k}
          value: {v}"""

        return env_spec

    def generate(self) -> PlainFile:
        env_string = self.__gen_env_vars()
        port_string = self.__gen_ports()
        volume_string = self._gen_volumes()
        _version = version()

        content = f"""\
# Save the output of this file and use kubectl create -f to import
# it into Kubernetes.
#
# Created with ramalama-{_version}
apiVersion: v1
kind: Deployment
metadata:
  name: {self.name}
  labels:
    app: {self.name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {self.name}
  template:
    metadata:
      labels:
        app: {self.name}
    spec:
      containers:
      - name: {self.name}
        image: {self.image}
        command: ["{self.exec_args[0]}"]
        args: {self.exec_args[1:]}
{env_string}
{port_string}
{volume_string}"""

        return genfile(self.name, content)


def genfile(name, content) -> PlainFile:
    file_name = f"{name}.yaml"
    print(f"Generating Kubernetes YAML file: {file_name}")

    file = PlainFile(file_name)
    file.content = content
    return file
