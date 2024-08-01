# ramalama

The Ramalama project's goal is to make working with AI boring
through the use of OCI containers.

On first run Ramalama inspects your system for GPU support, falling back to CPU
support if no GPUs are present. It then uses container engines like Podman to
pull the appropriate OCI image with all of the software necessary to run an
AI Model for your systems setup. This eliminates the need for the user to
configure the system for AI themselves. After the initialization, Ramalama
will run the AI Models within a container based on the OCI image.

## Install

Install Ramalama by running this one-liner:

```
curl -fsSL https://raw.githubusercontent.com/containers/ramalama/s/install.sh | sudo bash
```

## Usage

### Listing Models

You can `list` all models pulled into local storage.

```
$ ramalama list
NAME                                                                MODIFIED     SIZE
ollama://tiny-llm:latest                                            16 hours ago 5.5M
huggingface://afrideva/Tiny-Vicuna-1B-GGUF/tiny-vicuna-1b.q2_k.gguf 14 hours ago 460M
ollama://granite-code:3b                                            5 days ago   1.9G
ollama://granite-code:latest                                        1 day ago    1.9G
ollama://moondream:latest                                           6 days ago   791M
```
### Pulling Models

You can `pull` a model using the `pull` command. By default, it pulls from the ollama registry.

```
$ ramalama pull granite-code
###################################################                       32.5%
```

### Running Models

You can `run` a chatbot on a model using the `run` command. By default, it pulls from the ollama registry.

Note: Ramalama will inspect your machine for native GPU support and then will
use a container engine like Podman to pull an OCI container image with the
appropriate code and libraries to run the AI Model. This can take a long time to setup, but only on the first run.
```
$ ramalama run instructlab/merlinite-7b-lab
Copying blob 5448ec8c0696 [--------------------------------------] 0.0b / 63.6MiB (skipped: 0.0b = 0.00%)
Copying blob cbd7e392a514 [--------------------------------------] 0.0b / 65.3MiB (skipped: 0.0b = 0.00%)
Copying blob 5d6c72bcd967 done  208.5MiB / 208.5MiB (skipped: 0.0b = 0.00%)
Copying blob 9ccfa45da380 [--------------------------------------] 0.0b / 7.6MiB (skipped: 0.0b = 0.00%)
Copying blob 4472627772b1 [--------------------------------------] 0.0b / 120.0b (skipped: 0.0b = 0.00%)
>
```

After the initial container image has been downloaded, you can interact with
different models, using the container image.x
```
$ ramalama run granite-code
> Write a hello world application in python

print("Hello World")
```

In a different terminal window see the running podman container.
```
$ podman ps
CONTAINER ID  IMAGE                             COMMAND               CREATED        STATUS        PORTS       NAMES
91df4a39a360  quay.io/ramalama/ramalama:latest  /home/dwalsh/rama...  4 minutes ago  Up 4 minutes              gifted_volhard
```

### Serving Models

You can `serve` a chatbot on a model using the `serve` command. By default, it pulls from the ollama registry.

```
$ ramalama serve llama3
```

## Diagram

```
+---------------------------+
|                           |
| ramalama run granite-code |
|                           |
+-------+-------------------+
        |
        |
        |                                          +------------------+
        |                                          | Pull model layer |
        +----------------------------------------->| granite-code     |
                                                   +------------------+
                                                   | Repo options:    |
                                                   +-+-------+------+-+
                                                     |       |      |
                                                     v       v      v
                                             +---------+ +------+ +----------+
                                             | Hugging | | quay | | Ollama   |
                                             | Face    | |      | | Registry |
                                             +-------+-+ +---+--+ +-+--------+
                                                     |       |      |
                                                     v       v      v
                                                   +------------------+
                                                   | Start with       |
                                                   | llama.cpp and    |
                                                   | granite-code     |
                                                   | model            |
                                                   +------------------+
```

## In development

Regard this alpha, everything is under development, so expect breaking changes, luckily it's easy to reset everything and re-install:

```
rm -rf /var/lib/ramalama # only required if running as root user
rm -rf $HOME/.local/share/ramalama
```

and install again.

## Credit where credit is due

For the majority of AI/LLM software we use, under the covers the heavy lifting is being done by:

https://github.com/ggerganov/llama.cpp

so if you like this tool, give llama.cpp repo a :star:, and hey, give us a :star: too while you are at it.

![image](https://github.com/user-attachments/assets/d7a91662-5903-4117-ad41-2b193a852ea1)

## Contributors

Open to contributors

<a href="https://github.com/containers/ramalama/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=containers/ramalama" />
</a>
