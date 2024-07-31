# ramalama

The goal of ramalama is to make AI even more boring.

## Install

Install ramalama by running this one-liner:

```
curl -fsSL https://raw.githubusercontent.com/containers/ramalama/main/install.sh | sudo bash
```

## Usage

### Listing Models

You can `list` all models pulled into local storage.

```
ramalama list
```
### Pulling Models

You can `pull` a model using the `pull` command. By default, it pulls from the ollama registry.

```
ramalama pull granite-code
```

### Running Models

You can `run` a chatbot on a model using the `run` command. By default, it pulls from the ollama registry.

```
ramalama run instructlab/merlinite-7b-lab
```

### Serving Models

You can `serve` a chatbot on a model using the `serve` command. By default, it pulls from the ollama registry.

```
ramalama serve llama3
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
