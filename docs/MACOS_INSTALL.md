# macOS Installation Guide for RamaLama

This guide covers the different ways to install RamaLama on macOS.

## Method 1: Self-Contained Installer Package (Recommended)

The easiest way to install RamaLama on macOS is using our self-contained `.pkg` installer. This method includes Python and all dependencies, so you don't need to install anything else.

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

### Verify Installation

```bash
# Check version
ramalama --version

# Get help
ramalama --help
```

## Method 2: Python Package (pip)

If you prefer to use Python package management:

```bash
# Install Python 3.10 or later (if not already installed)
brew install python@3.11

# Install ramalama
pip3 install ramalama

# Or install from source
git clone https://github.com/containers/ramalama.git
cd ramalama
pip3 install .
```

## Method 3: Build from Source

For developers or if you want the latest code:

```bash
# Clone the repository
git clone https://github.com/containers/ramalama.git
cd ramalama

# Install build dependencies
pip3 install build

# Build and install
make install
```

## Prerequisites

Before using RamaLama, you'll need a container engine:

### Option A: Podman (Recommended)

```bash
brew install podman

# Initialize Podman machine with libkrun for GPU access
podman machine init --provider libkrun
podman machine start
```

For more details, see [ramalama-macos(7)](ramalama-macos.7.md).

### Option B: Docker

```bash
brew install docker
```

## Building the Installer Package (For Maintainers)

If you want to build the installer package yourself:

```bash
# Install PyInstaller
pip3 install pyinstaller

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
podman machine rm
podman machine init --provider libkrun
podman machine start
```

## Getting Started

Once installed, try these commands:

```bash
# Check version
ramalama --version

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

