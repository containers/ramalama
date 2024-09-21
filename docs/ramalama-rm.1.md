% ramalama-rm 1

## NAME
ramalama\-rm - remove AI Model from local storage

## SYNOPSIS
**ramalama rm** [*options*] *model*

## DESCRIPTION
remove AI Model from local storage

## OPTIONS

#### **--all**, **-a**
remove all local Models

#### **--help**, **-h**
show this help message and exit

#### **--ignore**
ignore errors when specified Model does not exist

## EXAMPLES

```
$ ramalama rm ollama://tinyllama

$ ramalama rm --all

$ ramalama rm --ignore bogusmodel

```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
