% ramalama-login 1

## NAME
ramalama\-login - login to remote registry

## SYNOPSIS
**ramalama login** [*options*] [*registry*]

## DESCRIPTION
login to remote model registry

By default, RamaLama uses the Ollama registry transport. You can override this default by configuring the `ramalama.conf` file or setting the `RAMALAMA_TRANSPORTS` environment variable. Ensure a registry transport is set before attempting to log in.

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
$ export RAMALAMA_TRANSPORT=quay.io/username
$ ramalama login -u username
```

Login to ollama registry
```
$ export RAMALAMA_TRANSPORT=ollama
$ ramalama login
```

Login to huggingface registry
```
$ export RAMALAMA_TRANSPORT=huggingface
$ ramalama login --token=XYZ
```
Logging in to Hugging Face requires the `hf` tool. For installation and usage instructions, see the documentation of the Hugging Face command line interface: [*https://huggingface.co/docs/huggingface_hub/en/guides/cli*](https://huggingface.co/docs/huggingface_hub/en/guides/cli).

Login to ModelScope registry
```
$ export RAMALAMA_TRANSPORT=modelscope
$ ramalama login --token=XYZ
```

Logging in to ModelScope requires the `modelscope` tool. For installation and usage instructions, see the documentation of the ModelScope command line interface: [*https://www.modelscope.cn/docs/Beginner-s-Guide/Environment-Setup*](https://www.modelscope.cn/docs/Beginner-s-Guide/Environment-Setup).

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
