% ramalama-perplexity 1

## NAME
ramalama\-perplexity - calculate the perplexity value of an AI Model

## SYNOPSIS
**ramalama perplexity** [*options*] *model* [arg ...]

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

## OPTIONS

#### **--authfile**=*password*
path of the authentication file for OCI registries

#### **--ctx-size**, **-c**
size of the prompt context. This option is also available as **--max-model-len**. Applies to llama.cpp and vllm regardless of alias (default: 2048, 0 = loaded from model)

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

#### **--help**, **-h**
show this help message and exit

#### **--name**, **-n**
name of the container to run the Model in

#### **--network**=*none*
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

#### **--runtime-args**="*args*"
Add *args* to the runtime (llama.cpp or vllm) invocation.

#### **--seed**=
Specify seed rather than using random seed model interaction

#### **--temp**="0.8"
Temperature of the response from the AI Model
llama.cpp explains this as:

    The lower the number is, the more deterministic the response.

    The higher the number is the more creative the response is, but more likely to hallucinate when set too high.

        Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories

#### **--threads**, **-t**
Maximum number of cpu threads to use.
The default is to use half the cores available on this system for the number of threads.

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

## DESCRIPTION
Calculate the perplexity of an AI Model. Perplexity measures how well the model can predict the next token with lower values being better.

## EXAMPLES

```
ramalama perplexity granite-moe3
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Jan 2025, Originally compiled by Eric Curtin <ecurtin@redhat.com>
