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
import signal
import shutil
import tempfile

import namedlist
import requests
from requests.packages.urllib3.util import retry
from requests import adapters
from backports.shutil_get_terminal_size import get_terminal_size

from cmd_editor import editor
from clusterfuzz import local_logging
from clusterfuzz import output_transformer


BASH_BLUE_MARKER = '\033[36m'
BASH_GREEN_MARKER = '\033[32m'
BASH_YELLOW_MARKER = '\033[33m'
BASH_MAGENTA_MARKER = '\033[35m'
BASH_RESET_MARKER = '\033[0m'
NO_SUCH_PROCESS_ERRNO = 3
DEFAULT_READ_BUFFER_LENGTH = 10

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
     'disable_gclient', 'enable_debug', 'goma_dir']
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


class CrashSignature(object):
  """Represents a crash signature (including output)."""

  def __init__(self, crash_type, crash_state_lines, output=''):
    self.crash_type = crash_type
    self.crash_state_lines = tuple(crash_state_lines)
    self.output = output

  def __hash__(self):
    return (self.crash_type, self.crash_state_lines, self.output).__hash__()

  def __eq__(self, other):
    return (isinstance(other, CrashSignature) and
            self.crash_type == other.crash_type and
            self.crash_state_lines == other.crash_state_lines and
            self.output == other.output)


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

  raise MinimizationNotFinishedError()


def get_version():
  """Print version."""
  with open(get_resource(0640, 'resources', 'VERSION')) as f:
    return f.read().strip()


class ExpectedException(Exception):
  """A general Exception to extend from."""

  def __init__(self, message, extras=None):
    super(ExpectedException, self).__init__(message)
    self.extras = extras


class MinimizationNotFinishedError(ExpectedException):
  """Raise when the minimize_task failed or hasn't finished yet. When the
    minimization is not finished, we won't find 'Running command: ' in the
    stacktrace."""

  MESSAGE = (
      "The testcase hasn't been minimized yet or cannot be minimized.\n"
      'If the testcase is new, please wait for a few more hours.\n'
      "If we can't minimize the testcase, it means the testcase is "
      'unreproducible and, thus, not supported by this tool.')

  def __init__(self):
    super(MinimizationNotFinishedError, self).__init__(
        MinimizationNotFinishedError.MESSAGE)


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
               ' Please set up goma before continuing. '
               'See go/ma to learn more.\n\n'
               "If you wouldn't like to use goma, "
               'please re-run with --disable-goma.')
    super(GomaNotInstalledError, self).__init__(message)


class JobTypeNotSupportedError(ExpectedException):
  """An exception raised when user tries to run an unsupported build type."""

  def __init__(self, job_type):
    message = 'The job %s is not yet supported by clusterfuzz tools.' % job_type
    super(JobTypeNotSupportedError, self).__init__(message)


class NotInstalledError(ExpectedException):
  """An exception raised to tell the user to install the required binary."""

  MESSAGE = (
      '{binary} is not found. Please install it or ensure the path is '
      'correct.\n'
      'Most of the time you can install it with `apt-get install {binary}`.')

  def __init__(self, binary):
    super(NotInstalledError, self).__init__(
        NotInstalledError.MESSAGE.format(binary=binary))


class GsutilNotInstalledError(ExpectedException):
  """An exception raised to tell the user to install the required binary."""

  MESSAGE = (
      'gsutil is not installed. Please install it. See:'
      'https://cloud.google.com/storage/docs/gsutil_install')

  def __init__(self):
    super(GsutilNotInstalledError, self).__init__(
        GsutilNotInstalledError.MESSAGE)


class BadJobTypeDefinitionError(ExpectedException):
  """An exception raised when a job type description is malformed."""

  def __init__(self, job_type):
    message = ('The definition for the %s job type is incorrectly formatted or'
               ' missing crucial information.' % job_type)
    super(BadJobTypeDefinitionError, self).__init__(message)


