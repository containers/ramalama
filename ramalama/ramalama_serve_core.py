#!/usr/bin/env python3

import argparse
import sys


def main_serve_core(args):
    sys.path.append('./')
    from ramalama.common import exec_cmd

    exec_cmd(args)

    return 0

