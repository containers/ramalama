import os
import tempfile

import ramalama.kube as kube
import ramalama.quadlet as quadlet
from ramalama.common import (
    exec_cmd,
    genname,
    tagged_image,
)
from ramalama.engine import add_labels
from ramalama.model import compute_serving_port
from ramalama.model_factory import ModelFactory, New


class Stack:
    """Stack class"""

    type = "Stack"

    def __init__(self, args):
        self.args = args
        self.name = args.name if hasattr(args, "name") and args.name else genname()
        if os.path.basename(args.engine) != "podman":
            raise ValueError("llama-stack requires use of the Podman container engine")
        self.host = "127.0.0.1"
        model = ModelFactory(args.MODEL, args)
        self.model = model.prune_model_input()
        model = New(args.MODEL, args)
        self.model_type = model.type
        self.model_path = model.get_model_path(args)
        self.model_port = str(int(self.args.port) + 1)
        self.stack_image = tagged_image("quay.io/ramalama/llama-stack")
        self.labels = ""

    def add_label(self, label):
        cleanlabel = label.replace("=", ": ", 1)
        self.labels = f"{self.labels}\n        {cleanlabel}"

    def generate(self):
        add_labels(self.args, self.add_label)
        volume_mounts = """
        - mountPath: /mnt/models/model.file
          name: model
        - mountPath: /dev/dri
          name: dri"""

        if self.model_type == "OCI":
            volume_mounts = """
        - mountPath: /mnt/models
          subPath: /models
          name: model
        - mountPath: /dev/dri
          name: dri"""

        volumes = f"""
      - hostPath:
          path: {self.model_path}
        name: model
      - hostPath:
          path: /dev/dri
        name: dri"""

        llama_cmd = [
            'llama-server',
            '--port',
            self.model_port,
            '--model',
            '/mnt/models/model.file',
            '--alias',
            self.model,
            '--ctx-size',
            self.args.context,
            '--temp',
            self.args.temp,
            '--jinja',
            '--cache-reuse',
            '256',
            '-v',
            '--threads',
            self.args.threads,
            '--host',
            self.host,
        ]

        security = """
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - CAP_CHOWN
            - CAP_FOWNER
            - CAP_FSETID
            - CAP_KILL
            - CAP_NET_BIND_SERVICE
            - CAP_SETFCAP
            - CAP_SETGID
            - CAP_SETPCAP
            - CAP_SETUID
            - CAP_SYS_CHROOT
            add:
            - CAP_DAC_OVERRIDE
          seLinuxOptions:
            type: spc_t"""

        self.stack_yaml = f"""
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
        ai.ramalama: ""
        app: {self.name}{self.labels}
    spec:
      containers:
      - name: model-server
        image: {self.args.image}
        command: ["/usr/libexec/ramalama/ramalama-serve-core"]
        args: {llama_cmd}\
        {security}
        volumeMounts:{volume_mounts}
      - name: llama-stack
        image: {self.stack_image}
        args:
        - /bin/sh
        - -c
        - llama stack run --image-type venv /etc/ramalama/ramalama-run.yaml
        env:
        - name: RAMALAMA_URL
          value: http://127.0.0.1:{self.model_port}
        - name: INFERENCE_MODEL
          value: {self.model}\
        {security}
        ports:
        - containerPort: 8321
          hostPort: {self.args.port}
      volumes:{volumes}"""
        return self.stack_yaml

    def serve(self):
        self.args.port = compute_serving_port(self.args, quiet=self.args.generate)
        yaml = self.generate()
        if self.args.dryrun:
            print(yaml)
            return

        if self.args.generate.gen_type == "kube":
            kube.genfile(self.name, yaml).write(self.args.generate.output_dir)
            return

        if self.args.generate.gen_type == "quadlet/kube":
            kube.genfile(self.name, yaml).write(self.args.generate.output_dir)
            k = quadlet.kube(self.name, f"RamaLama {self.model} Kubernetes YAML - llama Stack AI Model Service")
            openai = f"http://localhost:{self.args.port}"
            k.add("comment", f"# RamaLama service for {self.model}")
            k.add("comment", "# Serving RESTAPIs:")
            k.add("comment", f"#    Llama Stack: {openai}")
            k.add("comment", f"#    OpenAI:      {openai}/v1/openai\n")
            k.write(self.args.generate.output_dir)
            return

        yaml_file = tempfile.NamedTemporaryFile(prefix='RamaLama_', delete=not self.args.debug)
        with open(yaml_file.name, 'w') as c:
            c.write(yaml)
            c.flush()

        exec_args = [
            self.args.engine,
            "kube",
            "play",
            "--replace",
        ]
        if not self.args.detach:
            exec_args.append("--wait")

        exec_args.append(yaml_file.name)
        exec_cmd(exec_args)

    def stop(self):
        yaml_file = tempfile.NamedTemporaryFile(prefix='RamaLama_', delete=not self.args.debug)
        with open(yaml_file.name, 'w') as c:
            c.write(self.generate())
            c.flush()

        exec_args = [
            self.args.engine,
            "kube",
            "down",
            yaml_file.name,
        ]

        exec_cmd(exec_args)
