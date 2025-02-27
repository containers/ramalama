% ramalama-bench 1

## NAME
ramalama\-bench - benchmark specified AI Model

## SYNOPSIS
**ramalama bench** [*options*] *model* [arg ...]

## MODEL TRANSPORTS

| Transports    | Prefix | Web Site                                            |
| ------------- | ------ | --------------------------------------------------- |
| URL based    | https://, http://, file:// | `https://web.site/ai.model`, `file://tmp/ai.model`|
| HuggingFace   | huggingface://, hf://, hf.co/ | [`huggingface.co`](https://www.huggingface.co)      |
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

#### **--device**
Add a host device to the container. Optional permissions parameter  can
be  used  to  specify device permissions by combining r for read, w for
write, and m for mknod(2).

Example: --device=/dev/dri/renderD128:/dev/xvdc:rwm

#### **--help**, **-h**
show this help message and exit

#### **--name**, **-n**
name of the container to run the Model in

#### **--network**=*none*
set the network mode for the container

#### **--ngl**
number of gpu layers, 0 means CPU inferencing, 999 means use max layers (default: -1)
The default -1, means use whatever is automatically deemed appropriate (0 or 999)

#### **--privileged**
By  default, RamaLama containers are unprivileged (=false) and cannot, for
example, modify parts of the operating system. This is  because  by  de‐
fault  a  container is only allowed limited access to devices. A "privi‐
leged" container is given the same access to devices as the user launch‐
ing the container, with the exception of virtual consoles  (/dev/tty\d+)
when running in systemd mode (--systemd=always).

A  privileged container turns off the security features that isolate the
container from the host. Dropped Capabilities,  limited  devices,  read-
only  mount points, Apparmor/SELinux separation, and Seccomp filters are
all disabled.  Due to the disabled  security  features,  the  privileged
field  should  almost never be set as containers can easily break out of
confinement.

Containers running in a user namespace (e.g., rootless containers)  can‐
not have more privileges than the user that launched them.

#### **--pull**=*policy*

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage.  Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage.  Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage.  An image is considered to be newer when the digests are different.  Comparing the time stamps is prone to errors.  Pull errors are suppressed if a local image was found.

#### **--seed**=
Specify seed rather than using random seed model interaction

#### **--temp**="0.8"
Temperature of the response from the AI Model
llama.cpp explains this as:

    The lower the number is, the more deterministic the response.

    The higher the number is the more creative the response is, but more likely to hallucinate when set too high.

        Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

## DESCRIPTION
Benchmark specified AI Model.

## EXAMPLES

```
ramalama bench granite-moe3
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Jan 2025, Originally compiled by Eric Curtin <ecurtin@redhat.com>
