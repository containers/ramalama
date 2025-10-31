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

## PROXY SUPPORT

RamaLama supports HTTP, HTTPS, and SOCKS proxies via standard environment variables:

- **ALL_PROXY** or **all_proxy**: Proxy for all protocols
- **HTTP_PROXY** or **http_proxy**: Proxy for HTTP connections
- **HTTPS_PROXY** or **https_proxy**: Proxy for HTTPS connections
- **NO_PROXY** or **no_proxy**: Comma-separated list of hosts to bypass proxy

Example proxy URL formats:
- HTTP/HTTPS: `http://proxy.example.com:8080` or `https://proxy.example.com:8443`
- SOCKS4: `socks4://proxy.example.com:1080`
- SOCKS5: `socks5://proxy.example.com:1080` or `socks5h://proxy.example.com:1080` (DNS through proxy)

SOCKS proxy support requires the PySocks library (`pip install PySocks`).

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**

## HISTORY
Aug 2024, Originally compiled by Dan Walsh <dwalsh@redhat.com>
