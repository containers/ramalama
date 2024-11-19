% ramalama-login 1

## NAME
ramalama\-login - login to remote registry

## SYNOPSIS
**ramalama login** [*options*] [*registry*]

## DESCRIPTION
login to remote registry

## OPTIONS
Options are specific to registry types.

#### **--authfile**=*password*
path of the authentication file for OCI registries

#### **--help**, **-h**
show this help message and exit

#### **--password**, **-p**=*password*
password for registry

#### **--password-stdin**
take the password from stdin

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

#### **--token**=*token*
token to be passed to Model registry

#### **--username**, **-u**=*username*
username for registry

## EXAMPLES

Login to quay.io/username oci registry
```
$ ramalama login -u username quay.io/username
```

Login to ollama registry
```
$ ramalama login ollama
```

Login to huggingface registry
```
$ ramalama login --token=XYZ huggingface
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
