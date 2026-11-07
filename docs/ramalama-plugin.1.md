% ramalama-plugin 1

## NAME
ramalama\-plugin - build, push, pull, and list AI plugin OCI artifacts

## SYNOPSIS
**ramalama plugin** [*options*] *subcommand*

## DESCRIPTION
Manage plugin artifacts as OCI artifacts stored in your container engine's own
artifact storage. Plugins are directories packaged and tagged so they can be
pushed, pulled, and mounted into a **ramalama sandbox** container.

### build
Package a directory into a tagged OCI artifact:

    $ ramalama plugin build -d ./my-plugin -t quay.io/ramalama/my-plugin

### ls
List locally available plugin artifacts:

    $ ramalama plugin ls
    $ ramalama plugin ls --json
    $ ramalama plugin ls --path

### push
Publish a locally-built plugin artifact to a remote OCI registry:

    $ ramalama plugin push my-plugin quay.io/ramalama/my-plugin:latest

### pull
Fetch a remote plugin artifact and cache it locally:

    $ ramalama plugin pull quay.io/ramalama/my-plugin:latest

## OPTIONS

#### **--help**, **-h**
Print usage message

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-sandbox(1)](ramalama-sandbox.1.md)**

## HISTORY
Oct 2026, Originally compiled by Mennatullah Mohamed
