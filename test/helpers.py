"""Helper methods and classes to be used by all tests."""
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
import mock
from pyfakefs import fake_filesystem_unittest


# _Object is needed because we want to add attribute to its instance.
class _Object(object):
  pass

class ExtendedTestCase(fake_filesystem_unittest.TestCase):
  """An extended version of TestCase with extra methods for fine-grained method
  call assertions."""

  def mock_os_environment(self, environ):
    """Mock the OS environment with a provided dictionary."""

    patcher = mock.patch.dict('os.environ', environ)
    patcher.start()
    self.addCleanup(patcher.stop)

  def setup_fake_filesystem(self):
    """Sets up PyFakefs and creates aliases for filepaths."""

    self.setUpPyfakefs()
    self.clusterfuzz_dir = os.path.expanduser(os.path.join(
        '~', '.clusterfuzz'))
    self.auth_header_file = os.path.join(self.clusterfuzz_dir,
                                         'auth_header')

  def assert_file_permissions(self, filename, permissions):
    """Assert that 'filename' has specific permissions"""

    self.assertEqual(int(oct(os.stat(filename).st_mode & 0777)[-3:]),
                     permissions)

  def assert_n_calls(self, n, methods):
    """Assert that all patched methods in 'methods' have been called n times"""

    for m in methods:
      self.assertEqual(n, m.call_count)

  def assert_exact_calls(self, method, calls):
    """Assert that 'method' only has calls defined in 'calls', and no others"""

    method.assert_has_calls(calls)
    self.assertEqual(len(calls), method.call_count)


def patch(testcase_obj, names):
  """Patch names and add them as attributes to testcase_obj. For example,
    `patch(obj, ['a.b.function', ('function2', 'c.d.method')])` adds the
    attributes `mock.function` and `mock.function2` to `obj`.

    To provide a replacement function for a mocked one, use `side_effect`
    attribute, for example:
    `self.mock.function.side_effect = replacementFunctionForTests.`"""
  if not hasattr(testcase_obj, 'mock'):
    setattr(testcase_obj, 'mock', _Object())

  for name in names:
    if isinstance(name, tuple):
      attr_name = name[0]
      full_path = name[1]
    else:
      attr_name = name.split('.')[-1]
      full_path = name

    patcher = mock.patch(full_path, autospec=True, spec_set=True)
    testcase_obj.addCleanup(patcher.stop)
    setattr(testcase_obj.mock, attr_name, patcher.start())
