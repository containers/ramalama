% ramalama-daemon 1

## NAME
ramalama\-daemon - run a RamaLama REST server

## SYNOPSIS
**ramalama daemon** [*options*] [start|run]

## DESCRIPTION
Run a RamaLama REST server as a background daemon. The daemon exposes an
OpenAI-compatible API used to manage and serve AI Models.

## OPTIONS

#### **--help**, **-h**
Print usage message

## COMMANDS

#### **start**
prepares to run a new RamaLama REST server so it will be run either inside a RamaLama container or on the host

#### **run**
start a new RamaLama REST server

## EXAMPLES

Start the daemon (prepares and launches the REST server)
```
$ ramalama daemon start
```

Run the daemon in the foreground
```
$ ramalama daemon run
```

Run the daemon on a custom port
```
$ ramalama daemon run --port 8080
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Feb 2025, Originally compiled by Michael Engel <mengel@redhat.com>
