"""Classes & methods to be shared between all commands."""
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

import sys
import subprocess


class ClusterfuzzAuthError(Exception):
  """An exception to deal with Clusterfuzz Authentication errors.

  Makes the response dict available for inspection later on when
  the exception is dealt with."""

  def __init__(self, response):

    message = 'Error authenticating with Clusterfuzz\n%s' % str(response)
    super(ClusterfuzzAuthError, self).__init__(message)

    self.response = response

class PermissionsTooPermissiveError(Exception):
  """An exception to deal with file permissions errors.

  Stores the filename and the current permissions.."""

  def __init__(self, filename, current_permissions):
    message_tuple = (filename,
                     str(current_permissions),
                     filename)
    message = ('File permissions too permissive to open %s\n'
               'Current permissions: %s\nExpected user access only'
               '\nYou can run "chmod 600 %s" to fix this issue'
               % message_tuple)

    super(PermissionsTooPermissiveError, self).__init__(message)
    self.filename = filename
    self.current_permissions = current_permissions


class GomaNotInstalledError(Exception):
  """An exception to tell people GOMA isn not installed."""

  def __init__(self):
    message = ('Either goma is not installed, or $GOMA_DIR is not set.'
               ' Please set up goma before continuing.'
               '\nSee go/ma to learn more.')
    super(GomaNotInstalledError, self).__init__(message)

def execute(command,
            cwd,
            print_output=True,
            exit_on_error=True):
  """Execute a bash command."""
  def _print(s):
    if print_output:
      print s

  _print('Running: %s' % command)
  output = ''

  proc = subprocess.Popen(
      command,
      shell=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      cwd=cwd)

  for byte in iter(lambda: proc.stdout.read(1), b''):
    if print_output:
      sys.stdout.write(byte)
    output += byte

  proc.wait()
  if proc.returncode != 0:
    _print('| Return code is non-zero (%d).' % proc.returncode)
    if exit_on_error:
      _print('| Exit.')
      sys.exit(proc.returncode)
  return proc.returncode, output

def confirm(question, default='y'):
  """Asks the user a question and returns their answer.
  default can either be 'y', 'n', or None. Answer
  is returned as either True or False."""

  accepts = ['y', 'n']
  defaults = '[y/n]'
  if default:
    accepts += ['']
    defaults = defaults.replace(default, default.upper())

  answer = raw_input('%s %s: ' % (question, defaults)).lower().strip()
  while not answer in accepts:
    answer = raw_input('Please type either "y" or "n": ').lower().strip()

  if answer == 'y' or (answer == '' and default == 'y'):
    return True
  return False
