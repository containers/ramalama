% ramalama-rm 1

## NAME
ramalama\-rm - Remove specified AI Model from local storage

## SYNOPSIS
**ramalama rm** [*options*] *model*

## DESCRIPTION
Remove specified AI Model from local storage

## OPTIONS

#### **--all**, **-a**
Remove all local models

#### **--help**, **-h**
Print usage message

#### **--ignore**
Ignore errors when specified model does not exist

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
