% ramalama-stop 1

## NAME
ramalama\-stop - stop named container that is running AI Model

## SYNOPSIS
**ramalama stop** [*options*] [*name* ...]

Tells container engine to stop the specified container(s).

The stop command conflicts with --nocontainer option.

## OPTIONS

#### **--all**, **-a**
Stop all containers

#### **--help**, **-h**
Print usage message

#### **--ignore**
Ignore missing containers when stopping

## DESCRIPTION
Stop specified container(s) that are executing AI Models. Multiple container names may be given, or use **--all** to stop every RamaLama container.

The ramalama stop command conflicts with the --nocontainer option. The user needs to stop the RamaLama processes manually when running with --nocontainer.

## EXAMPLES

```
$ ramalama stop mymodel
$ ramalama stop mymodel1 mymodel2
$ ramalama stop --all
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**, **[ramalama-start(1)](ramalama-start.1.md)**


## HISTORY
Sep 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
