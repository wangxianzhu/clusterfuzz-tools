#!/usr/bin/env python
"""Called by asan_symbolize.py, mutates input, passes to llvm-symbolizer."""

import subprocess
import sys
import pkg_resources

def main(*argv):
  """Act as a proxy between asan_symbolize.py and llvm-symbolizer."""

  resource_package = __name__
  llvm_location = pkg_resources.resource_filename(resource_package,
                                                  'llvm-symbolizer')
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
