% ramalama-pull 1

## NAME
ramalama\-pull - pull AI Models from Model registries to local storage

## SYNOPSIS
**ramalama pull** [*options*] *model*

## DESCRIPTION
Pull specified AI Model into local storage

## OPTIONS

#### **--authfile**=*password*
path of the authentication file for OCI registries

#### **--help**, **-h**
Print usage message

#### **--tls-verify**=*true*
require HTTPS and verify certificates when contacting OCI registries

#### **--verify**=*true*
verify the model after pull, disable to allow pulling of models with different endianness

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
