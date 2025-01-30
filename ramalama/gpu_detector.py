"""
MIT License

(C) 2024-2025 ramalama developers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
"""

import subprocess
import glob
import platform
import logging

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class GPUDetector:
    def __init__(self):
        self.best_gpu = None
        self.best_vram = 0
        self.best_env = None

    def _update_best_gpu(self, memory_mib, gpu_name, env_var):
        """Updates the best available GPU based on highest VRAM."""
        if memory_mib > 1024 and memory_mib > self.best_vram:
            self.best_vram = memory_mib
            self.best_gpu = gpu_name
            self.best_env = env_var

    def get_nvidia_gpu(self):
        """Detects Nvidia GPUs using nvidia-smi (Linux only)."""
        if platform.system() != "Linux":
            return  # Skip on macOS and other platforms

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, check=True
            )
            output = result.stdout.strip()

            for line in output.split('\n'):
                try:
                    index, memory_mib = line.split(',')
                    memory_mib = int(memory_mib.strip())
                    self._update_best_gpu(memory_mib, index.strip(), "CUDA_VISIBLE_DEVICES")
                except ValueError:
                    raise RuntimeError(f"Error parsing Nvidia GPU info: {line}")

        except FileNotFoundError:
            raise RuntimeError("`nvidia-smi` not found. No NVIDIA GPU detected or drivers missing.")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error (check if NVIDIA drivers are loaded)."
            raise RuntimeError(f"Unable to detect NVIDIA GPU(s). Error: {error_msg}")

    def get_amd_gpu(self):
        """Detects AMD GPUs using sysfs on Linux or system_profiler on macOS."""
        if platform.system() == "Linux":
            self._read_gpu_memory('/sys/bus/pci/devices/*/mem_info_vram_total', "AMD GPU", "HIP_VISIBLE_DEVICES")
        elif platform.system() == "Darwin":  # macOS
            self.get_macos_gpu()  # macOS detection covers AMD GPUs

    def _read_gpu_memory(self, path_pattern, gpu_name, env_var):
        """Helper function to read GPU VRAM from `/sys/class/drm/`."""
        try:
            mem_files = glob.glob(path_pattern)
            for mem_file in mem_files:
                with open(mem_file, "r") as f:
                    vram_total = int(f.read().strip()) // (1024 * 1024)  # Convert bytes to MiB
                    return {"GPU": gpu_name, "VRAM": f"{vram_total} MiB", "Env": env_var}
        except Exception as e:
            return {"GPU": gpu_name, "VRAM": "Unknown", "Env": env_var, "Error": str(e)}
        return {"GPU": gpu_name, "VRAM": "Unknown", "Env": env_var}

    def get_intel_gpu(self):
        """Detect Intel GPUs using `lspci` and `/sys/class/drm/` for VRAM info."""
        gpus = []

        # Step 1: Use lspci to detect Intel GPUs
        try:
            output = subprocess.check_output("lspci | grep -i 'VGA compatible controller'", shell=True, text=True)
            for line in output.splitlines():
                if "Intel Corporation" in line:
                    gpu_info = {"GPU": "Intel", "Details": line.strip()}
                    gpus.append(gpu_info)
        except subprocess.CalledProcessError:
            pass  # No Intel GPU found

        # Step 2: Use `/sys/class/drm/` to read VRAM info
        vram_info = self._read_gpu_memory('/sys/class/drm/card*/device/mem_info_vram_total', "Intel GPU", "ONEAPI_DEVICE_SELECTOR")

        # If lspci found an Intel GPU, add VRAM info
        if gpus:
            for gpu in gpus:
                gpu.update(vram_info)
        else:
            gpus.append(vram_info)  # If no lspci match, return VRAM data anyway

        return gpus

    def get_macos_gpu(self):
        """Detect GPUs on macOS using system_profiler SPDisplaysDataType."""
        try:
            output = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"], text=True
            )
            gpus = []
            gpu_info = {}
            inside_gpu_section = False  # Tracks when we are inside a GPU block

            for line in output.splitlines():
                line = line.strip()

                # Start detecting a new GPU section
                if line.endswith(":") and "Displays:" not in line:
                    if gpu_info:  # Store the previous GPU before starting a new one
                        gpus.append(gpu_info)
                        gpu_info = {}
                    inside_gpu_section = True
                    gpu_info["GPU"] = line[:-1]  # Remove trailing colon from GPU name

                elif inside_gpu_section:
                    if "Chipset Model:" in line:
                        gpu_info["GPU"] = line.split(":")[1].strip()
                    elif "Total Number of Cores:" in line:
                        gpu_info["Cores"] = line.split(":")[1].strip()
                    elif "Vendor:" in line:
                        gpu_info["Vendor"] = line.split(":")[1].strip()
                    elif "Metal Support:" in line:
                        gpu_info["Metal"] = line.split(":")[1].strip()

            # Ensure the last detected GPU is added
            if gpu_info:
                gpus.append(gpu_info)

            if not gpus:
                logging.warning("No GPUs detected on macOS.")
                return [{"GPU": "Unknown", "Error": "No GPU detected on macOS"}]

            return gpus

        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to detect GPU on macOS: {e}")
            return [{"GPU": "Unknown", "Error": "Failed to detect GPU on macOS"}]
        except Exception as e:
            logging.error(f"Unexpected error while detecting macOS GPU: {e}")
            return [{"GPU": "Unknown", "Error": str(e)}]


    def detect_best_gpu(self, gpu_template):
        """
        Compares Nvidia, AMD, Apple, and Intel GPUs and appends the best GPU
        with the highest VRAM to gpu_template.
        If one type of GPU fails, it continues to the next type.
        """
        system = platform.system()
        best_gpu = None
        best_vram = 0
        best_env = None  # For CUDA, ONEAPI, Metal, etc.

        if system == "Linux":
            try:
                nvidia_gpus = self.get_nvidia_gpu()
                for gpu in nvidia_gpus:
                    vram = int(gpu.get("VRAM", "0 MiB").split()[0])
                    if vram > best_vram:
                        best_gpu = gpu
                        best_vram = vram
                        best_env = "CUDA"
            except RuntimeError as e:
                logging.warning(f"Warning: NVIDIA detection failed: {e}")

            try:
                amd_gpus = self.get_amd_gpu()
                for gpu in amd_gpus:
                    vram = int(gpu.get("VRAM", "0 MiB").split()[0])
                    if vram > best_vram:
                        best_gpu = gpu
                        best_vram = vram
                        best_env = "ROCm"
            except RuntimeError as e:
                logging.warning(f"Warning: AMD detection failed: {e}")

            try:
                intel_gpus = self.get_intel_gpu()
                for gpu in intel_gpus:
                    vram = int(gpu.get("VRAM", "0 MiB").split()[0])
                    if vram > best_vram:
                        best_gpu = gpu
                        best_vram = vram
                        best_env = "ONEAPI_DEVICE_SELECTOR"
            except RuntimeError as e:
                logging.warning(f"Warning: Intel detection failed: {e}")

        elif system == "Darwin":  # macOS
            try:
                macos_gpus = self.get_macos_gpu()
                for gpu in macos_gpus:
                    vram = int(gpu.get("VRAM", "0 MiB").split()[0])
                    if vram > best_vram:
                        best_gpu = gpu
                        best_vram = vram
                        best_env = "Metal"  # Apple uses Metal for GPU acceleration
            except RuntimeError as e:
                logging.warning(f"Warning: macOS GPU detection failed: {e}")

        else:
            raise RuntimeError(f"GPU detection is not supported on {system}.")

        if best_gpu is not None:
            gpu_template.append({
                "index": best_gpu["GPU"],
                "vram": f"{best_vram} MiB",
                "env": best_env
            })
            return True  # GPU detected and added successfully
        else:
            logging.warning("No compatible GPUs found.")
            return False  # No GPU found
