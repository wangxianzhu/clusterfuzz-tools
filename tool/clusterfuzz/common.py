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

from __future__ import print_function

import os
import sys
import stat
import subprocess
import logging
import time
import re
import signal
import shutil
import yaml

from backports.shutil_get_terminal_size import get_terminal_size
from clusterfuzz import local_logging

CLUSTERFUZZ_DIR = os.path.expanduser(os.path.join('~', '.clusterfuzz'))
AUTH_HEADER_FILE = os.path.join(CLUSTERFUZZ_DIR, 'auth_header')
DOMAIN_NAME = 'clusterfuzz.com'
DEBUG_PRINT = os.environ.get('CF_DEBUG')
TERMINAL_WIDTH = get_terminal_size().columns
SOURCE_CACHE = os.path.join(CLUSTERFUZZ_DIR, 'source_cache')
logger = logging.getLogger('clusterfuzz')


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


def get_version():
  """Print version."""
  with open(get_resource(0640, 'resources', 'VERSION')) as f:
    return f.read().strip()


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


class BlackboxNotInstalledError(ExpectedException):
  """An exception raised to tell the user to install Blackbox."""

  def __init__(self):
    message = ('The blackbox window manager is not installed. As this testcase'
               'requires blackbox running in a virtual display to reproduce'
               'correctly, please install blackbox and run this command again.')
    super(BlackboxNotInstalledError, self).__init__(message)


class BadJobTypeDefinitionError(ExpectedException):
  """An exception raised when a job type description is malformed."""

  def __init__(self, job_type):
    message = ('The definition for the %s job type is incorrectly formatted or'
               ' missing crucial information.' % job_type)
    super(BadJobTypeDefinitionError, self).__init__(message)


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


def wait_timeout(proc, timeout):
  """If proc runs longer than <timeout> seconds, kill it."""
  if not timeout:
    return
  for _ in range(0, timeout * 2):
    time.sleep(0.5)
    if proc.poll():
      break
  else:
    try:
      os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except OSError as e:
      if e.errno != 3:  # No such process.
        raise


def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1,
                       length=min(100, TERMINAL_WIDTH-26), fill='='):
  """Prints a progress bar on the same line.

  From: http://stackoverflow.com/a/34325723."""

  percent = ("{0:." + str(decimals) + "f}").format(
      100 * (iteration / float(total)))
  filled_length = int(length * iteration // total)
  bar = fill * filled_length + '-' * (length - filled_length)
  full_line = '\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix)
  print(full_line, end='\r')
  if iteration == total:
    print()
  return full_line


def interpret_ninja_output(line):
  """Call print progress bar with the right params if line is valid.

  In this case, valid implies line is of a form similar to:
  [12/1000] CXX /filename/1...."""

  if not re.search(r'\[[0-9]{1,6}\/[0-9]{1,6}\] [A-Z]*', line):
    return
  progress = line.split(' ')[0]
  current, total = [int(x) for x in (progress.replace('[', '')
                                     .replace(']', '').split('/'))]
  print_progress_bar(current, total, prefix='Ninja progress:')


def start_execute(command, cwd, environment, print_output=True):
  """Runs a command, and returns the subprocess.Popen object."""

  environment = environment or {}

  # See https://github.com/google/clusterfuzz-tools/issues/199 why we need this.
  sanitized_env = {}
  for k, v in environment.iteritems():
    if v is not None:
      sanitized_env[str(k)] = str(v)

  if print_output:
    env_str = ' '.join(
        ['%s="%s"' % (k, v) for k, v in sanitized_env.iteritems()])
    logger.info('Running: %s %s', env_str, command)

  final_env = os.environ.copy()
  final_env.update(sanitized_env)

  return subprocess.Popen(
      command,
      shell=True,
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      cwd=cwd,
      env=final_env,
      preexec_fn=os.setsid)


def wait_execute(proc, exit_on_error, capture_output=True, print_output=True,
                 timeout=None, ninja_command=False):
  """Looks after a command as it runs, and prints/returns its output after."""

  def _print(s):
    if print_output:
      logger.debug(s)

  _print('---------------------------------------')
  output_chunks = []
  current_line = []
  wait_timeout(proc, timeout)
  for chunk in iter(lambda: proc.stdout.read(100), b''):
    if print_output:
      local_logging.send_output(chunk)
      if ninja_command and not DEBUG_PRINT:
        for x in chunk:
          if x == '\n':
            interpret_ninja_output(''.join(current_line))
            current_line = []
          else:
            current_line.append(x)
      elif not DEBUG_PRINT:
        sys.stdout.write('.')
        sys.stdout.flush()
    if capture_output:
      # According to: http://stackoverflow.com/questions/19926089, this is the
      # fastest way to build strings.
      output_chunks.append(chunk)
  proc.wait()
  if print_output:
    print()
  _print('---------------------------------------')
  if proc.returncode != 0:
    _print('| Return code is non-zero (%d).' % proc.returncode)
    if exit_on_error:
      _print('| Exit.')
      sys.exit(proc.returncode)
  return proc.returncode, ''.join(output_chunks)


def execute(command, cwd, print_output=True, capture_output=True,
            exit_on_error=True, environment=None):
  """Execute a bash command."""
  proc = start_execute(command, cwd, environment, print_output)
  return wait_execute(proc, exit_on_error, capture_output, print_output,
                      ninja_command='ninja' in command)

def confirm(question, default='y'):
  """Asks the user a question and returns their answer.
  default can either be 'y', 'n', or None. Answer
  is returned as either True or False."""

  if os.environ.get('CF_QUIET'):
    return True

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


def get_resource(chmod_permission, *paths):
  """Take a relative filepath and return the actual path. chmod_permission is
    needed because our packaging might destroy the permission."""
  full_path = os.path.join(os.path.dirname(__file__), *paths)
  os.chmod(full_path, chmod_permission)
  return full_path


def delete_if_exists(path):
  """Deletes file if path exists."""

  if os.path.exists(path):
    shutil.rmtree(path)


def get_source_directory(source_name):
  """Returns the location of the source directory."""

  source_env = '%s_SRC' % source_name.upper()

  if os.environ.get(source_env):
    return os.environ.get(source_env)

  if os.path.exists(SOURCE_CACHE):
    with open(SOURCE_CACHE) as stream:
      source_locations = yaml.load(stream)

    if source_env in source_locations:
      return source_locations[source_env]
  else:
    source_locations = {}

  message = ('This is a %(name)s testcase, please define %(env_name)s'
             ' or enter your %(name)s source location here' %
             {'name': source_name, 'env_name': source_env})
  source_directory = os.path.expanduser(
      ask(message, 'Please enter a valid directory',
          lambda x: x and os.path.isdir(os.path.expanduser(x))))

  with open(SOURCE_CACHE, 'w') as f:
    source_locations[source_env] = source_directory
    f.write(yaml.dump(source_locations))

  return source_directory