class UnreproducibleError(ExpectedException):
  """An exception raised when the testcase cannot be reproduced."""

  MESSAGE = 'The testcase cannot be reproduced after trying {count} times.'

  def __init__(self, count, crash_signatures):
    crash_signatures = [
        {'type': s.crash_type, 'state': s.crash_state_lines,
         'output': s.output[:100000]}
        for s in list(crash_signatures)[:10]
    ]
    super(UnreproducibleError, self).__init__(
        message=UnreproducibleError.MESSAGE.format(count=count),
        extras={'signatures': crash_signatures})


class DirtyRepoError(ExpectedException):
  """An exception raised when the repo is dirty. Therefore, we cannot checkout
    to a wanted sha."""

  def __init__(self, source_dir):
    super(DirtyRepoError, self).__init__(
        "We can't run the checkout command because %s has "
        'uncommitted changes.\n '
        'please commit or stash these changes and re-run this tool.' %
        source_dir)


class CommandFailedError(ExpectedException):
  """An exception raised when the command doesn't return 0."""

  MESSAGE = '`{cmd}` failed with the return code {returncode}.'

  def __init__(self, command, returncode, stderr):
    super(CommandFailedError, self).__init__(
        CommandFailedError.MESSAGE.format(cmd=command, returncode=returncode),
        extras={'stderr': stderr[:100000]})


class KillProcessFailedError(ExpectedException):
  """An exception raised when the process cannot be killed."""

  def __init__(self, command, pid):
    super(KillProcessFailedError, self).__init__(
        '`%s` (pid=%s) cannot be killed.' % (command, pid))


class UserRespondingNoError(ExpectedException):
  """An exception raised when the user decides not to proceed."""

  def __init__(self, question):
    super(UserRespondingNoError, self).__init__(
        'User responding "no" to "%s".' % question)


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
      logger.debug('Killing pid=%s with %s', proc.pid, sig)
      # Process leader id is the group id.
      os.killpg(proc.pid, sig)

      # Wait for any shutdown stacktrace to be dumped.
      time.sleep(3)

    raise KillProcessFailedError(proc.args, proc.pid)
  except OSError as e:
    if e.errno != NO_SUCH_PROCESS_ERRNO:
      raise


def edit_if_needed(content, prefix, comment, should_edit):
  """Edit content in an editor if should_edit is true."""
  if not should_edit:
    return content

  return editor.edit(content, prefix=prefix, comment=comment)


def check_binary(binary, cwd):
  """Check if the binary exists."""
  try:
    subprocess.check_output(['which', binary], cwd=cwd)
  except subprocess.CalledProcessError:
    raise NotInstalledError(binary)


class Stdin(object):
  """Represent different ways of setting Popen's stdin."""

  def get(self):
    """Get the stdin handler for Popen."""
    raise NotImplementedError

  def update_cmd_log(self, cmd):
    """Modify the command to represent the stdin in logs."""
    raise NotImplementedError


class BlockStdin(Stdin):
  """Blocking input as opposed to accepting user's input."""

  def get(self):
    """Return subprocess.PIPE because it'll open a new buffer."""
    return subprocess.PIPE

  def update_cmd_log(self, cmd):
    """Return cmd because blocking input doesn't alter
      the command."""
    return cmd


class UserStdin(Stdin):
  """Accept user's input as stdin."""

  def get(self):
    """Return None because that's how it works."""
    return None

  def update_cmd_log(self, cmd):
    """Return cmd because accepting user's input doesn't alter
      the command."""
    return cmd


class StringStdin(Stdin):
  """Send a string as stdin."""

  def __init__(self, input_str):
    self.input_str = input_str
    self.stdin = tempfile.NamedTemporaryFile(delete=False)
    self.stdin.write(input_str)
    self.stdin.flush()
    self.stdin.seek(0)

  def get(self):
    """Get the file handler for the string."""
    return self.stdin

  def update_cmd_log(self, cmd):
    """Add the input filename to the command."""
    return '%s < %s' % (cmd, self.stdin.name)


