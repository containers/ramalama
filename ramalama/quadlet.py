import os

from ramalama.common import default_image, mnt_dir, mnt_file, get_env_vars


class Quadlet:
    def __init__(self, model, args, exec_args):
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
        port_string = ""
        if hasattr(self.args, "port"):
            port_string = f"PublishPort={self.args.port}"

        name_string = ""
        if hasattr(self.args, "name") and self.args.name:
            name_string = f"ContainerName={self.args.name}"

        env_var_string = ""
        for k, v in get_env_vars().items():
            env_var_string += f"Environment={k}={v}\n"

        outfile = self.name + ".container"
        print(f"Generating quadlet file: {outfile}")
        volume = self.gen_volume()
        with open(outfile, 'w') as c:
            c.write(
                f"""\
[Unit]
Description=RamaLama {self.model} AI Model Service
After=local-fs.target

[Container]
AddDevice=-/dev/dri
AddDevice=-/dev/kfd
Exec={" ".join(self.exec_args)}
Image={default_image()}
{env_var_string}
{volume}
{name_string}
{port_string}

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target
"""
            )

    def gen_volume(self):
        if os.path.exists(self.model):
            return f"Mount=type=bind,src={self.model},target={mnt_file},ro,Z"

        outfile = self.name + ".volume"

        self.gen_image()
        print(f"Generating quadlet file: {outfile} ")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
[Volume]
Driver=image
Image={self.name}.image
"""
            )
            return f"Mount=type=image,source={self.ai_image},destination={mnt_dir},subpath=/models,readwrite=false"

    def gen_image(self):
        outfile = self.name + ".image"
        print(f"Generating quadlet file: {outfile} ")
        with open(outfile, 'w') as c:
            c.write(
                f"""\
[Image]
Image={self.ai_image}
"""
            )
