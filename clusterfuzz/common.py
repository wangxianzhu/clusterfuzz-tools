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

import os
import sys
import stat
import subprocess
import pkg_resources

CLUSTERFUZZ_DIR = os.path.expanduser(os.path.join('~', '.clusterfuzz'))
AUTH_HEADER_FILE = os.path.join(CLUSTERFUZZ_DIR, 'auth_header')
DOMAIN_NAME = 'clusterfuzz.com'


def get_binary_name(stacktrace):
  prefix = 'Running command: '
  stacktrace_lines = [l['content'] for l in stacktrace]
  for l in stacktrace_lines:
    if prefix in l:
      l = l.replace(prefix, '').split(' ')
      binary_name = os.path.basename(l[0])
      return binary_name

  raise Exception("The stacktrace doesn't contain a line starting with '%s'" %
                  prefix)


class ExpectedException(Exception):
  """A general Exception to extend from."""

  def __init__(self, message):
    super(ExpectedException, self).__init__(message)


class SanitizerNotProvidedError(ExpectedException):
  """An error to notify when a sanitizer isn't passed to a BinaryDefinition"""

  def __init__(self):
    message = 'A sanitizer must be provided with each BinaryDefinition.'
    super(SanitizerNotProvidedError, self).__init__(message)


class BinaryDefinition(object):
  """Holds all the necessary information to initialize a job's builder."""

  def __init__(self, builder, source_var, reproducer, binary_name=None,
               sanitizer=None, target=None):
    if not sanitizer:
      raise SanitizerNotProvidedError()
    self.builder = builder
    self.source_var = source_var
    self.binary_name = binary_name
    self.sanitizer = sanitizer
    self.reproducer = reproducer
    self.target = target


class ClusterfuzzAuthError(ExpectedException):
  """An exception to deal with Clusterfuzz Authentication errors.

  Makes the response dict available for inspection later on when
  the exception is dealt with."""

  def __init__(self, response):

    message = 'Error authenticating with Clusterfuzz\n%s' % str(response)
    super(ClusterfuzzAuthError, self).__init__(message)

    self.response = response

class PermissionsTooPermissiveError(ExpectedException):
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


class GomaNotInstalledError(ExpectedException):
  """An exception to tell people GOMA isn not installed."""

  def __init__(self):
    message = ('Either goma is not installed, or $GOMA_DIR is not set.'
               ' Please set up goma before continuing.'
               '\nSee go/ma to learn more.')
    super(GomaNotInstalledError, self).__init__(message)


class JobTypeNotSupportedError(ExpectedException):
  """An exception raised when user tries to run an unsupported build type."""

  def __init__(self, job_type):
    message = 'The job %s is not yet supported by clusterfuzz tools.' % job_type
    super(JobTypeNotSupportedError, self).__init__(message)


def store_auth_header(auth_header):
  """Stores 'auth_header' locally for future access."""

  if not os.path.exists(os.path.dirname(AUTH_HEADER_FILE)):
    os.makedirs(os.path.dirname(AUTH_HEADER_FILE))

  with open(AUTH_HEADER_FILE, 'w') as f:
    f.write(auth_header)
  os.chmod(AUTH_HEADER_FILE, stat.S_IWUSR|stat.S_IRUSR)


def get_stored_auth_header():
  """Checks whether there is a valid auth key stored locally."""
  if not os.path.isfile(AUTH_HEADER_FILE):
    return None

  can_group_access = bool(os.stat(AUTH_HEADER_FILE).st_mode & 0070)
  can_other_access = bool(os.stat(AUTH_HEADER_FILE).st_mode & 0007)

  if can_group_access or can_other_access:
    raise PermissionsTooPermissiveError(
        AUTH_HEADER_FILE,
        oct(os.stat(AUTH_HEADER_FILE).st_mode & 0777))

  with open(AUTH_HEADER_FILE, 'r') as f:
    return f.read()


def start_execute(command, cwd, environment):
  """Runs a command, and returns the subprocess.Popen object."""

  return subprocess.Popen(
      command,
      shell=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      cwd=cwd,
      env=environment)


def wait_execute(proc, exit_on_error, capture_output=True, print_output=True):
  """Looks after a command as it runs, and prints/returns its output after."""

  def _print(s):
    if print_output:
      print s

  output_chunks = []
  for chunk in iter(lambda: proc.stdout.read(100), b''):
    if print_output:
      sys.stdout.write(chunk)
    if capture_output:
      # According to: http://stackoverflow.com/questions/19926089, this is the
      # fastest way to build strings.
      output_chunks.append(chunk)
  proc.wait()
  if proc.returncode != 0:
    _print('| Return code is non-zero (%d).' % proc.returncode)
    if exit_on_error:
      _print('| Exit.')
      sys.exit(proc.returncode)
  return proc.returncode, ''.join(output_chunks)


def execute(command, cwd, print_output=True, capture_output=True,
            exit_on_error=True, environment=None):
  """Execute a bash command."""

  if print_output:
    print 'Running: %s' % command

  proc = start_execute(command, cwd, environment)
  return wait_execute(proc, exit_on_error, capture_output, print_output)

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

def check_confirm(question):
  """Exits the program if the answer is negative, does nothing otherwise."""

  if not confirm(question):
    sys.exit()


def ask(question, error_message, validate_fn):
  """Asks question, and keeps asking error_message until validate_fn is True"""

  answer = ''
  while not validate_fn(answer):
    answer = raw_input('%s: ' % question)
    question = error_message
  return answer


def get_location(filepath):
  """Take a relative filepath and return the actual path."""

  resource_package = __name__
  resource_path = filepath
  return   pkg_resources.resource_filename(resource_package, resource_path)
