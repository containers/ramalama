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

#### **--help**, **-h**
Show this help message and exit

#### **--list**
List the available models at an endpoint

#### **--max-tokens**=*integer*
Maximum number of tokens to generate. Set to 0 for unlimited output (default: 0).

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

#### **--summarize-after**=*N*
Automatically summarize conversation history after N messages to prevent context growth.
When enabled, ramalama will periodically condense older messages into a summary,
keeping only recent messages and the summary. This prevents the context from growing
indefinitely during long chat sessions. Set to 0 to disable (default: 4).

#### **--temp**=*float*
Temperature of the response from the AI Model.
Lower numbers are more deterministic, higher numbers are more creative.

#### **--url**=URL
The host to send requests to (default: http://127.0.0.1:8080)


## INTERACTIVE COMMANDS

When running in interactive chat mode, the following commands are available.
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

Communicate with the default local OpenAI REST API. (http://127.0.0.1:8080)
With Podman containers.
```
$ ramalama chat
🦭 >
```

Communicate with an alternative OpenAI REST API URL. With Docker containers.
```
$ ramalama chat --url http://localhost:1234
🐋 >
```

Send multiple lines at once
```
$ ramalama chat
🦭 > Hi \
🦭 > tell me a funny story \
🦭 > please
```

Clear conversation history during a chat session (commands are case-insensitive)
```
$ ramalama chat
🦭 > What is 2+2?
4
🦭 > /CLEAR
Conversation history cleared.
🦭 >
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Jun 2025, Originally compiled by Dan Walsh <dwalsh@redhat.com>
