import os

from ramalama.common import MNT_CHAT_TEMPLATE_FILE, MNT_DIR, MNT_FILE, RAG_DIR, get_accel_env_vars


class Quadlet:
    def __init__(self, model, chat_template, image, args, exec_args):
        self.ai_image = model
        if hasattr(args, "MODEL"):
            self.ai_image = args.MODEL
        self.ai_image = self.ai_image.removeprefix("oci://")
        if args.name:
            self.name = args.name
        else:
            self.name = os.path.basename(self.ai_image)

        self.model = model.removeprefix("oci://")
        self.args = args
        self.exec_args = exec_args
        self.image = image
        self.chat_template = chat_template
        self.rag = ""
        self.rag_name = ""
        if args.rag:
            self.rag = args.rag.removeprefix("oci://")
            self.rag_name = os.path.basename(self.rag) + "-rag"

    def kube(self):
        outfile = self.name + ".kube"
        print(f"Generating quadlet file: {outfile}")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
[Unit]
Description=RamaLama {self.model} Kubernetes YAML - AI Model Service
After=local-fs.target

[Kube]
Yaml={self.name}.yaml

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target
"""
            )

    def generate(self):
        chat_template_volume = self._gen_chat_template_volume()
        env_var_string = self._gen_env()
        model_volume = self._gen_model_volume()
        name_string = self._gen_name()
        port_string = self._gen_port()
        rag_volume = self._gen_rag_volume()

        outfile = self.name + ".container"
        print(f"Generating quadlet file: {outfile}")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
[Unit]
Description=RamaLama {self.model} AI Model Service
After=local-fs.target

[Container]
AddDevice=-/dev/accel
AddDevice=-/dev/dri
AddDevice=-/dev/kfd\
{env_var_string}
Exec={" ".join(self.exec_args)}
Image={self.image}\
{model_volume}\
{rag_volume}\
{chat_template_volume}\
{name_string}\
{port_string}

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target
"""
            )

    def _gen_chat_template_volume(self):
        if os.path.exists(self.chat_template):
            return f"\nMount=type=bind,src={self.chat_template},target={MNT_CHAT_TEMPLATE_FILE},ro,Z"
        return ""

    def _gen_env(self):
        env_var_string = ""
        for k, v in get_accel_env_vars().items():
            env_var_string += f"\nEnvironment={k}={v}"
        for e in self.args.env:
            env_var_string += f"\nEnvironment={e}"
        return env_var_string

    def _gen_image(self, name, image):
        outfile = name + ".image"
        print(f"Generating quadlet file: {outfile} ")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
[Image]
Image={image}
"""
            )

    def _gen_name(self):
        name_string = ""
        if hasattr(self.args, "name") and self.args.name:
            name_string = f"\nContainerName={self.args.name}"
        return name_string

    def _gen_model_volume(self):
        if os.path.exists(self.model):
            return f"\nMount=type=bind,src={self.model},target={MNT_FILE},ro,Z"

        outfile = self.name + ".volume"

        print(f"Generating quadlet file: {outfile} ")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
[Volume]
Driver=image
Image={self.name}.image
"""
            )
        self._gen_image(self.name, self.ai_image)
        return f"\nMount=type=image,source={self.ai_image},destination={MNT_DIR},subpath=/models,readwrite=false"

    def _gen_port(self):
        port_string = ""
        if hasattr(self.args, "port"):
            port_string = f"\nPublishPort={self.args.port}"
        return port_string

    def _gen_rag_volume(self):
        rag_volume = ""
        if not hasattr(self.args, "rag") or not self.rag:
            return rag_volume

        outfile = self.rag_name + ".volume"

        print(f"Generating quadlet file: {outfile} ")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
[Volume]
Driver=image
Image={self.rag_name}.image
"""
            )
        self._gen_image(self.rag_name, self.rag)
        return f"\nMount=type=image,source={self.rag},destination={RAG_DIR},readwrite=false"
