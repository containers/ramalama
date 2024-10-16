% ramalama-info 1

## NAME
ramalama\-info - Display RamaLama configuration information


## SYNOPSIS
**ramalama info** [*options*]

## DESCRIPTION
Display configuration information in a json format.

## OPTIONS

#### **--help**, **-h**
show this help message and exit

## EXAMPLE

Info all Models downloaded to users homedir
```
$ ramalama info
{
    "Engine": "podman",
    "Image": "quay.io/ramalama/ramalama:latest",
    "Runtime": "llama.cpp",
    "Store": "/home/dwalsh/.local/share/ramalama",
    "Version": "0.0.18"
}
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Oct 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
