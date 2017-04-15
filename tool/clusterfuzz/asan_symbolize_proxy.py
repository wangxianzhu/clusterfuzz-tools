#!/usr/bin/env python
"""Called by asan_symbolize.py, mutates input, passes to llvm-symbolizer.
  This file should be a standalone and must NOT depend on other file."""

import os
import subprocess
import sys

def main(*argv):
  """Act as a proxy between asan_symbolize.py and llvm-symbolizer."""
  llvm_location = os.path.join(os.path.dirname(__file__), 'llvm-symbolizer')
  cmd = [llvm_location]
  for x in argv[1:]:
    if '--functions' in x:
      cmd.append('--functions=linkage')
    elif '--inlining' in x:
      cmd.append('--inlining=false')
    else:
      cmd.append(x)
  subprocess.call(cmd, stdin=sys.stdin, stdout=sys.stdout)
  sys.exit(0)

if __name__ == '__main__':
  main()