def start_execute(
    binary, args, cwd, env=None, print_command=True, stdin=None,
    preexec_fn=os.setsid, redirect_stderr_to_stdout=False):
  """Runs a command, and returns the subprocess.Popen object."""
  check_binary(binary, cwd)

  command = (binary + ' ' + args).strip()
  env = env or {}
  stdin = stdin or UserStdin()

  # See https://github.com/google/clusterfuzz-tools/issues/199 why we need this.
  sanitized_env = {}
  for k, v in env.iteritems():
    if v is not None:
      sanitized_env[str(k)] = str(v)

  env_str = ' '.join(
      ['%s="%s"' % (k, v) for k, v in sanitized_env.iteritems()])

  log = colorize(
      stdin.update_cmd_log(
          'Running: %s' % ' '.join([env_str, command]).strip()),
      BASH_BLUE_MARKER)
  if print_command:
    logger.info(log)
  else:
    logger.debug(log)

  final_env = os.environ.copy()
  final_env.update(sanitized_env)

  proc = subprocess.Popen(
      command,
      shell=True,
      stdin=stdin.get(),
      stdout=subprocess.PIPE,
      stderr=(
          subprocess.STDOUT if redirect_stderr_to_stdout else subprocess.PIPE),
      cwd=cwd,
      env=final_env,
      preexec_fn=preexec_fn)

  setattr(proc, 'args', command)
  return proc


def wait_execute(proc, exit_on_error, capture_output=True, print_output=True,
                 timeout=None, stdout_transformer=None,
                 stderr_transformer=None,
                 read_buffer_length=DEFAULT_READ_BUFFER_LENGTH):
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
  for chunk in iter(lambda: proc.stdout.read(read_buffer_length), b''):
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

  for (transformer, data) in [(stdout_transformer, stdout_data or ''),
                              (stderr_transformer, stderr_data or '')]:
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
      raise CommandFailedError(proc.args, proc.returncode, stderr_data)
  return proc.returncode, ''.join(output_chunks)


def execute(binary, args, cwd, print_command=True, print_output=True,
            capture_output=True, exit_on_error=True, env=None,
            stdout_transformer=None, stderr_transformer=None, timeout=None,
            stdin=None, preexec_fn=os.setsid,
            redirect_stderr_to_stdout=False,
            read_buffer_length=DEFAULT_READ_BUFFER_LENGTH):
  """Execute a bash command."""
  proc = start_execute(
      binary, args, cwd, env=env, print_command=print_command,
      stdin=stdin, preexec_fn=preexec_fn,
      redirect_stderr_to_stdout=redirect_stderr_to_stdout)
  return wait_execute(
      proc=proc, exit_on_error=exit_on_error, capture_output=capture_output,
      print_output=print_output, timeout=timeout,
      stdout_transformer=stdout_transformer,
      stderr_transformer=stderr_transformer,
      read_buffer_length=read_buffer_length)


def check_confirm(question):
  """Exits the program if the answer is negative, does nothing otherwise."""
  if not confirm(question):
    raise UserRespondingNoError(question)


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

  answer = raw_input(colorize(
      '%s %s: ' % (question, defaults), BASH_MAGENTA_MARKER)).lower().strip()
  while not answer in accepts:
    answer = raw_input(colorize(
        'Please type either "y" or "n": ', BASH_MAGENTA_MARKER)).lower().strip()

  if answer == 'y' or (answer == '' and default == 'y'):
    return True
  return False


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


def gsutil(*args, **kwargs):
  """Run gsutil and raise an elaborated exception if gsutil doesn't exist."""
  try:
    return execute('gsutil', *args, **kwargs)
  except NotInstalledError:
    raise GsutilNotInstalledError()
