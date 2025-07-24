# Setting Up RamaLama with CUDA Support in WSL2 Using Podman

This guide will walk you through the steps required to set up RamaLama in WSL2 with CUDA support using Podman.

## Prerequisites

1. **NVIDIA Game-Ready Drivers**
   Make sure you have the appropriate NVIDIA game-ready drivers installed on your Windows system for CUDA support in WSL2.

## Install the NVIDIA Container Toolkit
Follow the installation instructions provided in the [NVIDIA Container Toolkit installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

---

### Example: Installation using APT (For Distros like Ubuntu)

1. **Configure the Production Repository:**
   ```bash
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
   sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
   sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
   sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

2. **Update the packages list from the repository:**
   ```bash
   sudo apt-get update
   ```
3. **Install the NVIDIA Container Toolkit packages:**
   ```bash
   sudo apt-get install -y nvidia-container-toolkit
   ```
  > **Note:** The Nvidia Container Toolkit is required for WSL to have CUDA resources while running a container. 


## Setting Up CUDA Support For Podman
**Based on this Documentation:**  [Support for Container Device Interface](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html)

---

1. **Generate the CDI specification file:**
   ```bash
   sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
   ```

2. **Check the names of the generated devices**
   Open and edit the NVIDIA container runtime configuration:
   ```bash
   nvidia-ctk cdi list
   ```
   **We Should See Something Like This**
   ```bash
   INFO[0000] Found 1 CDI devices
   nvidia.com/gpu=all
   ```
> **Note:** You must generate a new CDI specification after any configuration change most notably when the driver is upgraded!

## Testing the Setup
**Based on this Documentation:**  [Running a Sample Workload](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/sample-workload.html)

---


1. **Test the Installation**
   Run the following command to verify your setup:
   ```bash
   podman run --rm --device=nvidia.com/gpu=all ubuntu nvidia-smi
   ```

2. **Expected Output**
   If everything is set up correctly, you should see an output similar to this:
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

## Installing Nvidia CUDA Toolkit (Optional)

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

  > **Note:** The Nvidia Cuda Toolkit enables the container runtime to build containers with CUDA. 