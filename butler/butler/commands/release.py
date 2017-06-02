"""Make a release."""
# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import subprocess


BASH_BLUE_MARKER = '\033[1;36m'
BASH_RESET_MARKER = '\033[0m'


def run(cmd):
  """Run the command."""
  print
  print '%s%s%s' %(BASH_BLUE_MARKER, cmd, BASH_RESET_MARKER)

  subprocess.check_call(cmd, shell=True, env=os.environ.copy())


def read_version():
  """Read the current version."""
  with open('tool/clusterfuzz/resources/VERSION', 'r') as f:
    return f.read().strip()


def check_git_state():
  """Check if the repo is NOT dirty."""
  diff = subprocess.check_output('git diff', shell=True, env=os.environ.copy())

  if bool(diff):
    raise Exception(
        'The repo is dirty. Please fix it before releasing a version.')


def execute():
  """Release the new version."""
  check_git_state()
  version = read_version()

  if 'rc' in version:
    dest = '/google/data/rw/teams/clusterfuzz-tools/releases/clusterfuzz-rc'
  else:
    dest = '/google/data/rw/teams/clusterfuzz-tools/releases/clusterfuzz'

  run('./pants binary tool:clusterfuzz-%s' % version)
  run('gsutil cp dist/clusterfuzz-%s.pex gs://clusterfuzz-tools/' % version)
  run('gsutil acl set public-read gs://clusterfuzz-tools/clusterfuzz-%s.pex' %
      version)

  run('prodaccess')
  run('cp dist/clusterfuzz-%s.pex '
      '/google/data/rw/teams/clusterfuzz-tools/releases/' % version)
  run('chmod 775 '
      '/google/data/rw/teams/clusterfuzz-tools/releases/clusterfuzz-%s.pex' %
      version)
  run('ln -sf '
      '/google/data/rw/teams/clusterfuzz-tools/releases/clusterfuzz-%s.pex '
      '%s' % (version, dest))
  run('ls -l %s' % dest)
  run('%s reproduce -h' % dest)

  run('git tag -f -a %s -m "Version %s"' % (version, version))
  run('git push -f --tags')
