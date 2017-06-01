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
import logging
import time
import re
import signal
import shutil

import namedlist
import requests
from requests.packages.urllib3.util import retry
from requests import adapters
from backports.shutil_get_terminal_size import get_terminal_size

from clusterfuzz import local_logging
from clusterfuzz import output_transformer


BASH_BLUE_MARKER = '\033[1;36m'
BASH_YELLOW_MARKER = '\033[1;33m'
BASH_RESET_MARKER = '\033[0m'


NO_SUCH_PROCESS_ERRNO = 3


CLUSTERFUZZ_DIR = os.path.expanduser(os.path.join('~', '.clusterfuzz'))
CLUSTERFUZZ_CACHE_DIR = os.path.join(CLUSTERFUZZ_DIR, 'cache')
CLUSTERFUZZ_TESTCASES_DIR = os.path.join(CLUSTERFUZZ_CACHE_DIR, 'testcases')
CLUSTERFUZZ_BUILDS_DIR = os.path.join(CLUSTERFUZZ_CACHE_DIR, 'builds')
AUTH_HEADER_FILE = os.path.join(CLUSTERFUZZ_CACHE_DIR, 'auth_header')
DOMAIN_NAME = 'clusterfuzz.com'
TERMINAL_WIDTH = get_terminal_size().columns
logger = logging.getLogger('clusterfuzz')


Options = namedlist.namedlist(
    'Options',
    ['testcase_id', 'current', 'build', 'disable_goma', 'goma_threads',
     'iterations', 'disable_xvfb', 'target_args', 'edit_mode',
     'disable_gclient', 'goma_dir']
)


# Configuring backoff retrying because sending a request to ClusterFuzz
# might fail during a deployment.
http = requests.Session()
http.mount(
    'https://',
    adapters.HTTPAdapter(
        # backoff_factor is 0.5. Therefore, the max wait time is 16s.
        retry.Retry(
            total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504]))
)


def post(*args, **kwargs):  # pragma: no cover
  """Make a post request. This method is needed for mocking."""
  return http.post(*args, **kwargs)


def get_os_name():
  """We need this method because we cannot mock os.name."""
  return os.name


def colorize(s, color):
  """Wrap the string with bash-compatible color."""
  if get_os_name() == 'posix':
    return color + s + BASH_RESET_MARKER
  else:
    return s


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
  """An error to notify when a sanitizer isn't passed to a Definition"""

  def __init__(self):
    message = 'A sanitizer must be provided with each Definition.'
    super(SanitizerNotProvidedError, self).__init__(message)


class Definition(object):
  """Holds all the necessary information to initialize a job's builder."""

  def __init__(self, builder, source_var, reproducer, binary_name,
               sanitizer, target, require_user_data_dir):
    if not sanitizer:
      raise SanitizerNotProvidedError()
    self.builder = builder
    self.source_var = source_var
    self.binary_name = binary_name
    self.sanitizer = sanitizer
    self.reproducer = reproducer
    self.target = target
    self.require_user_data_dir = require_user_data_dir


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


class NotInstalledError(ExpectedException):
  """An exception raised to tell the user to install Blackbox."""

  def __init__(self, binary):
    message = ('%s is not found. Please install it or ensure the path is '
               'correct.' % binary)
    super(NotInstalledError, self).__init__(message)


class BadJobTypeDefinitionError(ExpectedException):
  """An exception raised when a job type description is malformed."""

  def __init__(self, job_type):
    message = ('The definition for the %s job type is incorrectly formatted or'
               ' missing crucial information.' % job_type)
    super(BadJobTypeDefinitionError, self).__init__(message)


class UnreproducibleError(ExpectedException):
  """An exception raised when the testcase cannot be reproduced."""

  def __init__(self, count):
    super(UnreproducibleError, self).__init__(
        'The testcase cannot be reproduced after trying %d times.' % count)


class UserRespondingNoError(ExpectedException):
  """An exception raised when the user decides not to proceed."""

  def __init__(self, question):
    super(UserRespondingNoError, self).__init__(
        'User responding "no" to "%s".' % question)


class DirtyRepoError(ExpectedException):
  """An exception raised when the repo is dirty. Therefore, we cannot checkout
    to a wanted sha."""

  def __init__(self):
    super(DirtyRepoError, self).__init__(
        'Your source directory has uncommitted changes: please '
        'commit or stash these changes and re-run this tool.')


class CommandFailedError(ExpectedException):
  """An exception raised when the command doesn't return 0."""

  def __init__(self, command, returncode):
    super(CommandFailedError, self).__init__(
        '`%s` failed with the return code %s.' % (command, returncode))


class KillProcessFailedError(ExpectedException):
  """An exception raised when the process cannot be killed."""

  def __init__(self, command, pid, pgid):
    super(KillProcessFailedError, self).__init__(
        '`%s` (pid=%s, pgid=%s) cannot be killed.' % (command, pid, pgid))


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

  try:
    for _ in range(0, timeout * 2):
      time.sleep(0.5)
      if proc.poll():
        break

  finally:
    try:
      kill(proc)
    except:  # pylint: disable=bare-except
      pass


def kill(proc):
  """Kill a process multiple times.
    See: https://github.com/google/clusterfuzz-tools/pull/301"""
  try:
    for sig in [signal.SIGTERM, signal.SIGTERM,
                signal.SIGKILL, signal.SIGKILL]:
      pgid = os.getpgid(proc.pid)
      logger.debug('Killing pgid=%s (pid=%s) with %s', pgid, proc.pid, sig)
      os.killpg(pgid, sig)

      # Wait for any shutdown stacktrace to be dumped.
      time.sleep(3)

    raise KillProcessFailedError(proc.args, proc.pid, pgid)
  except OSError as e:
    if e.errno != NO_SUCH_PROCESS_ERRNO:
      raise


