% ramalama-run 1

## NAME
ramalama\-run - run specified AI Model as a chatbot

## SYNOPSIS
**ramalama run** [*options*] *model* [arg ...]

## MODEL TRANSPORTS

| Transports    | Prefix | Web Site                                            |
| ------------- | ------ | --------------------------------------------------- |
| URL based    | https://, http://, file:// | `https://web.site/ai.model`, `file://tmp/ai.model`|
| HuggingFace   | huggingface://, hf:// | [`huggingface.co`](https://www.huggingface.co)      |
| Ollama        | ollama:// | [`ollama.com`](https://www.ollama.com)              |
| OCI Container Registries | oci:// | [`opencontainers.org`](https://opencontainers.org)|
|||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io),[`Artifactory`](https://artifactory.com)|

RamaLama defaults to the Ollama registry transport. This default can be overridden in the `ramalama.conf` file or via the RAMALAMA_TRANSPORTS
environment. `export RAMALAMA_TRANSPORT=huggingface` Changes RamaLama to use huggingface transport.

Modify individual model transports by specifying the `huggingface://`, `oci://`, `ollama://`, `https://`, `http://`, `file://` prefix to the model.

URL support means if a model is on a web site or even on your local system, you can run it directly.

## OPTIONS

#### **--authfile**=*password*
path of the authentication file for OCI registries

#### **--ctx-size**, **-c**
size of the prompt context (default: 2048, 0 = loaded from model)

#### **--gpu**
offload the workload to the GPU

#### **--help**, **-h**
show this help message and exit

#### **--image**
OCI container image to run with specified AI model. By default RamaLama uses
`quay.io/ramalama/ramalama:latest`. The --image option allows users to override
the default.

The default can be overridden in the ramalama.conf file or via the the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_TRANSPORT=quay.io/ramalama/aiimage:latest` tells
RamaLama to use the `quay.io/ramalama/aiimage:latest` image.

#### **--name**, **-n**
name of the container to run the Model in

#### **--privileged**
give extended privileges to container

#### **--seed**=
specify seed rather than using random seed model interaction

#### **--temp**="0.8"
temperature of the response from the AI Model
llama.cpp explains this as:

    The lower the number is, the more deterministic the response.

    The higher the number is the more creative the response is, but more likely to hallucinate when set too high.

        Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

## DESCRIPTION
Run specified AI Model as a chat bot. RamaLama pulls specified AI Model from
registry if it does not exist in local storage. By default a prompt for a chat
bot is started. When arguments are specified, the arguments will be given
to the AI Model and the output returned without entering the chatbot.

## EXAMPLES

Run command without arguments starts a chatbot
```
ramalama run granite
>
```

Run command with local downloaoded model
```
ramalama run file:///tmp/mymodel
>
```

```
ramalama run merlinite "when is the summer solstice"
The summer solstice, which is the longest day of the year, will happen on June ...
```

Run command with a custom prompt and a file passed by the stdin
```
cat file.py | ramalama run quay.io/USER/granite-code:1.0 'what does this program do?'

This program is a Python script that allows the user to interact with a terminal. ...
 [end of text]
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
