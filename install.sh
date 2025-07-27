#!/bin/bash

available() {
  command -v "$1" >/dev/null
}

nvidia_lshw() {
  lshw -c display -numeric -disable network | grep -q 'vendor: .* \[10DE\]'
}

amd_lshw() {
  lshw -c display -numeric -disable network | grep -q 'vendor: .* \[1002\]'
}

mthreads_lshw() {
  lshw -c display -numeric -disable network | grep -q 'vendor: .* \[1ED5\]'
}

dnf_install() {
  if grep -q ostree= /proc/cmdline; then
    return 1
  fi

  $sudo dnf install -y "$1"

  return 0
}

dnf_install_podman() {
  if ! available podman; then
    dnf_install podman || true
  fi
}

apt_install() {
  apt install -y "$1"
}

apt_update_install() {
  if ! available podman; then
    $sudo apt update || true

    # only install docker if podman can't be
    if ! $sudo apt_install podman; then
      if ! available docker; then
        $sudo apt_install docker || true
      fi
    fi
  fi
}

install_mac_dependencies() {
  if [ "$EUID" -eq 0 ]; then
    echo "This script is intended to run as non-root on macOS"

    return 1
  fi

  if ! available "brew"; then
    echo "RamaLama requires brew to complete installation."
    echo
    echo "To install brew please run:"
    echo
    echo "curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash"
    echo

    return 2
  fi

  brew install llama.cpp
  echo
}

check_platform() {
  if [ "$os" = "Darwin" ]; then
    install_mac_dependencies
  elif [ "$os" = "Linux" ]; then
    if [ "$EUID" -ne 0 ]; then
      if ! available sudo; then
        error "This script is intended to run as root on Linux"

        return 3
      fi

      sudo="sudo"
    fi
  else
    echo "This script is intended to run on Linux and macOS only"

    return 4
  fi

  return 0
}

parse_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -l)
        local_install="true"
        shift
        ;;
      *)
        break
    esac
  done
}

print_banner() {
  echo -e "  _____                       _\n" \
          "|  __ \                     | |\n" \
          "| |__) |__ _ _ __ ___   __ _| |     __ _ _ __ ___   __ _\n" \
          "|  _  // _\` | '_ \` _ \ / _\` | |    / _\` | '_ \` _ \ / _\` |\n" \
          "| | \ \ (_| | | | | | | (_| | |___| (_| | | | | | | (_| |\n" \
          "|_|  \_\__,_|_| |_| |_|\__,_|______\__,_|_| |_| |_|\__,_|\n"
}

print_success_info() {
  echo
  echo "====================== Installation Completed ======================"
  echo "Success! RamaLama has been installed successfully."
  echo "For further details, check the documentation at:"
  echo "https://github.com/containers/ramalama/tree/main/docs"
  echo "Or use the '--help' flag to learn more about usage."
  echo "===================================================================="
}

is_python3_at_least_310() {
  python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)'
}

install_uv() {
  local host="raw.githubusercontent.com"
  local install_uv_url="https://$host/containers/ramalama/s/install-uv.sh"
  curl -fsSL "$install_uv_url" | bash
  echo
}

main() {
  set -e -o pipefail

  print_banner
  local local_install="false"
  parse_arguments "$@"

  local os
  os="$(uname -s)"
  local sudo=""
  check_platform
  if ! $local_install && [ -z "$BRANCH" ]; then
    if available dnf; then
      dnf_install_podman
      if is_python3_at_least_310 && dnf_install "ramalama"; then
        return 0
      fi
    elif available apt; then
      apt_update_install
    fi

    if available brew && brew install ramalama; then
      install_uv
      uv tool install mlx-lm
      return 0
    fi
  fi

  install_uv
  uv tool install --force --python python3.11 ramalama
  print_success_info
}

main "$@"
