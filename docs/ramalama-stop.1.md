% ramalama-stop 1

## NAME
ramalama\-stop - stop named container that is running AI Model

## SYNOPSIS
**ramalama stop** [*options*] *name*

## OPTIONS

#### **--all**, **-a**
Stop all containers

#### **--help**, **-h**
Print usage message

#### **--ignore**
Ignore missing containers when stopping

## DESCRIPTION
Stop specified container that is executing the AI Model.

If ramalama command was executed with the --nocontainer model, then
this command will have no effect. The user will need to stop the ramalama
processes manually.

## EXAMPLES

```
$ ramalama stop mymodel
$ ramalama stop --all
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**


## HISTORY
Sep 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
