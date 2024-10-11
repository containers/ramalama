# Setting Up RamaLama with CUDA Support in WSL2 Using Podman

This guide will walk you through the steps required to set up RamaLama in WSL2 with CUDA support using Podman.

## Prerequisites

1. **NVIDIA Game-Ready Drivers**
   Make sure you have the appropriate NVIDIA game-ready drivers installed on your Windows system for CUDA support in WSL2.

## Installing CUDA Toolkit

1. **Install the CUDA Toolkit**
   Follow the instructions in the [NVIDIA CUDA WSL User Guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) to install the CUDA toolkit.

   - **Download the CUDA Toolkit**
     Visit the [NVIDIA CUDA Downloads page](https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=WSL-Ubuntu&target_version=2.0&target_type=deb_local) to download the appropriate version for WSL-Ubuntu.

2. **Remove Existing Keys (if needed)**
   Run this command to remove any old keys that might conflict:
   ```bash
   sudo apt-key del 7fa2af80
   ```

3. **Select Your Environment**
   Head back to the [NVIDIA CUDA Downloads page](https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=WSL-Ubuntu&target_version=2.0&target_type=deb_local) and choose the environment that fits your setup. Follow the installation instructions to install the CUDA package (deb format is recommended).

   > **Note:** This allows WSL2 to interact with Windows drivers for CUDA support.

4. **Install the NVIDIA Container Toolkit**
   Install the NVIDIA Container Toolkit by following the instructions in the [NVIDIA Container Toolkit installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

   > **Important:** This package is essential for allowing Podman to access CUDA.

## Setting Up Podman NVIDIA Hook

1. **Create the `nvidia-hook.json` file**
   Run the following command to create the NVIDIA hook configuration for Podman:
   ```bash
   sudo mkdir -p /usr/share/containers/oci/hooks.d/
   cat <<EOF | sudo tee /usr/share/containers/oci/hooks.d/oci-nvidia-hook.json
   {
      "version": "1.0.0",
      "hook": {
	 "path": "/usr/bin/nvidia-container-toolkit",
	 "args": ["nvidia-container-toolkit", "prestart"],
	 "env": [
	       "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
	 ]
      },
      "when": {
	 "always": true,
	 "commands": [".*"]
      },
      "stages": ["prestart"]
   }
   EOF
   ```
     > Hook from [https://gist.github.com/alexandreteles/634006078874ee5e3225b3d9ff64d4df](https://gist.github.com/alexandreteles/634006078874ee5e3225b3d9ff64d4df)

2. **Modify the NVIDIA Container Runtime Configuration**
   Open and edit the NVIDIA container runtime configuration:
   ```bash
   sudo nano /etc/nvidia-container-runtime/config.toml
   ```
   - Find the line with `#no-cgroups = false` uncomment it change it to:
     ```toml
     no-cgroups = true
     ```

## Testing the Setup

1. **Test the Installation**
   Run the following command to verify your setup:
   ```bash
   podman run --rm --gpus all nvidia/cuda:12.6.1-devel-ubi9 nvidia-smi
   ```

2. **Expected Output**
   If everything is set up correctly, you should see an output similar to this:
   ```text
   Wed Oct  9 17:53:31 2024
   +-----------------------------------------------------------------------------------------+
   | NVIDIA-SMI 565.51.01              Driver Version: 565.90         CUDA Version: 12.7     |
   |-----------------------------------------+------------------------+----------------------+
   | GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
   | Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
   |                                         |                        |               MIG M. |
   |=========================================+========================+======================|
   |   0  NVIDIA GeForce RTX 3080        On  |   00000000:0A:00.0  On |                  N/A |
   | 34%   26C    P5             56W /  380W |     790MiB /  10240MiB |      1%      Default |
   |                                         |                        |                  N/A |
   +-----------------------------------------+------------------------+----------------------+

   +-----------------------------------------------------------------------------------------+
   | Processes:                                                                              |
   |  GPU   GI   CI        PID   Type   Process name                              GPU Memory |
   |        ID   ID                                                               Usage      |
   |=========================================================================================|
   |  No running processes found                                                             |
   +-----------------------------------------------------------------------------------------+
   ```
