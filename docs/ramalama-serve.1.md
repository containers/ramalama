% ramalama-serve 1

## NAME
ramalama\-serve - Serve specified AI Model as an API server

## SYNOPSIS
**ramalama serve** [*options*] *model*

## DESCRIPTION
Serve specified AI Model as a chat bot. Ramalama pulls specified AI Model from
registry if it does not exist in local storage.

## OPTIONS

#### **--detach**, **-d**
Run the container in the background and print the new container ID.
The default is false. Conflicts with the --nocontainer option.

Use the `ramalama stop` command to stop the container running the served ramalama model.

#### **--help**, **-h**
Print usage message

#### **--name**, **-n**
Name of the container to run the model in.

#### **--port**, **-p**
Port for AI Model server to listen on

## EXAMPLES

```
$ ramalama serve -p 8080 --name mymodel ollama://tiny-llm:latest
$ ramalama serve -n example --port 8081 oci://quay.io/mmortari/gguf-py-example/v1/example.gguf

```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-stop(1)](ramalama-stop.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
