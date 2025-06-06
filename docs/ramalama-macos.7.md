% ramalama-macos 7

# Configure Podman Machine on Mac for GPU Acceleration

Leveraging GPU acceleration on a Mac with Podman requires the configurion of
the `libkrun` machine provider.

This can be done by either setting an environment variable or modifying the
`containers.conf` file. On MacOS, you'll likely need to create a new Podman
machine with libkrun to access the GPU.

Previously created Podman Machines must be recreated to take
advantage of the `libkrun` provider.

## Configuration Methods:

### containers.conf

Open the containers.conf file, typically located at $HOME/.config/containers/containers.conf.

Add the following line within the [machine] section: provider = "libkrun".
This change will persist across sessions.

### Environment Variable
Set the CONTAINERS_MACHINE_PROVIDER environment variable to libkrun. This will be a temporary change until you restart your terminal or session.

For example: export CONTAINERS_MACHINE_PROVIDER=libkrun

### ramalama.conf

RamaLama can also be run in a limited manner without using Containers, by
specifying the --nocontainer option. Open the ramalama.conf file, typically located at $HOME/.config/ramalama/ramalama.conf.

Add the following line within the [machine] section: `container = false`
This change will persist across sessions.

## Podman Desktop

Creating a Podman Machine with libkrun (MacOS):

    Go to Settings > Resources in Podman Desktop.

In the Podman tile, click Create new.
In the Create a Podman machine screen, you can configure the machine's resources (CPU, Memory, Disk size) and enable Machine with root privileges if needed.
To use libkrun, ensure that the environment variable is set or the containers.conf file is configured before creating the machine.
Once the machine is created, Podman Desktop will manage the connection to the new machine.

## Important Notes:

On MacOS, `libkrun` is used to leverage the system's virtualization framework for running containers, and it requires a Podman machine to be created.

Refer to the [Podman Desktop documentation](https://podman-desktop.io/docs/podman/creating-a-podman-machine) for detailed instructions and troubleshooting tips.

## SEE ALSO

**[ramalama(1)](ramalama.1.md)**, **[podman-machine(1)](https://github.com/containers/podman/blob/main/docs/source/markdown/podman-machine.1.md)**

## HISTORY

Apr 2025, Originally compiled by Dan Walsh <dwalsh@redhat.com>
