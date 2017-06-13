"""Tests for error."""

import collections

from error import error
from test_libs import helpers


class FakeException(error.ExpectedException):
  """FakeException."""

  EXIT_CODE = 100


class AnotherFakeException(error.ExpectedException):
  """AnotherFakeException."""

  EXIT_CODE = 100


class GetClassNameTest(helpers.ExtendedTestCase):
  """Test get_class_name."""

  def test_get_by_code(self):
    """Get each class by exit code."""
    self.assertEqual(
        error.MinimizationNotFinishedError.__name__,
        error.get_class_name(error.MinimizationNotFinishedError.EXIT_CODE))
    self.assertEqual(
        error.UserRespondingNoError.__name__,
        error.get_class_name(error.UserRespondingNoError.EXIT_CODE))

  def test_get_unknown(self):
    """Get UnknownException."""
    self.assertEqual(
        error.UNKNOWN_EXIT_CODE_ERROR, error.get_class_name(9999))

  def test_same_exit_code(self):
    """Test some classes having the same exit code."""
    helpers.patch(self, ['inspect.getmembers'])
    self.mock.getmembers.return_value = [
        (FakeException.__name__, FakeException),
        (AnotherFakeException.__name__, AnotherFakeException)]

    with self.assertRaises(Exception) as cm:
      error.get_class_name(500)

    self.assertEqual(
        'FakeException and AnotherFakeException have the same exit code.',
        cm.exception.message)


Signature = collections.namedtuple(
    'Signature', ['crash_type', 'crash_state_lines', 'output'])


class InitTest(helpers.ExtendedTestCase):
  """Test initialize all types of Exception."""

  def test_init(self):
    """Test init."""
    error.MinimizationNotFinishedError()
    error.SanitizerNotProvidedError()
    error.ClusterfuzzAuthError('resp')
    error.PermissionsTooPermissiveError('filename', 'perm')
    error.GomaNotInstalledError()
    error.JobTypeNotSupportedError('job')
    error.NotInstalledError('bin')
    error.GsutilNotInstalledError()
    error.BadJobTypeDefinitionError('job')
    error.UnreproducibleError(10, [Signature('type', ['a', 'b'], 'output')])
    error.DirtyRepoError('source')
    error.CommandFailedError('cmd', 12, 'err')
    error.KillProcessFailedError('cmd', 123)
    error.UserRespondingNoError('question')
