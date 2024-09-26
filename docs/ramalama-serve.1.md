% ramalama-serve 1

## NAME
ramalama\-serve - serve REST API on specified AI Model

## SYNOPSIS
**ramalama serve** [*options*] *model*

## DESCRIPTION
Serve specified AI Model as a chat bot. RamaLama pulls specified AI Model from
registry if it does not exist in local storage.

## OPTIONS

#### **--detach**, **-d**
Run the container in the background and print the new container ID.
The default is TRUE. The --nocontainer option forces this option to False.

Use the `ramalama stop` command to stop the container running the served ramalama Model.

#### **--generate**=quadlet
Generate specified configuration format for running the AI Model as a service

#### **--help**, **-h**
show this help message and exit

#### **--name**, **-n**
Name of the container to run the Model in.

#### **--port**, **-p**
port for AI Model server to listen on

## EXAMPLES

Run two AI Models at the same time, notice that they are running within Podman Containers.
```
$ ramalama serve -p 8080 --name mymodel ollama://tiny-llm:latest
09b0e0d26ed28a8418fb5cd0da641376a08c435063317e89cf8f5336baf35cfa

$ ramalama serve -n example --port 8081 oci://quay.io/mmortari/gguf-py-example/v1/example.gguf
3f64927f11a5da5ded7048b226fbe1362ee399021f5e8058c73949a677b6ac9c

$ podman ps
CONTAINER ID  IMAGE                             COMMAND               CREATED         STATUS         PORTS                   NAMES
09b0e0d26ed2  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  32 seconds ago  Up 32 seconds  0.0.0.0:8081->8081/tcp  ramalama_sTLNkijNNP
3f64927f11a5  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  17 seconds ago  Up 17 seconds  0.0.0.0:8082->8082/tcp  ramalama_YMPQvJxN97
```

Generate a quadlet for running the AI Model service
```
$ ramalama serve --generate=quadlet granite

[Unit]
Description=RamaLama granite AI Model Service
After=local-fs.target

[Container]
Device=+/dev/dri
Device=+/dev/kfd
Environment=RAMALAMA_TRANSPORT=HuggingFace
Exec=llama-server --port 8080 -m /home/dwalsh/.local/share/ramalama/models/huggingface/instructlab/granite-7b-lab-GGUF/granite-7b-lab-Q4_K_M.gguf
Image=quay.io/ramalama/ramalama:latest
Label=RAMALAMA container
Name=ramalama_YcTTynYeJ6
SecurityLabelDisable=true
Volume=/home/dwalsh/ramalama/ramalama:/usr/bin/ramalama/ramalama:ro
Volume=./ramalama.py:/var/lib/ramalama:ro
PublishPort=8080

[Install]
# Start by default on boot
WantedBy=multi-user.target default.target
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-stop(1)](ramalama-stop.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
