"""Run pylint of all changed."""
import subprocess
import sys
import os

def check_valid_file(filename):
  return os.path.exists(filename) and filename.endswith('.py')

files = subprocess.check_output(
    'git diff --name-only origin/master', shell=True).splitlines()
files = [f for f in files if check_valid_file(f)]

exit_code = 0
for f in files:
  exit_code = exit_code | subprocess.call('pylint %s' % f, shell=True)

sys.exit(exit_code)
