# ramalama

The goal of ramalama is to make AI even more boring.

## Install

Install ramalama by running this one-liner:

```
curl -fsSL https://raw.githubusercontent.com/containers/ramalama/main/install.sh | sudo bash
```

## Usage

### Pulling Models

You can pull a model using the `pull` command. By default, it pulls from the ollama registry.

```
ramalama pull granite-code
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
                                                   | Start container  |
                                                   | with llama.cpp   |
                                                   | and granite-code |
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

For the vast majority of AI/LLM software we use, under the covers the heavy lifting is being done by:

https://github.com/ggerganov/llama.cpp

so if you like this tool, give llama.cpp repo a :star:, and hey, give us a :star: too while you are at it.

![image](https://github.com/user-attachments/assets/d7a91662-5903-4117-ad41-2b193a852ea1)
