#!/usr/bin/env python3

import argparse
import sys


def serve_code_main(args):
    sys.path.append('./')
    from ramalama.common import exec_cmd

    exec_cmd(args)

    return 0


