% ramalama-export 1

## NAME
ramalama\-export - export all AI Models to a tarball

## SYNOPSIS
**ramalama export**

## DESCRIPTION
Export all AI Models in the store of RamaLama as tarball so it can be imported on another machine.

## OPTIONS

#### **--filename**
The name of the produced tarball containing all AI Models of the store.
Defaults to ramalama.tar.gz.

#### **--help**, **-h**
Print usage message

#### **--output**
The output directory to save the ramalama.tar.gz to.
Defaults to /var/tmp.

## EXAMPLES

```
$ ramalama export --output /tmp
Exporting store '/usr/share/ramalama/store' to '/tmp/ramalama.tar.gz'
   Processing '/usr/share/ramalama/store/huggingface'...
   Processing '/usr/share/ramalama/store/file'...

$ ramalama --store /usr/share/ramalama export --output /tmp
Exporting store '/usr/share/ramalama/store' to '/tmp/ramalama.tar.gz'
   Processing '/usr/share/ramalama/store/huggingface'...
   Processing '/usr/share/ramalama/store/ollama'...
   Processing '/usr/share/ramalama/store/https'...
   Processing '/usr/share/ramalama/store/file'...
>
```
## SEE ALSO
**[ramalama(1)](ramalama.1.md)**
**[ramalama-import(1)](ramalama-import.1.md)**

## HISTORY
Oct 2025, Originally compiled by Michael Engel <mengel@redhat.com>
