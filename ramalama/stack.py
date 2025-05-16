from ramalama.common import (
    tagged_image,
)
from ramalama.model_factory import ModelFactory, New


class Stack:
    """Stack class"""

    type = "Stack"

    def __init__(self, args):
        self.args = args
        self.host = "127.0.0.1"
        model = ModelFactory(args.MODEL, args)
        self.model = model.prune_model_input()
        model = New(args.MODEL, args)
        self.model_type = model.type
        self.model_path = model.get_model_path(args)
        self.model_port = str(int(self.args.port) + 1)
        self.stack_image = tagged_image("quay.io/ramalama/llama-stack")

    def generate(self):
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
  name: {self.args.name}
  labels:
    app: {self.args.name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {self.args.name}
  template:
    metadata:
      labels:
        app: {self.args.name}
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

    def Serve(self):
        if self.args.dryrun:
            print(self.stack_yaml)
        return self.engine.run()
