"""Run pylint of all changed."""

import sys
import os

from pylint import lint


def run_lint(path, pylintrc_path):
  """Run pylint and return exit code."""
  try:
    print 'Linting: %s' % path
    lint.Run(['--rcfile=%s' % pylintrc_path, path])
    return 0
  except SystemExit as e:
    return e.code


def main():
  """Get diff files and run pylint against them."""
  basedir = os.path.dirname(__file__)
  pylintrc_path = os.path.join(basedir, '.pylintrc')
  print 'Pylintrc: %s' % pylintrc_path

  rootdir = os.path.join(basedir, '..')

  exit_code = 0
  for root, dirnames, filenames in os.walk(rootdir):
    filenames = [f for f in filenames if not f.startswith('.')]
    # In PEX, the 3rdparty libraries are placed under `.deps`.
    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
    for filename in filenames:
      if not filename.endswith('.py') or filename == '__main__.py':
        continue
      path = os.path.join(root, filename)
      exit_code = exit_code | run_lint(path, pylintrc_path)

  sys.exit(exit_code)
