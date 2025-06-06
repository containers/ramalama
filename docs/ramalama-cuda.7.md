% ramalama 7

# Setting Up RamaLama with CUDA Support on Linux systems

This guide walks through the steps required to set up RamaLama with CUDA support.

## Install the NVIDIA Container Toolkit

Follow the installation instructions provided in the [NVIDIA Container Toolkit installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

### Installation using dnf/yum (For RPM based distros like Fedora)

* Install the NVIDIA Container Toolkit packages

   ```bash
   sudo dnf install -y nvidia-container-toolkit
   ```

  > **Note:** The NVIDIA Container Toolkit is required on the host for running CUDA in containers.
  > **Note:** If the above installation is not working for you and you are running Fedora, try removing it and using the [COPR](https://copr.fedorainfracloud.org/coprs/g/ai-ml/nvidia-container-toolkit/).

### Installation using APT (For Debian based distros like Ubuntu)

* Configure the Production Repository

   ```bash
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
   sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
   sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
   sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
   ```

* Update the packages list from the repository

   ```bash
   sudo apt-get update
   ```

* Install the NVIDIA Container Toolkit packages

   ```bash
   sudo apt-get install -y nvidia-container-toolkit
   ```

  > **Note:** The NVIDIA Container Toolkit is required for WSL to have CUDA resources while running a container.

## Setting Up CUDA Support

   For additional information see:  [Support for Container Device Interface](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html)

# Generate the CDI specification file

   ```bash
   sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
   ```

# Check the names of the generated devices

   Open and edit the NVIDIA container runtime configuration:

   ```bash
   nvidia-ctk cdi list
   INFO[0000] Found 1 CDI devices
   nvidia.com/gpu=all
   ```

   > **Note:** Generate a new CDI specification after any configuration change most notably when the driver is upgraded!

## Testing the Setup

**Based on this Documentation:**  [Running a Sample Workload](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/sample-workload.html)

---

# **Test the Installation**

   Run the following command to verify setup:

   ```bash
   podman run --rm --device=nvidia.com/gpu=all fedora nvidia-smi
   ```

# **Expected Output**

   Verify everything is configured correctly, with output similar to this:

   ```text
   Thu Dec  5 19:58:40 2024
   +-----------------------------------------------------------------------------------------+
   | NVIDIA-SMI 565.72                 Driver Version: 566.14         CUDA Version: 12.7     |
   |-----------------------------------------+------------------------+----------------------+
   | GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
   | Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
   |                                         |                        |               MIG M. |
   |=========================================+========================+======================|
   |   0  NVIDIA GeForce RTX 3080        On  |   00000000:09:00.0  On |                  N/A |
   | 34%   24C    P5             31W /  380W |     867MiB /  10240MiB |      7%      Default |
   |                                         |                        |                  N/A |
   +-----------------------------------------+------------------------+----------------------+

   +-----------------------------------------------------------------------------------------+
   | Processes:                                                                              |
   |  GPU   GI   CI        PID   Type   Process name                              GPU Memory |
   |        ID   ID                                                               Usage      |
   |=========================================================================================|
   |    0   N/A  N/A        35      G   /Xwayland                                   N/A      |
   |    0   N/A  N/A        35      G   /Xwayland                                   N/A      |
   +-----------------------------------------------------------------------------------------+
   ```

   > **NOTE:** On systems that have SELinux enabled, it may be necessary to turn on the `container_use_devices` boolean in order to run the `nvidia-smi` command successfully from a container.

   To check the status of the boolean, run the following:

   ```bash
   getsebool container_use_devices
   ```

   If the result of the command shows that the boolean is `off`, run the following to turn the boolean on:

   ```bash
   sudo setsebool -P container_use_devices 1
   ```

## Troubleshooting

### CUDA Updates

On some CUDA software updates, RamaLama stops working complaining about missing shared NVIDIA libraries for example:

```bash
ramalama run granite
Error: crun: cannot stat `/lib64/libEGL_nvidia.so.565.77`: No such file or directory: OCI runtime attempted to invoke a command that was not found
```

Because the CUDA version is updated, the CDI specification file needs to be recreated.

   ```bash
   sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
   ```

## SEE ALSO

**[ramalama(1)](ramalama.1.md)**, **[podman(1)](https://github.com/containers/podman/blob/main/docs/podman.1.md)**

## HISTORY

Jan 2025, Originally compiled by Dan Walsh <dwalsh@redhat.com>
