"""Clones the chromium source to ~/chromium/src"""

import os
import subprocess

HOME = os.path.expanduser('~')
DEPOT_TOOLS = os.path.join(HOME, 'depot_tools')
CHROMIUM_DIR = os.path.join(HOME, 'chromium')
CHROMIUM_SRC = os.path.join(CHROMIUM_DIR, 'src')


def clone_chromium():
  """Runs the correct commands to clone chromium & depot tools."""

  if os.path.exists(CHROMIUM_SRC):
    return

  if not os.path.exists(DEPOT_TOOLS):
    subprocess.call(
        ('git clone https://chromium.googlesource.com/chromium/tools/'
         'depot_tools.git'), cwd=HOME, shell=True)

  if not os.path.exists(CHROMIUM_DIR):
    os.makedirs(CHROMIUM_DIR)

  subprocess.call('%s --nohooks chromium' % os.path.join(DEPOT_TOOLS, 'fetch'),
                  cwd=CHROMIUM_DIR, shell=True)
  subprocess.call('build/install-build-deps.sh --no-prompt',
                  cwd=CHROMIUM_SRC, shell=True)
  subprocess.call('export PATH=$PATH:%s && gclient runhooks' % DEPOT_TOOLS,
                  shell=True, cwd=CHROMIUM_SRC)
