% ramalama-serve 1

## NAME
ramalama\-serve - serve REST API on specified AI Model

## SYNOPSIS
**ramalama serve** [*options*] _model_

## DESCRIPTION
Serve specified AI Model as a chat bot. RamaLama pulls specified AI Model from
registry if it does not exist in local storage.

## MODEL TRANSPORTS

| Transports    | Prefix | Web Site                                            |
| ------------- | ------ | --------------------------------------------------- |
| URL based     | https://, http://, file:// | `https://web.site/ai.model`, `file://tmp/ai.model`|
| HuggingFace   | huggingface://, hf://, hf.co/ | [`huggingface.co`](https://www.huggingface.co)|
| ModelScope    | modelscope://, ms:// | [`modelscope.cn`](https://modelscope.cn/)|
| Ollama        | ollama:// | [`ollama.com`](https://www.ollama.com)|
| OCI Container Registries | oci:// | [`opencontainers.org`](https://opencontainers.org)|
|||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io),[`Artifactory`](https://artifactory.com)|

RamaLama defaults to the Ollama registry transport. This default can be overridden in the `ramalama.conf` file or via the RAMALAMA_TRANSPORTS
environment. `export RAMALAMA_TRANSPORT=huggingface` Changes RamaLama to use huggingface transport.

Modify individual model transports by specifying the `huggingface://`, `oci://`, `ollama://`, `https://`, `http://`, `file://` prefix to the model.

URL support means if a model is on a web site or even on your local system, you can run it directly.

## REST API ENDPOINTS
Under the hood, `ramalama-serve` uses the `LLaMA.cpp` HTTP server by default.

For REST API endpoint documentation, see: [https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#api-endpoints](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#api-endpoints)

## OPTIONS

#### **--api**=**llama-stack** | none**
Unified API layer for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.(default: none)
The default can be overridden in the ramalama.conf file.

#### **--authfile**=*password*
Path of the authentication file for OCI registries

#### **--ctx-size**, **-c**
size of the prompt context. This option is also available as **--max-model-len**. Applies to llama.cpp and vllm regardless of alias (default: 2048, 0 = loaded from model)

#### **--detach**, **-d**
Run the container in the background and print the new container ID.
The default is TRUE. The --nocontainer option forces this option to False.

Use the `ramalama stop` command to stop the container running the served ramalama Model.

#### **--device**
Add a host device to the container. Optional permissions parameter can
be used to specify device permissions by combining r for read, w for
write, and m for mknod(2).

Example: --device=/dev/dri/renderD128:/dev/xvdc:rwm

The device specification is passed directly to the underlying container engine. See documentation of the supported container engine for more information.

#### **--env**=

Set environment variables inside of the container.

This option allows arbitrary environment variables that are available for the
process to be launched inside of the container. If an environment variable is
specified without a value, the container engine checks the host environment
for a value and set the variable only if it is set on the host.

#### **--generate**=type
Generate specified configuration format for running the AI Model as a service

| Key          | Description                                                              |
| ------------ | -------------------------------------------------------------------------|
| quadlet      | Podman supported container definition for running AI Model under systemd |
| kube         | Kubernetes YAML definition for running the AI Model as a service         |
| quadlet/kube | Kubernetes YAML definition for running the AI Model as a service and Podman supported container definition for running the Kube YAML specified pod under systemd|

Optionally, an output directory for the generated files can be specified by
appending the path to the type, e.g. `--generate kube:/etc/containers/systemd`.

#### **--help**, **-h**
show this help message and exit

#### **--host**="0.0.0.0"
IP address for llama.cpp to listen on.

#### **--model-draft**


A draft model is a smaller, faster model that helps accelerate the decoding
process of larger, more complex models, like Large Language Models (LLMs). It
works by generating candidate sequences of tokens that the larger model then
verifies and refines. This approach, often referred to as speculative decoding,
can significantly improve the speed of inferencing by reducing the number of
times the larger model needs to be invoked.

Use --runtime-arg to pass the other draft model related parameters.
Make sure the sampling parameters like top_k on the web UI are set correctly.

#### **--name**, **-n**
Name of the container to run the Model in.

#### **--network**=*""*
set the network mode for the container

#### **--ngl**
number of gpu layers, 0 means CPU inferencing, 999 means use max layers (default: -1)
The default -1, means use whatever is automatically deemed appropriate (0 or 999)

#### **--oci-runtime**

Override the default OCI runtime used to launch the container. Container
engines like Podman and Docker, have their own default oci runtime that they
use. Using this option RamaLama will override these defaults.

On Nvidia based GPU systems, RamaLama defaults to using the
`nvidia-container-runtime`. Use this option to override this selection.

#### **--port**, **-p**
port for AI Model server to listen on. It must be available. If not specified,
the serving port will be 8080 if available, otherwise a free port in 8081-8090 range.

#### **--privileged**
By default, RamaLama containers are unprivileged (=false) and cannot, for
example, modify parts of the operating system. This is because by de‐
fault a container is only allowed limited access to devices. A "privi‐
leged" container is given the same access to devices as the user launch‐
ing the container, with the exception of virtual consoles (/dev/tty\d+)
when running in systemd mode (--systemd=always).

A privileged container turns off the security features that isolate the
container from the host. Dropped Capabilities, limited devices, read-
only mount points, Apparmor/SELinux separation, and Seccomp filters are
all disabled. Due to the disabled security features, the privileged
field should almost never be set as containers can easily break out of
confinement.

Containers running in a user namespace (e.g., rootless containers) can‐
not have more privileges than the user that launched them.

#### **--pull**=*policy*

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

#### **--rag**=
Specify path to Retrieval-Augmented Generation (RAG) database or an OCI Image containing a RAG database

Note: RAG support requires AI Models be run within containers, --nocontainer not supported. Docker does not support image mounting, meaning Podman support required.

#### **--runtime-args**="*args*"
Add *args* to the runtime (llama.cpp or vllm) invocation.

#### **--seed**=
Specify seed rather than using random seed model interaction

#### **--temp**="0.8"
Temperature of the response from the AI Model.
llama.cpp explains this as:

    The lower the number is, the more deterministic the response.

    The higher the number is the more creative the response is, but more likely to hallucinate when set too high.

	Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories

#### **--threads**, **-t**
Maximum number of cpu threads to use.
The default is to use half the cores available on this system for the number of threads.

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

#### **--webui**=*on* | *off*
Enable or disable the web UI for the served model (enabled by default). When set to "on" (the default), the web interface is properly initialized. When set to "off", the `--no-webui` option is passed to the llama-server command to disable the web interface.

## EXAMPLES
### Run two AI Models at the same time. Notice both are running within Podman Containers.
```

$ ramalama serve -d -p 8080 --name mymodel ollama://smollm:135m
09b0e0d26ed28a8418fb5cd0da641376a08c435063317e89cf8f5336baf35cfa

$ ramalama serve -d -n example --port 8081 oci://quay.io/mmortari/gguf-py-example/v1/example.gguf
3f64927f11a5da5ded7048b226fbe1362ee399021f5e8058c73949a677b6ac9c

$ podman ps
CONTAINER ID  IMAGE                             COMMAND               CREATED         STATUS         PORTS                   NAMES
09b0e0d26ed2  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  32 seconds ago  Up 32 seconds  0.0.0.0:8081->8081/tcp  ramalama_sTLNkijNNP
3f64927f11a5  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  17 seconds ago  Up 17 seconds  0.0.0.0:8082->8082/tcp  ramalama_YMPQvJxN97
```

### Generate quadlet service off of HuggingFace granite Model
```
$ ramalama serve --name MyGraniteServer --generate=quadlet granite
Generating quadlet file: MyGraniteServer.container

$ cat MyGraniteServer.container
[Unit]
Description=RamaLama $HOME/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf AI Model Service
After=local-fs.target

[Container]
AddDevice=-/dev/accel
AddDevice=-/dev/dri
AddDevice=-/dev/kfd
Exec=llama-server --port 1234 -m $HOME/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf
Image=quay.io/ramalama/ramalama:latest
Mount=type=bind,src=/home/dwalsh/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf,target=/mnt/models/model.file,ro,Z
ContainerName=MyGraniteServer
PublishPort=8080

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target

$ mv MyGraniteServer.container $HOME/.config/containers/systemd/
$ systemctl --user daemon-reload
$ systemctl start --user MyGraniteServer
$ systemctl status --user MyGraniteServer
● MyGraniteServer.service - RamaLama granite AI Model Service
     Loaded: loaded (/home/dwalsh/.config/containers/systemd/MyGraniteServer.container; generated)
    Drop-In: /usr/lib/systemd/user/service.d
	    └─10-timeout-abort.conf
     Active: active (running) since Fri 2024-09-27 06:54:17 EDT; 3min 3s ago
   Main PID: 3706287 (conmon)
      Tasks: 20 (limit: 76808)
     Memory: 1.0G (peak: 1.0G)

...
$ podman ps
CONTAINER ID  IMAGE                             COMMAND               CREATED        STATUS        PORTS                    NAMES
7bb35b97a0fe  quay.io/ramalama/ramalama:latest  llama-server --po...  3 minutes ago  Up 3 minutes  0.0.0.0:43869->8080/tcp  MyGraniteServer
```

### Generate quadlet service off of tiny OCI Model
```
$ ramalama --runtime=vllm serve --name tiny --generate=quadlet oci://quay.io/rhatdan/tiny:latest
Downloading quay.io/rhatdan/tiny:latest...
Trying to pull quay.io/rhatdan/tiny:latest...
Getting image source signatures
Copying blob 65ba8d40e14a skipped: already exists
Copying blob e942a1bf9187 skipped: already exists
Copying config d8e0b28ee6 done   |
Writing manifest to image destination
Generating quadlet file: tiny.container
Generating quadlet file: tiny.image
Generating quadlet file: tiny.volume

$cat tiny.container
[Unit]
Description=RamaLama /run/model/model.file AI Model Service
After=local-fs.target

[Container]
AddDevice=-/dev/accel
AddDevice=-/dev/dri
AddDevice=-/dev/kfd
Exec=vllm serve --port 8080 /run/model/model.file
Image=quay.io/ramalama/ramalama:latest
Mount=type=volume,source=tiny:latest.volume,dest=/mnt/models,ro
ContainerName=tiny
PublishPort=8080

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target

$ cat tiny.volume
[Volume]
Driver=image
Image=tiny:latest.image

$ cat tiny.image
[Image]
Image=quay.io/rhatdan/tiny:latest
```

### Generate quadlet service off of tiny OCI Model and output to directory
```
$ ramalama --runtime=vllm serve --name tiny --generate=quadlet:~/.config/containers/systemd/ oci://quay.io/rhatdan/tiny:latest
Generating quadlet file: tiny.container
Generating quadlet file: tiny.image
Generating quadlet file: tiny.volume

$ ls ~/.config/containers/systemd/
tiny.container tiny.image tiny.volume
```

### Generate a kubernetes YAML file named MyTinyModel
```
$ ramalama serve --name MyTinyModel --generate=kube oci://quay.io/rhatdan/tiny-car:latest
Generating Kubernetes YAML file: MyTinyModel.yaml
$ cat MyTinyModel.yaml
# Save the output of this file and use kubectl create -f to import
# it into Kubernetes.
#
# Created with ramalama-0.0.21
apiVersion: v1
kind: Deployment
metadata:
  name: MyTinyModel
  labels:
    app: MyTinyModel
spec:
  replicas: 1
  selector:
    matchLabels:
      app: MyTinyModel
  template:
    metadata:
      labels:
	app: MyTinyModel
    spec:
      containers:
      - name: MyTinyModel
	image: quay.io/ramalama/ramalama:latest
	command: ["llama-server"]
	args: ['--port', '8080', '-m', '/mnt/models/model.file']
	ports:
	- containerPort: 8080
	volumeMounts:
	- mountPath: /mnt/models
	  subPath: /models
	  name: model
	- mountPath: /dev/dri
	  name: dri
      volumes:
      - image:
	  reference: quay.io/rhatdan/tiny-car:latest
	  pullPolicy: IfNotPresent
	name: model
      - hostPath:
	  path: /dev/dri
	name: dri
```

### Generate a Llama Stack Kubernetes YAML file named MyLamaStack
```
$ ramalama serve --api llama-stack --name MyLamaStack --generate=kube oci://quay.io/rhatdan/granite:latest
Generating Kubernetes YAML file: MyLamaStack.yaml
$ cat MyLamaStack.yaml
apiVersion: v1
kind: Deployment
metadata:
  name: MyLamaStack
  labels:
    app: MyLamaStack
spec:
  replicas: 1
  selector:
    matchLabels:
      app: MyLamaStack
  template:
    metadata:
      labels:
	ai.ramalama: ""
	app: MyLamaStack
	ai.ramalama.model: oci://quay.io/rhatdan/granite:latest
	ai.ramalama.engine: podman
	ai.ramalama.runtime: llama.cpp
	ai.ramalama.port: 8080
	ai.ramalama.command: serve
    spec:
      containers:
      - name: model-server
	image: quay.io/ramalama/ramalama:0.8
	command: ["/usr/libexec/ramalama/ramalama-serve-core"]
	args: ['llama-server', '--port', '8081', '--model', '/mnt/models/model.file', '--alias', 'quay.io/rhatdan/granite:latest', '--ctx-size', 2048, '--temp', '0.8', '--jinja', '--cache-reuse', '256', '-v', '--threads', 16, '--host', '127.0.0.1']
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
	    type: spc_t
	volumeMounts:
	- mountPath: /mnt/models
	  subPath: /models
	  name: model
	- mountPath: /dev/dri
	  name: dri
      - name: llama-stack
	image: quay.io/ramalama/llama-stack:0.8
	args:
	- /bin/sh
	- -c
	- llama stack run --image-type venv /etc/ramalama/ramalama-run.yaml
	env:
	- name: RAMALAMA_URL
	  value: http://127.0.0.1:8081
	- name: INFERENCE_MODEL
	  value: quay.io/rhatdan/granite:latest
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
	    type: spc_t
	ports:
	- containerPort: 8321
	  hostPort: 8080
      volumes:
      - hostPath:
	  path: quay.io/rhatdan/granite:latest
	name: model
      - hostPath:
	  path: /dev/dri
	name: dri
```

### Generate a kubernetes YAML file named MyTinyModel shown above, but also generate a quadlet to run it in.
```
$ ramalama --name MyTinyModel --generate=quadlet/kube oci://quay.io/rhatdan/tiny-car:latest
run_cmd:  podman image inspect quay.io/rhatdan/tiny-car:latest
Generating Kubernetes YAML file: MyTinyModel.yaml
Generating quadlet file: MyTinyModel.kube
$ cat MyTinyModel.kube
[Unit]
Description=RamaLama quay.io/rhatdan/tiny-car:latest Kubernetes YAML - AI Model Service
After=local-fs.target

[Kube]
Yaml=MyTinyModel.yaml

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target
```

## NVIDIA CUDA Support

See **[ramalama-cuda(7)](ramalama-cuda.7.md)** for setting up the host Linux system for CUDA support.

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-stop(1)](ramalama-stop.1.md)**, **quadlet(1)**, **systemctl(1)**, **podman(1)**, **podman-ps(1)**, **[ramalama-cuda(7)](ramalama-cuda.7.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
