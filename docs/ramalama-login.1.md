% ramalama-login 1

## NAME
ramalama\-login - Login to remote model registry

## SYNOPSIS
**ramalama login** [*options*]

## DESCRIPTION
Login to remote model registry

## OPTIONS

Options are specific to registry types.

#### **--username**, **-u**=*username*

Username for registry

#### **--password**, **-p**=*password*

Password for registry

#### **--password-stdin**

Take the password from stdin

#### **--token**

Token to be passed to Model registry

## EXAMPLE

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
$ ramalama login --token=XYZ ollama
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
