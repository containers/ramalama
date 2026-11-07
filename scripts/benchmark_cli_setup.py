"""Measure fresh-process CLI setup: python -m scripts.benchmark_cli_setup.

Full mode forces runtime parser registration, reproducing upstream's setup path.
Optimized mode uses the selected command. GPU mode measures one uncached probe.
No command handlers are executed. Results describe only the current host/config.
"""

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
from time import perf_counter


def sample(mode, command):
    from ramalama import cli, common

    if mode == "gpu":
        common.get_accel.cache_clear()
        start = perf_counter()
        common.get_accel()
    else:
        if mode == "full":
            get_parser = cli.get_parser
            cli.get_parser = lambda **kwargs: get_parser()
        start = perf_counter()
        cli.parse_args_from_cmd([command])
    print(json.dumps({"operation_ms": (perf_counter() - start) * 1000}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--command", choices=["list", "models", "version"], default="list")
    parser.add_argument("--mode", choices=["full", "optimized", "gpu"], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.mode:
        sample(args.mode, args.command)
        return
    if args.samples < 1:
        parser.error("--samples must be positive")

    env = dict(os.environ, RAMALAMA__USER__NO_MISSING_GPU_PROMPT="True")
    results = {mode: {"operation_ms": [], "process_ms": []} for mode in ["full", "optimized", "gpu"]}
    for i in range(args.samples):
        # Alternate order to reduce warm filesystem and scheduling bias.
        modes = list(results)
        for mode in modes if i % 2 == 0 else reversed(modes):
            start = perf_counter()
            result = subprocess.run(
                [sys.executable, "-m", "scripts.benchmark_cli_setup", "--mode", mode, "--command", args.command],
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            results[mode]["process_ms"].append((perf_counter() - start) * 1000)
            results[mode]["operation_ms"].append(json.loads(result.stdout)["operation_ms"])
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "command": args.command,
        "samples": args.samples,
        "results": {
            mode: {
                metric: {"median": statistics.median(values), "min": min(values), "max": max(values)}
                for metric, values in metrics.items()
            }
            for mode, metrics in results.items()
        },
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
