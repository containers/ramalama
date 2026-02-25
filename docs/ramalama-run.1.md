% ramalama-run 1

## NAME
ramalama\-run - run specified AI Model as a chatbot

## SYNOPSIS
**ramalama run** [*options*] *model* [arg ...]

## MODEL TRANSPORTS

| Transports    | Prefix | Web Site                                            |
| ------------- | ------ | --------------------------------------------------- |
| URL based     | https://, http://, file:// | `https://web.site/ai.model`, `file://tmp/ai.model`|
| HuggingFace   | huggingface://, hf://, hf.co/ | [`huggingface.co`](https://www.huggingface.co)|
| ModelScope    | modelscope://, ms:// | [`modelscope.cn`](https://modelscope.cn/)|
| Ollama        | ollama:// | [`ollama.com`](https://www.ollama.com)|
| rlcr          | rlcr://   | [`ramalama.com`](https://registry.ramalama.com) |
| OCI Container Registries | oci:// | [`opencontainers.org`](https://opencontainers.org)|
|||Examples: [`quay.io`](https://quay.io),  [`Docker Hub`](https://docker.io),[`Artifactory`](https://artifactory.com)|
| Hosted API Providers | openai:// | [`api.openai.com`](https://api.openai.com)|

RamaLama defaults to the Ollama registry transport. This default can be overridden in the `ramalama.conf` file or via the RAMALAMA_TRANSPORTS
environment. `export RAMALAMA_TRANSPORT=huggingface` Changes RamaLama to use huggingface transport.

Modify individual model transports by specifying the `huggingface://`, `oci://`, `ollama://`, `https://`, `http://`, `file://`, or hosted API
prefix (`openai://`).

Hosted API transports connect directly to the remote provider and bypass the local container runtime. In this mode, flags that tune local
containers (for example `--image`, GPU settings, or `--network`) do not apply, and the provider's own capabilities and security posture govern
the execution. URL support means if a model is on a web site or even on your local system, you can run it directly.

## OPTIONS

#### **--api**=**llama-stack** | none**
unified API layer for Inference, RAG, Agents, Tools, Safety, Evals, and Telemetry.(default: none)
The default can be overridden in the `ramalama.conf` file.

#### **--authfile**=*password*
path of the authentication file for OCI registries

#### **--cache-reuse**=256
Min chunk size to attempt reusing from the cache via KV shifting

#### **--color**
Indicate whether or not to use color in the chat.
Possible values are "never", "always" and "auto". (default: auto)

#### **--ctx-size**, **-c**
size of the prompt context. This option is also available as **--max-model-len**. Applies to llama.cpp and vllm regardless of alias (default: 4096, 0 = loaded from model)

#### **--device**
Add a host device to the container. Optional permissions parameter  can
be  used  to  specify device permissions by combining r for read, w for
write, and m for mknod(2).

Example: --device=/dev/dri/renderD128:/dev/xvdc:rwm

The device specification is passed directly to the underlying container engine.  See documentation of the supported container engine for more information.

Pass '--device=none' explicitly add no device to the container, eg for
running a CPU-only performance comparison.

#### **--env**=

Set environment variables inside of the container.

This option allows arbitrary environment variables that are available for the
process to be launched inside of the container. If an environment variable is
specified without a value, the container engine checks the host environment
for a value and set the variable only if it is set on the host.

#### **--help**, **-h**
Show this help message and exit

#### **--image**=IMAGE
OCI container image to run with specified AI model. RamaLama defaults to using
images based on the accelerator it discovers. For example:
`quay.io/ramalama/ramalama`. See the table below for all default images.
The default image tag is based on the minor version of the RamaLama package.
Version 0.17.1 of RamaLama pulls an image with a `:0.17` tag from the quay.io/ramalama OCI repository. The --image option overrides this default.

The default can be overridden in the `ramalama.conf` file or via the
RAMALAMA_IMAGE environment variable. `export RAMALAMA_IMAGE=quay.io/ramalama/aiimage:1.2` tells
RamaLama to use the `quay.io/ramalama/aiimage:1.2` image.

Accelerated images:

| Accelerator             | Image                      |
| ------------------------| -------------------------- |
|  CPU, Apple             | quay.io/ramalama/ramalama  |
|  HIP_VISIBLE_DEVICES    | quay.io/ramalama/rocm      |
|  CUDA_VISIBLE_DEVICES   | quay.io/ramalama/cuda      |
|  ASAHI_VISIBLE_DEVICES  | quay.io/ramalama/asahi     |
|  INTEL_VISIBLE_DEVICES  | quay.io/ramalama/intel-gpu |
|  ASCEND_VISIBLE_DEVICES | quay.io/ramalama/cann      |
|  MUSA_VISIBLE_DEVICES   | quay.io/ramalama/musa      |

#### **--keep-groups**
pass --group-add keep-groups to podman (default: False)
If GPU device on host system is accessible to user via group access, this option leaks the groups into the container.

#### **--keepalive**
duration to keep a model loaded (e.g. 5m)

#### **--max-tokens**=*integer*
Maximum number of tokens to generate. Set to 0 for unlimited output (default: 0).
This parameter is mapped to the appropriate runtime-specific parameter:
- llama.cpp: `-n` parameter
- MLX: `--max-tokens` parameter
- vLLM: `--max-tokens` parameter

#### **--mcp**=SERVER_URL
MCP (Model Context Protocol) servers to use for enhanced tool calling capabilities.
Can be specified multiple times to connect to multiple MCP servers.
Each server provides tools that can be automatically invoked during chat conversations.

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

#### **--port**, **-p**=*port*
Port for AI Model server to listen on (default: 8080)

The default can be overridden in the `ramalama.conf` file.

#### **--prefix**
Prefix for the user prompt (default: 🦭 > )

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
Pull image policy. The default is **missing**.

- **always**: Always pull the image and throw an error if the pull fails.
- **missing**: Only pull the image when it does not exist in the local containers storage. Throw an error if no image is found and the pull fails.
- **never**: Never pull the image but use the one from the local containers storage. Throw an error when no image is found.
- **newer**: Pull if the image on the registry is newer than the one in the local containers storage. An image is considered to be newer when the digests are different. Comparing the time stamps is prone to errors. Pull errors are suppressed if a local image was found.

#### **--rag**=
Specify path to Retrieval-Augmented Generation (RAG) database or an OCI Image containing a RAG database

#### **--rag-image**=
The image to use to process the RAG database specified by the `--rag` option. The image must contain the `/usr/bin/rag_framework` executable, which
will create a proxy which embellishes client requests with RAG data before passing them on to the LLM, and returns the responses.

#### **--runtime-args**="*args*"
Add *args* to the runtime (llama.cpp or vllm) invocation.

#### **--seed**=
Specify seed rather than using random seed model interaction

#### **--selinux**=*true*
Enable SELinux container separation

#### **--summarize-after**=*N*
Automatically summarize conversation history after N messages to prevent context growth.
When enabled, ramalama will periodically condense older messages into a summary,
keeping only recent messages and the summary. This prevents the context from growing
indefinitely during long chat sessions. Set to 0 to disable (default: 4).

#### **--temp**="0.8"
Temperature of the response from the AI Model
llama.cpp explains this as:

  The lower the number is, the more deterministic the response.

  The higher the number is the more creative the response is, but more likely to hallucinate when set too high.

    Usage: Lower numbers are good for virtual assistants where we need deterministic responses. Higher numbers are good for roleplay or creative tasks like editing stories

#### **--thinking**=*true*
Enable or disable thinking mode in reasoning models

#### **--threads**, **-t**
Maximum number of cpu threads to use.
The default is to use half the cores available on this system for the number of threads.

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

## DESCRIPTION
Run specified AI Model as a chat bot. RamaLama pulls specified AI Model from
registry if it does not exist in local storage. By default a prompt for a chat
bot is started. When arguments are specified, the arguments will be given
to the AI Model and the output returned without entering the chatbot.

## INTERACTIVE COMMANDS

When running in interactive chat mode (without arguments), the following commands are available.
All commands are case-insensitive (e.g., `/CLEAR`, `/Clear`, and `/clear` all work).

#### **/help**, **help**, **?**
Display help information showing all available commands and their descriptions.

#### **/clear**
Clear the conversation history without exiting the chat session. This resets the context
and allows starting a fresh conversation without restarting the container or connection.
A confirmation message will be displayed when the history is cleared.

#### **/bye**, **exit**
Exit the chat session and close the connection.

#### **/tool** [question]
(Only available when using --mcp) Manually select which MCP tool to use for a question.
Without this command, the AI automatically decides whether to use tools based on the question.

#### **Ctrl + D**
Exit the chat session (EOF signal).

## EXAMPLES

Run command without arguments starts a chatbot
```
ramalama run granite
>
```

Run command with local downloaded model for 10 minutes
```
ramalama run --keepalive 10m file:///tmp/mymodel
>
```

Run command with a custom port to allow multiple models running simultaneously
```
ramalama run --port 8081 granite
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

Run command and send multiple lines at once to the chatbot by adding a backslash `\`
at the end of the line
```
$ ramalama run granite
🦭 > Hi \
🦭 > tell me a funny story \
🦭 > please
```

Clear conversation history during a chat session
```
$ ramalama run granite
🦭 > What is the capital of France?
Paris
🦭 > /clear
Conversation history cleared.
🦭 > What is 2+2?
4
```

## Exit Codes:

0   Success
124 RamaLama command did not exit within the keepalive time.


## NVIDIA CUDA Support

See **[ramalama-cuda(7)](ramalama-cuda.7.md)** for setting up the host Linux system for CUDA support.

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-cuda(7)](ramalama-cuda.7.md)**, **[ramalama.conf(5)](ramalama.conf.5.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
