# macOS Installation Guide for RamaLama

This guide covers the different ways to install RamaLama on macOS.

## GPU acceleration options

GPU passthrough from a container has unique challenges on macOS, and
it is not yet as fast as running outside of a container (at the time
of writing, performance from a container is around 75-80% of native). We
therefore offer two different options for running ramalama on macOS:

- Within a podman container, using krunkit for GPU passthrough
- Without a container, using MLX directly

### Podman & krunkit Prerequisites

To use krunkit with podman you will need to add `provider = "libkrun"`
to the `[machine]` section of your `containers.conf` (typically in
`$HOME/.config/containers/containers.conf`), like this:

```
[machine]
provider = libkrun
```

Then you can install podman and krunkit and start podman machine.

```bash
brew tap slp/krun
brew install krunkit

brew install podman

podman machine init
podman machine start
```

For more details, see [ramalama-macos(7)](ramalama-macos.7.md).

### Native MLX Prerequisites

If podman is not used, MLX needs to be installed on the host:

```bash
brew install mlx-lm
```

You will also need to tell ramalama to use the MLX runtime using
`--runtime=mlx` or by setting it in `$HOME/.config/ramalama/ramalama.conf`:

```
[ramalama]
runtime = "mlx"
```

If podman is installed, ramalama will default to using it, so if
you would rather use MLX, either pass the `--nocontainer` flag to
ramalama or set it in `$HOME/.config/ramalama/ramalama.conf`:

```
[machine]
container = false
```

## Method 1: Self-Contained Installer Package (Recommended)

The easiest way to install RamaLama on macOS is using our self-contained `.pkg` installer. This method includes Python and all dependencies, so you don't need to install anything else (except for the Prerequisites listed above).

### Download and Install

1. Download the latest installer from the [Releases page](https://github.com/containers/ramalama/releases)
2. Double-click the downloaded `.pkg` file
3. Follow the installation wizard

Or via command line:

```bash
# Download the installer (replace VERSION with the actual version)
curl -LO https://github.com/containers/ramalama/releases/download/vVERSION/RamaLama-VERSION-macOS-Installer.pkg

# Verify the SHA256 checksum (optional but recommended)
curl -LO https://github.com/containers/ramalama/releases/download/vVERSION/RamaLama-VERSION-macOS-Installer.pkg.sha256
shasum -a 256 -c RamaLama-VERSION-macOS-Installer.pkg.sha256

# Install
sudo installer -pkg RamaLama-VERSION-macOS-Installer.pkg -target /
```

### What Gets Installed

The installer places files in:
- `/usr/local/bin/ramalama` - Main executable
- `/usr/local/share/man/` - Man pages
- `/usr/local/share/bash-completion/` - Bash completions
- `/usr/local/share/fish/` - Fish completions
- `/usr/local/share/zsh/` - Zsh completions
- `/Applications/ramalama.app` - App bundle containing configuration files, resources, Python dependencies, etc.

## Method 2: Python Package (pipx)

If you prefer to use Python package management:

```bash
# Install Python 3.10 or later and pipx (if not already installed)
brew install python@3.13 pipx

# Install ramalama
pipx install ramalama
```

## Method 3: Build from Source

For developers or if you want the latest code:

```bash
# Install Python 3.10 or later and pipx (if not already installed)
brew install python@3.13 pipx

# Clone the repository
git clone https://github.com/containers/ramalama.git
cd ramalama

# Install ramalama
pipx install .
```

## Verify Installation

```bash
# Check version
ramalama version

# Get help
ramalama --help
```

## Building the Installer Package (For Maintainers)

If you want to build the installer package yourself:

```bash
# Install PyInstaller
pipx install pyinstaller

# Build the package
./scripts/build_macos_pkg.sh

# The built package will be in:
# build/macos-pkg/RamaLama-VERSION-macOS-Installer.pkg
```

## Uninstallation

To remove RamaLama:

```bash
# Remove the executable
sudo rm /usr/local/bin/ramalama

# Remove the app bundle
sudo rm -rf /Applications/ramalama.app

# Remove configuration and data files (optional)
rm -rf -- "${XDG_DATA_HOME:-~/.local/share}/ramalama"
rm -rf -- "${XDG_CONFIG_HOME:-~/.config}/ramalama"

# Remove man pages (optional)
sudo rm /usr/local/share/man/man1/ramalama*.1
sudo rm /usr/local/share/man/man5/ramalama*.5
sudo rm /usr/local/share/man/man7/ramalama*.7

# Remove shell completions (optional)
sudo rm /usr/local/share/bash-completion/completions/ramalama
sudo rm /usr/local/share/fish/vendor_completions.d/ramalama.fish
sudo rm /usr/local/share/zsh/site-functions/_ramalama
```

## Troubleshooting

### "ramalama: command not found"

Make sure `/usr/local/bin` is in your PATH:

```bash
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### "Cannot verify developer" warning

macOS may show a security warning for unsigned packages.
NOTE: We're working on getting keys to sign it.

To bypass:

1. Right-click the `.pkg` file
2. Select "Open"
3. Click "Open" in the dialog

### Podman machine issues

If Podman isn't working:

```bash
# Reset Podman machine
podman machine stop
podman machine reset
podman machine init
podman machine start
```

## Getting Started

Once installed, try these commands:

```bash
# Check version
ramalama version

# Pull a model
ramalama pull tinyllama

# Run a chatbot
ramalama run tinyllama

# Get help
ramalama --help
```

## Additional Resources

- [RamaLama Documentation](https://ramalama.ai)
- [GitHub Repository](https://github.com/containers/ramalama)
- [macOS-specific Documentation](ramalama-macos.7.md)
- [Report Issues](https://github.com/containers/ramalama/issues)

## System Requirements

- macOS 10.15 (Catalina) or later
- Intel or Apple Silicon (M1/M2/M3) processor
- 4GB RAM minimum (8GB+ recommended for running models)
- 10GB free disk space
- Podman or Docker

