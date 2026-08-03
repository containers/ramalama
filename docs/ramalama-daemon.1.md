% ramalama-daemon 1

## NAME
ramalama\-daemon - manage the RamaLama REST daemon

## SYNOPSIS
**ramalama daemon** *command* [*options*]

## DESCRIPTION
Manage the RamaLama daemon, a REST server that can start and stop AI Models on
demand and proxy inference requests to the models it manages.

Unlike **ramalama serve**, which runs a single model (or router) in the
foreground, the daemon stays up and exposes management APIs under **/api**
(for example listing local models, serving a model, listing running models, and
stopping a model). Inference traffic for served models is proxied under
paths returned by the serve API.

## OPTIONS

#### **--help**, **-h**
Print usage message

## COMMANDS

| Command | Man Page                                                         | Description                                      |
| ------- | ---------------------------------------------------------------- | ------------------------------------------------ |
| start   | [ramalama-daemon-start(1)](ramalama-daemon-start.1.md)           | prepare and start a RamaLama REST daemon         |
| run     | [ramalama-daemon-run(1)](ramalama-daemon-run.1.md)               | run the RamaLama REST daemon process             |

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-daemon-start(1)](ramalama-daemon-start.1.md)**, **[ramalama-daemon-run(1)](ramalama-daemon-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**

## HISTORY
Feb 2025, Originally compiled by Michael Engel <mengel@redhat.com>
Aug 2026, Split daemon start/run into separate man pages
