% ramalama-agent 1

## NAME
ramalama\-agent - build, push, pull, and list AI agent OCI artifacts

## SYNOPSIS
**ramalama agent** [*options*] *subcommand*

## DESCRIPTION
Manage agent artifacts as OCI artifacts stored in your container engine's own
artifact storage. Agents are directories packaged and tagged so they can be
pushed, pulled, and mounted into a **ramalama sandbox** container.

### build
Package a directory into a tagged OCI artifact:

    $ ramalama agent build -d ./my-agent -t quay.io/ramalama/my-agent

### ls
List locally available agent artifacts:

    $ ramalama agent ls
    $ ramalama agent ls --json
    $ ramalama agent ls --path

### push
Publish a locally-built agent artifact to a remote OCI registry:

    $ ramalama agent push my-agent quay.io/ramalama/my-agent:latest

### pull
Fetch a remote agent artifact and cache it locally:

    $ ramalama agent pull quay.io/ramalama/my-agent:latest

## OPTIONS

#### **--help**, **-h**
Print usage message

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-sandbox(1)](ramalama-sandbox.1.md)**

## HISTORY
Oct 2026, Originally compiled by Mennatullah Mohamed
