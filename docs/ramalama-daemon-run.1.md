% ramalama-daemon-run 1

## NAME
ramalama\-daemon\-run - run the RamaLama REST daemon process

## SYNOPSIS
**ramalama daemon run** [*options*]

## DESCRIPTION
Runs the RamaLama daemon process in the foreground on the host. This is the
command used inside the container when **ramalama daemon start** runs with a
container engine; it can also be invoked directly for host-only deployments.

The daemon listens on the configured host and port and serves management APIs
under **/api**. See **[ramalama-daemon(1)](ramalama-daemon.1.md)** for an
overview of the daemon.

## OPTIONS


[//]: # (BEGIN included file options/help.md)
#### **--help**, **-h**
Show this help message and exit

[//]: # (END   included file options/help.md)


[//]: # (BEGIN included file options/host.md)
#### **--host**="::"
IP address for service to listen on. Defaults to the value from
`ramalama.conf` (typically "::" on dual-stack systems, "0.0.0.0" on IPv4-only
systems).

[//]: # (END   included file options/host.md)


[//]: # (BEGIN included file options/port.md)
#### **--port**, **-p**
port for AI Model server to listen on. It must be available. If not specified,
a free port in the 8080-8180 range is selected, starting with 8080.

The default can be overridden in the `ramalama.conf` file.

[//]: # (END   included file options/port.md)

## EXAMPLES

Run the daemon process directly on the host:

```shell
ramalama daemon run --host :: --port 8080
```

Bind the daemon to localhost only:

```shell
ramalama daemon run --host 127.0.0.1 --port 8080
```

## SEE ALSO
**[ramalama(1)](ramalama.1.md)**, **[ramalama-daemon(1)](ramalama-daemon.1.md)**, **[ramalama-daemon-start(1)](ramalama-daemon-start.1.md)**, **[ramalama-serve(1)](ramalama-serve.1.md)**

## HISTORY
Aug 2026, Split from ramalama-daemon(1)
