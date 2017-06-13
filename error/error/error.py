"""Expected errors."""

import inspect
import sys


UNKNOWN_EXIT_CODE_ERROR = 'UnknownExitCodeError'


def get_class_name(exit_code):
  """Get class name given an exit code."""
  code_to_klass = {}
  for _, obj in inspect.getmembers(sys.modules[__name__]):
    if inspect.isclass(obj) and obj != ExpectedException:
      if obj.EXIT_CODE not in code_to_klass:
        code_to_klass[obj.EXIT_CODE] = obj.__name__
      else:
        raise Exception(
            '%s and %s have the same exit code.' % (
                code_to_klass[obj.EXIT_CODE], obj.__name__))
  return code_to_klass.get(exit_code, UNKNOWN_EXIT_CODE_ERROR)


class ExpectedException(Exception):
  """A general Exception to extend from."""

  def __init__(self, message, exit_code, extras=None):
    super(ExpectedException, self).__init__(message)
    self.extras = extras
    self.exit_code = exit_code


class MinimizationNotFinishedError(ExpectedException):
  """Raise when the minimize_task failed or hasn't finished yet. When the
    minimization is not finished, we won't find 'Running command: ' in the
    stacktrace."""

  MESSAGE = (
      "The testcase hasn't been minimized yet or cannot be minimized.\n"
      'If the testcase is new, please wait for a few more hours.\n'
      "If we can't minimize the testcase, it means the testcase is "
      'unreproducible and, thus, not supported by this tool.')
  EXIT_CODE = 42

  def __init__(self):
    super(MinimizationNotFinishedError, self).__init__(
        self.MESSAGE, self.EXIT_CODE)


class SanitizerNotProvidedError(ExpectedException):
  """An error to notify when a sanitizer isn't passed to a Definition"""

  MESSAGE = 'A sanitizer must be provided with each Definition.'
  EXIT_CODE = 43

  def __init__(self):
    super(SanitizerNotProvidedError, self).__init__(
        self.MESSAGE, self.EXIT_CODE)


class ClusterfuzzAuthError(ExpectedException):
  """An exception to deal with Clusterfuzz Authentication errors.

  Makes the response dict available for inspection later on when
  the exception is dealt with."""

  MESSAGE = (
      'Error authenticating with Clusterfuzz. '
      'Can you access the testcase on clusterfuzz.com using the same email?'
      '\n{response}')
  EXIT_CODE = 44

  def __init__(self, response):
    super(ClusterfuzzAuthError, self).__init__(
        self.MESSAGE.format(response=str(response)), self.EXIT_CODE)
    self.response = response


class PermissionsTooPermissiveError(ExpectedException):
  """An exception to deal with file permissions errors.

  Stores the filename and the current permissions.."""

  MESSAGE = ('File permissions too permissive to open {filename}\n'
             'Current permissions: {permission}\nExpected user access only'
             '\nYou can run "chmod 600 {filename}filename" to fix this issue')
  EXIT_CODE = 45

  def __init__(self, filename, current_permissions):
    super(PermissionsTooPermissiveError, self).__init__(
        self.MESSAGE.format(filename=filename, permission=current_permissions),
        self.EXIT_CODE)
    self.filename = filename
    self.current_permissions = current_permissions


class GomaNotInstalledError(ExpectedException):
  """An exception to tell people GOMA isn not installed."""

  MESSAGE = ('Either goma is not installed, or $GOMA_DIR is not set.'
             ' Please set up goma before continuing. '
             'See go/ma to learn more.\n\n'
             "If you wouldn't like to use goma, "
             'please re-run with --disable-goma.')
  EXIT_CODE = 46

  def __init__(self):
    super(GomaNotInstalledError, self).__init__(self.MESSAGE, self.EXIT_CODE)


class JobTypeNotSupportedError(ExpectedException):
  """An exception raised when user tries to run an unsupported build type."""

  MESSAGE = 'The job {job_type} is not yet supported by clusterfuzz tools.'
  EXIT_CODE = 47

  def __init__(self, job_type):
    super(JobTypeNotSupportedError, self).__init__(
        self.MESSAGE.format(job_type=job_type), self.EXIT_CODE)


