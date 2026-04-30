% ramalama-sandbox 1

## NAME
ramalama\-sandbox - run an AI agent in a sandbox, backed by a local AI Model

## SYNOPSIS
**ramalama sandbox** *agent* [*options*] *model* [arg ...]

## DESCRIPTION
Run an AI agent in a container, connected to a local model server also running
in a container. The agent uses the model for reasoning and tool calling.

The *agent* argument selects which AI agent to run. Currently supported agents:

- **goose** - the Goose AI agent (https://github.com/block/goose)
- **openclaw** - the OpenClaw AI agent (https://openclaw.ai/)
- **opencode** - the OpenCode AI agent (https://opencode.ai/)


## OPTIONS

#### **--help**, **-h**
show this help message and exit

## SUBCOMMANDS

| Command  | Man Page                                                       | Description                                           |
| -------- | -------------------------------------------------------------- | ----------------------------------------------------- |
| goose    | [ramalama-sandbox-goose(1)](ramalama-sandbox-goose.1.md)       | run Goose in a sandbox, backed by a local AI Model    |
| openclaw | [ramalama-sandbox-openclaw(1)](ramalama-sandbox-openclaw.1.md) | run OpenClaw in a sandbox, backed by a local AI Model |
| opencode | [ramalama-sandbox-opencode(1)](ramalama-sandbox-opencode.1.md) | run OpenCode in a sandbox, backed by a local AI Model |


## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**

## HISTORY
Mar 2026, Originally compiled by Mike Bonnet <mikeb@redhat.com>
