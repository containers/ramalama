% ramalama-containers 1

## NAME
ramalama\-containers - List all ramalama containers

## SYNOPSIS
**ramalama containers** [*options*]

**ramalama ps** [*options*]

## DESCRIPTION
List all containers running AI Models

## OPTIONS

#### **--help**, **-h**
Print usage message

#### **--noheading**, **-n**
Do not print heading

## EXAMPLE

```
$ ramalama containers
CONTAINER ID  IMAGE                             COMMAND               CREATED        STATUS                    PORTS                   NAMES
85ad75ecf866  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  5 hours ago    Up 5 hours                0.0.0.0:8080->8080/tcp  ramalama_s3Oh6oDfOP
85ad75ecf866  quay.io/ramalama/ramalama:latest  /usr/bin/ramalama...  4 minutes ago  Exited (0) 4 minutes ago                          granite-server
```
## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
