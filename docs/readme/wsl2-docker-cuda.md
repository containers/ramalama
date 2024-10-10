# Setting Up Ramalama with CUDA Support in WSL2 Using Docker

This guide will walk you through the steps required to set up Ramalama in WSL2 with CUDA support using Docker.

## Prerequisites

1. **NVIDIA Game-Ready Drivers**
   Ensure that you have the appropriate NVIDIA game-ready drivers installed on your Windows system. This is necessary for CUDA support in WSL2.

2. **Docker Desktop Installation**
   Install Docker Desktop and in settings under **General**, ensure the option to **Use the WSL 2 based engine** is checked :white_check_mark:.

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

   > **Note:** This package enables WSL to interact with Windows drivers, allowing CUDA support.

4. **Install the NVIDIA Container Toolkit**
   Follow the installation instructions provided in the [NVIDIA Container Toolkit installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

5. **Configure the NVIDIA Container Toolkit**
   Run the following command to configure the NVIDIA container runtime for Docker:
   ```bash
   sudo nvidia-ctk runtime configure --runtime=docker
   ```
   > **Note:** Since the Docker daemon does not run in WSL one must restart Docker Desktop in Windows and reopen WSL to apply the changes.

   > **Important:** This package is required for Docker to access CUDA when building images.

## Testing the Setup

1. **Test the Installation**
   Run the following command to verify your setup:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.6.1-devel-ubi9 nvidia-smi
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
