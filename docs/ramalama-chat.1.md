% ramalama-chat 1

## NAME
ramalama\-chat - OpenAI chat with the specified REST API URL

## SYNOPSIS
**ramalama chat** [*options*] [arg...]

positional arguments:
  ARGS                  overrides the default prompt, and the output is
                        returned without entering the chatbot

## DESCRIPTION
Chat with an OpenAI Rest API

## OPTIONS

#### **--api-key**
OpenAI-compatible API key.
Can also be set via the RAMALAMA_API_KEY environment variable.

#### **--color**
Indicate whether or not to use color in the chat.
Possible values are "never", "always" and "auto". (default: auto)

#### **--context-strategy**
Enable LLM-based summarization for managing context when the limit is reached. When enabled, the LLM creates intelligent summaries of conversation history to prevent context overflow.

#### **--help**, **-h**
Show this help message and exit

#### **--list**
List the available models at an endpoint

#### **--mcp**=SERVER_URL
MCP (Model Context Protocol) servers to use for enhanced tool calling capabilities.
Can be specified multiple times to connect to multiple MCP servers.
Each server provides tools that can be automatically invoked during chat conversations.

#### **--model**=MODEL
Model for inferencing (may not be required for endpoints that only serve one model)

#### **--prefix**
Prefix for the user prompt (default: 🦭 > )

#### **--rag**=path
A file or directory of files to be loaded and provided as local context in the chat history.

#### **--server-timeout**=*seconds*
Timeout in seconds for server API queries such as context size and health checks (default: 2.0).

#### **--summarization-timeout**=*seconds*
Timeout in seconds for LLM summarization requests. Only used with `--context-strategy` (default: 30.0).

#### **--summarize-after**=*N*
Automatically summarize conversation history after N messages to prevent context growth.
When enabled, ramalama will periodically condense older messages into a summary,
keeping only recent messages and the summary. This prevents the context from growing
indefinitely during long chat sessions. Set to 0 to disable (default: 4).

#### **--url**=URL
The host to send requests to (default: http://127.0.0.1:8080)


## EXAMPLES

Communicate with the default local OpenAI REST API. (http://127.0.0.1:8080)
With Podman containers.
```
$ ramalama chat
🦭 >

Communicate with an alternative OpenAI REST API URL. With Docker containers.
$ ramalama chat --url http://localhost:1234
🐋 >

Send multiple lines at once
$ ramalama chat
🦭 > Hi \
🦭 > tell me a funny story \
🦭 > please
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Jun 2025, Originally compiled by Dan Walsh <dwalsh@redhat.com>
