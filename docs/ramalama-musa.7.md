% ramalama-musa 7

# Setting Up RamaLama with MUSA Support on Linux systems

This guide walks through the steps required to set up RamaLama with MUSA support.

## Install the MT Linux Driver

Download the appropriate [MUSA SDK](https://developer.mthreads.com/sdk/download/musa) and follow the installation instructions provided in the [MT Linux Driver installation guide](https://docs.mthreads.com/musa-sdk/musa-sdk-doc-online/install_guide#2%E9%A9%B1%E5%8A%A8%E5%AE%89%E8%A3%85).

## Install the MT Container Toolkit

Obtain the latest [MT CloudNative Toolkits](https://developer.mthreads.com/sdk/download/CloudNative) and follow the installation instructions provided in the [MT Container Toolkit installation guide](https://docs.mthreads.com/cloud-native/cloud-native-doc-online/install_guide/#%E6%91%A9%E5%B0%94%E7%BA%BF%E7%A8%8B%E5%AE%B9%E5%99%A8%E8%BF%90%E8%A1%8C%E6%97%B6%E5%A5%97%E4%BB%B6).

## Setting Up MUSA Support

   ```bash
   $ (cd /usr/bin/musa && sudo ./docker setup $PWD)
   $ docker info | grep mthreads
   Runtimes: mthreads mthreads-experimental runc
   Default Runtime: mthreads
   ```

## Testing the Setup

# **Test the Installation**

   Run the following command to verify setup:

   ```bash
   docker run --rm --env MTHREADS_VISIBLE_DEVICES=all ubuntu:22.04 mthreads-gmi
   ```

# **Expected Output**

   Verify everything is configured correctly, with output similar to this:

   ```text
   Thu May 15 01:53:39 2025
   ---------------------------------------------------------------
       mthreads-gmi:2.0.0           Driver Version:3.0.0
   ---------------------------------------------------------------
   ID   Name           |PCIe                |%GPU  Mem
        Device Type    |Pcie Lane Width     |Temp  MPC Capable
                                            |      ECC Mode
   +-------------------------------------------------------------+
   0    MTT S80        |00000000:01:00.0    |0%    3419MiB(16384MiB)
        Physical       |16x(16x)            |59C   YES
                                            |      N/A
   ---------------------------------------------------------------

   ---------------------------------------------------------------
   Processes:
   ID   PID       Process name                         GPU Memory
                                                            Usage
   +-------------------------------------------------------------+
      No running processes found
   ---------------------------------------------------------------
   ```

### MUSA_VISIBLE_DEVICES

RamaLama respects the `MUSA_VISIBLE_DEVICES` environment variable if it's already set in your environment. If not set, RamaLama will default to using all the GPU detected by mthreads-gmi.

You can specify which GPU devices should be visible to RamaLama by setting this variable before running RamaLama commands:

```bash
export MUSA_VISIBLE_DEVICES="0,1"  # Use GPUs 0 and 1
ramalama run granite
```

This is particularly useful in multi-GPU systems where you want to dedicate specific GPUs to different workloads.

## HISTORY

May 2025, Originally compiled by Xiaodong Ye <yeahdongcn@gmail.com>