class NotInstalledError(ExpectedException):
  """An exception raised to tell the user to install the required binary."""

  MESSAGE = (
      '{binary} is not found. Please install it or ensure the path is '
      'correct.\n'
      'Most of the time you can install it with `apt-get install {binary}`.')
  EXIT_CODE = 48

  def __init__(self, binary):
    super(NotInstalledError, self).__init__(
        self.MESSAGE.format(binary=binary), self.EXIT_CODE)


class GsutilNotInstalledError(ExpectedException):
  """An exception raised to tell the user to install the required binary."""

  MESSAGE = (
      'gsutil is not installed. Please install it. See:'
      'https://cloud.google.com/storage/docs/gsutil_install')
  EXIT_CODE = 49

  def __init__(self):
    super(GsutilNotInstalledError, self).__init__(self.MESSAGE, self.EXIT_CODE)


class BadJobTypeDefinitionError(ExpectedException):
  """An exception raised when a job type description is malformed."""

  MESSAGE = (
      'The definition for the {job_type} job type is incorrectly formatted or'
      ' missing crucial information.')
  EXIT_CODE = 50

  def __init__(self, job_type):
    super(BadJobTypeDefinitionError, self).__init__(
        self.MESSAGE.format(job_type=job_type), self.EXIT_CODE)


class UnreproducibleError(ExpectedException):
  """An exception raised when the testcase cannot be reproduced."""

  MESSAGE = (
      'The testcase cannot be reproduced after trying {count} times.\n'
      'Here are 2 things you can try:\n'
      '- Run with the downloaded build by adding `--build download`.\n'
      '- Run with more number of trials by adding `-i 10`, '
      'which is especially good for gesture-related testcases.')
  EXIT_CODE = 51

  def __init__(self, count, crash_signatures):
    crash_signatures = [
        {'type': s.crash_type, 'state': s.crash_state_lines,
         'output': s.output[:100000]}
        for s in list(crash_signatures)[:10]
    ]
    super(UnreproducibleError, self).__init__(
        message=self.MESSAGE.format(count=count),
        exit_code=self.EXIT_CODE,
        extras={'signatures': crash_signatures})


class DirtyRepoError(ExpectedException):
  """An exception raised when the repo is dirty. Therefore, we cannot checkout
    to a wanted sha."""

  MESSAGE = (
      "We can't run the checkout command because {source_dir} has "
      'uncommitted changes.\n '
      'please commit or stash these changes and re-run this tool.')
  EXIT_CODE = 52

  def __init__(self, source_dir):
    super(DirtyRepoError, self).__init__(
        self.MESSAGE.format(source_dir=source_dir), self.EXIT_CODE)

class CommandFailedError(ExpectedException):
  """An exception raised when the command doesn't return 0."""

  MESSAGE = '`{cmd}` failed with the return code {returncode}.'
  EXIT_CODE = 53

  def __init__(self, command, returncode, stderr):
    super(CommandFailedError, self).__init__(
        self.MESSAGE.format(cmd=command, returncode=returncode),
        self.EXIT_CODE,
        extras={'stderr': stderr[:100000]})


class KillProcessFailedError(ExpectedException):
  """An exception raised when the process cannot be killed."""

  MESSAGE = '`{command}` (pid={pid}) cannot be killed.'
  EXIT_CODE = 54

  def __init__(self, command, pid):
    super(KillProcessFailedError, self).__init__(
        self.MESSAGE.format(command=command, pid=pid),
        self.EXIT_CODE)


class UserRespondingNoError(ExpectedException):
  """An exception raised when the user decides not to proceed."""

  MESSAGE = 'User responding "no" to "{question}"'
  EXIT_CODE = 55

  def __init__(self, question):
    super(UserRespondingNoError, self).__init__(
        self.MESSAGE.format(question=question),
        self.EXIT_CODE)
