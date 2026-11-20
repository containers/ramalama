% ramalama-skill 1

## NAME
ramalama\-skill - build, push, pull, and list AI skill OCI artifacts

## SYNOPSIS
**ramalama skill** [*options*] *subcommand*

## DESCRIPTION
Manage skill artifacts as OCI artifacts stored in your container engine's own
artifact storage. Skills are directories packaged and tagged so they can be
pushed, pulled, and mounted into a **ramalama sandbox** container.

### build
Package a directory into a tagged OCI artifact:

    $ ramalama skill build -d ./my-skill -t quay.io/ramalama/wiki-kb

### ls
List locally available skill artifacts:

    $ ramalama skill ls
    $ ramalama skill ls --json
    $ ramalama skill ls --path

### push
Publish a locally-built skill artifact to a remote OCI registry:

    $ ramalama skill push my-skill quay.io/ramalama/wiki-kb:latest

### pull
Fetch a remote skill artifact and cache it locally:

    $ ramalama skill pull quay.io/ramalama/wiki-kb:latest

## OPTIONS

#### **--help**, **-h**
Print usage message

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-sandbox(1)](ramalama-sandbox.1.md)**

## HISTORY
Oct 2026, Originally compiled by Mennatullah Mohamed