def check_binary(binary, cwd):
  """Check if the binary exists."""
  try:
    subprocess.check_output(['which', binary], cwd=cwd)
  except subprocess.CalledProcessError:
    raise NotInstalledError(binary)


def get_stdin_and_filter_args(args):
  """Filter arguments to remove piped input, and return as stdin."""
  match = re.match('(.*)<(.*)', args)
  if not match:
    return subprocess.PIPE, args

  args = match.group(1).strip()
  stdin_handle = open(match.group(2).strip(), 'rb')
  return stdin_handle, args


def start_execute(binary, args, cwd, env=None, print_command=True):
  """Runs a command, and returns the subprocess.Popen object."""

  check_binary(binary, cwd)
  stdin_handle, args = get_stdin_and_filter_args(args)

  command = (binary + ' ' + args).strip()
  env = env or {}

  # See https://github.com/google/clusterfuzz-tools/issues/199 why we need this.
  sanitized_env = {}
  for k, v in env.iteritems():
    if v is not None:
      sanitized_env[str(k)] = str(v)

  env_str = ' '.join(
      ['%s="%s"' % (k, v) for k, v in sanitized_env.iteritems()])

  log = (colorize('Running: %s', BASH_BLUE_MARKER),
         ' '.join([env_str, command]).strip())
  if print_command:
    logger.info(*log)
  else:
    logger.debug(*log)

  final_env = os.environ.copy()
  final_env.update(sanitized_env)

  proc = subprocess.Popen(
      command,
      shell=True,
      stdin=stdin_handle,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      cwd=cwd,
      env=final_env,
      preexec_fn=os.setsid)

  setattr(proc, 'args', command)
  return proc


def wait_execute(proc, exit_on_error, capture_output=True, print_output=True,
                 timeout=None, stdout_transformer=None,
                 stderr_transformer=None):
  """Looks after a command as it runs, and prints/returns its output after."""
  if stdout_transformer is None:
    stdout_transformer = output_transformer.Hidden()

  if stderr_transformer is None:
    stderr_transformer = output_transformer.Identity()

  logger.debug('---------------------------------------')
  wait_timeout(proc, timeout)

  output_chunks = []
  stdout_transformer.set_output(sys.stdout)
  stderr_transformer.set_output(sys.stderr)

  # Stdout is printed as the process runs because some commands (e.g. ninja)
  # might take a long time to run.
  for chunk in iter(lambda: proc.stdout.read(10), b''):
    if print_output:
      local_logging.send_output(chunk)
      stdout_transformer.process(chunk)
    if capture_output:
      # According to: http://stackoverflow.com/questions/19926089, this is the
      # fastest way to build strings.
      output_chunks.append(chunk)

  # We cannot read from stderr because it might cause a hang.
  # Therefore, we use communicate() to get stderr instead.
  # See: https://github.com/google/clusterfuzz-tools/issues/278
  stdout_data, stderr_data = proc.communicate()
  kill(proc)

  for (transformer, data) in [(stdout_transformer, stdout_data),
                              (stderr_transformer, stderr_data)]:
    if capture_output:
      output_chunks.append(data)

    if print_output:
      local_logging.send_output(data)
      transformer.process(data)
      transformer.flush()

  logger.debug('---------------------------------------')
  if proc.returncode != 0:
    logger.debug('| Return code is non-zero (%d).', proc.returncode)
    if exit_on_error:
      logger.debug('| Exit.')
      raise CommandFailedError(proc.args, proc.returncode)
  return proc.returncode, ''.join(output_chunks)


def execute(binary, args, cwd, print_command=True, print_output=True,
            capture_output=True, exit_on_error=True, env=None,
            stdout_transformer=None, stderr_transformer=None):
  """Execute a bash command."""
  proc = start_execute(binary, args, cwd, env=env, print_command=print_command)
  return wait_execute(
      proc=proc, exit_on_error=exit_on_error, capture_output=capture_output,
      print_output=print_output, timeout=None,
      stdout_transformer=stdout_transformer,
      stderr_transformer=stderr_transformer)


def execute_with_shell(binary, args, cwd):
  """Execute command with os.system because install_deps.sh needs it."""
  check_binary(binary, cwd)

  command = ('cd %s && %s %s' % (cwd, binary, args or '')).strip()
  logger.info(colorize('Running: %s' % command, BASH_BLUE_MARKER))
  os.system(command)


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
    raise UserRespondingNoError(question)


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


def get_valid_abs_dir(path):
  """Return true if path is a valid dir."""
  if not path:
    return None

  abs_path = os.path.abspath(os.path.expanduser(path))

  if not os.path.isdir(abs_path):
    return None

  return abs_path


def get_source_directory(source_name):
  """Returns the location of the source directory."""

  source_env = '%s_SRC' % source_name.upper()

  if os.environ.get(source_env):
    return os.environ.get(source_env)

  message = ('This is a %(name)s testcase, please define %(env_name)s'
             ' or enter your %(name)s source location here' %
             {'name': source_name, 'env_name': source_env})

  source_directory = get_valid_abs_dir(
      ask(message, 'Please enter a valid directory', get_valid_abs_dir))

  return source_directory
