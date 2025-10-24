% ramalama-import 1

## NAME
ramalama\-import - import an tarball of AI Models

## SYNOPSIS
**ramalama import**

## DESCRIPTION
Import all AI Models of a previously exported RamaLama tarball into the current store.

## OPTIONS

#### **--help**, **-h**
Print usage message

#### **--input**
The path to the ramalama.tar.gz tarball to import into the current model store.

## EXAMPLES

```
$ ramalama import --input /tmp/ramalama.tar.gz
Importing '/tmp/ramalama.tar.gz' into '/usr/share/ramalama/store

$ ramalama --store /tmp/ramalama import --input /tmp/ramalama.tar.gz
Importing '/tmp/ramalama.tar.gz' into '/tmp/ramalama/store
>
```
## SEE ALSO
**[ramalama(1)](ramalama.1.md)**
**[ramalama-export(1)](ramalama-export.1.md)**

## HISTORY
Oct 2025, Originally compiled by Michael Engel <mengel@redhat.com>
