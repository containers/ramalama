"""utilities for working with AMDKFD driver"""

import glob

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
