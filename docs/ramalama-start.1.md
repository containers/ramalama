% ramalama-start 1

## NAME
ramalama\-start - start named container that is running AI Model

## SYNOPSIS
**ramalama start** [*options*] *name* [...]

Tells container engine to start the specified container(s).

The start command conflicts with --nocontainer option.

## OPTIONS

#### **--help**, **-h**
Print usage message

#### **--ignore**
Ignore missing containers when starting

## DESCRIPTION
Start specified container(s) that execute AI Models. This complements **ramalama-stop(1)**: containers previously stopped with `ramalama stop` can be brought back up with `ramalama start` instead of talking to the container engine directly.

The ramalama start command conflicts with the --nocontainer option. The user needs to start the RamaLama processes manually when running with --nocontainer.

## EXAMPLES

```
$ ramalama start mymodel
$ ramalama start mymodel1 mymodel2
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-run(1)](ramalama-run.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**, **[ramalama-stop(1)](ramalama-stop.1.md)**


## HISTORY
Sep 2026, Originally compiled by Mustafa Senoglu <mmustafasenoglu0@gmail.com>
