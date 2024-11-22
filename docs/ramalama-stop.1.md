% ramalama-stop 1

## NAME
ramalama\-stop - stop named container that is running AI Model

## SYNOPSIS
**ramalama stop** [*options*] *name*

Tells container engine to stop the specified container.

The stop command conflicts with --nocontainer option.

## OPTIONS

#### **--all**, **-a**
Stop all containers

#### **--help**, **-h**
Print usage message

#### **--ignore**
Ignore missing containers when stopping

## DESCRIPTION
Stop specified container that is executing the AI Model.

The ramalama stop command conflicts with the --nocontainer option. The user needs to stop the RamaLama processes manually when running with --nocontainer.

## EXAMPLES

```
$ ramalama stop mymodel
$ ramalama stop --all
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**


## HISTORY
Sep 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
