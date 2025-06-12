"""utilities for working with AMDKFD driver"""

import glob

# Heap types in memory properties
#
# Imported from /usr/include/linux/kfd_sysfs.h
HEAP_TYPE_SYSTEM = 0
HEAP_TYPE_FB_PUBLIC = 1
HEAP_TYPE_FB_PRIVATE = 2
HEAP_TYPE_GPU_GDS = 3
HEAP_TYPE_GPU_LDS = 4
HEAP_TYPE_GPU_SCRATCH = 5


def parse_props(path):
    """Returns a dict corresponding to a KFD properties file"""
    with open(path) as file:
        return {key: int(value) for key, _, value in (line.partition(' ') for line in file)}


def gpus():
    """Yields GPU nodes within KFD topology and their properties"""
    for np in sorted(glob.glob('/sys/devices/virtual/kfd/kfd/topology/nodes/*')):
        props = parse_props(np + '/properties')

        # Skip CPUs
        if props['gfx_target_version'] == 0:
            continue

        yield np, props
