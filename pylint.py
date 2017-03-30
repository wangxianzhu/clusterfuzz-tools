"""Run pylint of all changed."""
import subprocess
import sys


files = subprocess.check_output(
    'git diff --name-only origin/master', shell=True).splitlines()
files = [f for f in files if f.endswith('.py')]

exit_code = 0
for f in files:
  exit_code = exit_code | subprocess.call('pylint %s' % f, shell=True)

sys.exit(exit_code)
