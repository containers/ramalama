% ramalama-serve 1

## NAME
ramalama\-serve - serve REST API on specified AI Model

## SYNOPSIS
**ramalama serve** [*options*] _model_

## DESCRIPTION
Serve specified AI Model as a chat bot. RamaLama pulls specified AI Model from
registry if it does not exist in local storage.

## REST API ENDPOINTS
Under the hood, `ramalama-serve` uses the `LLaMA.cpp` HTTP server by default.

For REST API endpoint documentation, see: [https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md#api-endpoints](https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md#api-endpoints)

## OPTIONS

#### **--authfile**=*password*
path of the authentication file for OCI registries

#### **--detach**, **-d**
Run the container in the background and print the new container ID.
The default is TRUE. The --nocontainer option forces this option to False.

Use the `ramalama stop` command to stop the container running the served ramalama Model.

#### **--generate**=type
Generate specified configuration format for running the AI Model as a service

| Key          | Description                                                              |
| ------------ | -------------------------------------------------------------------------|
| quadlet      | Podman supported container definition for running AI Model under systemd |
| kube         | Kubernetes YAML definition for running the AI Model as a service         |
| quadlet/kube | Kubernetes YAML definition for running the AI Model as a service and Podman supported container definition for running the Kube YAML specified pod under systemd|

#### **--help**, **-h**
show this help message and exit

#### **--host**="0.0.0.0"
IP address for llama.cpp to listen on.

#### **--name**, **-n**
Name of the container to run the Model in.

#### **--port**, **-p**
port for AI Model server to listen on

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

## EXAMPLES
### Run two AI Models at the same time. Notice both are running within Podman Containers.
```

$ ramalama serve -d -p 8080 --name mymodel ollama://tiny-llm:latest
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
AddDevice=-/dev/dri
AddDevice=-/dev/kfd
Exec=python3 -m llama_cpp.server --port 1234 --model $HOME/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf
Image=quay.io/ramalama/ramalama:latest
Mount=type=bind,src=/home/dwalsh/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf,target=/mnt/models/model.file,ro,Z
ContainerName=MyGraniteServer
PublishPort=8080

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target

$ mv  MyGraniteServer.container $HOME/.config/containers/systemd/
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

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-stop(1)](ramalama-stop.1.md)**, **quadlet(1)**, **systemctl(1)**, **podman-ps(1)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
