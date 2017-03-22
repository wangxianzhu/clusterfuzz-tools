"""Test the 'testcase' module and class."""
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

from test import helpers
from clusterfuzz import testcase

def build_base_testcase(stacktrace_lines=None, revision=None, build_url=None,
                        window_arg='', minimized_args='', extension='.js',
                        gestures=None):
  """Builds a testcase instance that can be used for testing."""
  if extension is not None:
    extension = '.%s' % extension
  else:
    extension = ''
  if stacktrace_lines is None:
    stacktrace_lines = []
  testcase_json = {
      'id': '12345',
      'crash_stacktrace': {'lines': stacktrace_lines},
      'crash_type': 'bad_crash',
      'crash_state': 'halted',
      'crash_revision': revision,
      'metadata': {'build_url': build_url},
      'testcase': {'window_argument': window_arg,
                   'job_type': 'linux_asan_d8_dbg',
                   'one_time_crasher_flag': False,
                   'minimized_arguments': minimized_args,
                   'absolute_path': '/absolute/path%s' % extension}}
  if gestures:
    testcase_json['testcase']['gestures'] = []

  return testcase.Testcase(testcase_json)


class TestcaseFileExtensionTest(helpers.ExtendedTestCase):
  """Tests the file extension parsing."""

  def test_no_extension(self):
    """Tests functionality when the testcase has no extension."""

    test = build_base_testcase(extension=None)
    self.assertEqual(test.file_extension, '')

  def test_with_extension(self):
    """Tests functionality when the testcase has an extension."""

    test = build_base_testcase(extension='py')
    self.assertEqual(test.file_extension, '.py')



class TestcaseSetupTest(helpers.ExtendedTestCase):
  """Tests populating the testcase parameters."""

  def test_parsing_json(self):
    """Ensures the JSON is parsed correctly."""

    stacktrace_lines = [
        {'content': '[Environment] TEST_ARGS = first=1:second=2'},
        {'content': 'Not an env line'},
        {'content': '[Environment] ASAN_OPTIONS = x=1:symbolize=0'},
        {'content': '[Environment] LSAN_OPTIONS = y=1'},
        {'content': ('Running command: /path/to/binary --random-seed=23 '
                     '--turbo /path/to/testcase')},
        {'content': '[Environment] TEST_TWO = third=3:fourth=4'}]
    result = build_base_testcase(
        stacktrace_lines=stacktrace_lines, revision=5, build_url='build_url',
        gestures=True)
    self.assertEqual(result.id, '12345')
    self.assertEqual(result.revision, 5)
    self.assertEqual(result.environment, {'TEST_ARGS': 'first=1:second=2',
                                          'TEST_TWO': 'third=3:fourth=4',
                                          'ASAN_OPTIONS': 'x=1:symbolize=1',
                                          'LSAN_OPTIONS': 'y=1:symbolize=1'})
    self.assertEqual(result.reproduction_args, '--random-seed=23 --turbo')
    self.assertEqual(result.build_url, 'build_url')
    self.assertTrue(result.reproducible)
    self.assertEqual(result.gestures, [])


class GetTestcasePathTest(helpers.ExtendedTestCase):
  """Tests the get_testcase_path method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.get_stored_auth_header',
        'clusterfuzz.common.execute',
        'os.listdir',
        'clusterfuzz.testcase.Testcase.get_true_testcase_file'])
    self.mock.get_stored_auth_header.return_value = 'Bearer 1a2s3d4f'
    self.testcase_dir = os.path.expanduser(os.path.join(
        '~', '.clusterfuzz', 'testcases', '12345_testcase'))
    self.test = build_base_testcase()

  def test_already_downloaded(self):
    """Tests the scenario in which the testcase is already downloaded."""

    filename = os.path.join(self.testcase_dir, 'testcase.js')
    os.makedirs(self.testcase_dir)
    with open(filename, 'w') as f:
      f.write('testcase exists')
    self.assertTrue(os.path.isfile(filename))

    result = self.test.get_testcase_path()
    self.assertEqual(result, filename)
    self.assert_n_calls(0, [self.mock.get_stored_auth_header,
                            self.mock.execute])

  def test_not_already_downloaded(self):
    """Tests the creation of folders & downloading of the testcase"""

    def do_wget(*unused_args):
      with open(os.path.join(testcase.CLUSTERFUZZ_TESTCASES_DIR,
                             '12345_testcase/testcase.js'), 'w') as f:
        f.write('Fake testcase')
    self.mock.execute.side_effect = do_wget
    filename = os.path.join(self.testcase_dir, 'testcase.js')
    self.mock.get_true_testcase_file.return_value = filename
    self.assertFalse(os.path.exists(self.testcase_dir))

    result = self.test.get_testcase_path()

    self.assertEqual(result, filename)
    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.execute, [mock.call(
        ('wget --content-disposition --header="Authorization: %s" "%s"' %
         (self.mock.get_stored_auth_header.return_value,
          testcase.CLUSTERFUZZ_TESTCASE_URL % str(12345))),
        self.testcase_dir)])
    self.assertTrue(os.path.exists(self.testcase_dir))


class GetTrueTestcaseFileTest(helpers.ExtendedTestCase):
  """Tests the get_true_testcase_file method."""

  def setUp(self):
    helpers.patch(self, ['zipfile.ZipFile',
                         'os.rename'])
    self.test = build_base_testcase()
    self.mock.ZipFile.return_value = mock.Mock()

  def test_zipfile(self):
    """Tests when the file is a zipfile."""
    self.test.absolute_path = '/absolute/path/to/wrong_testcase.js'
    self.test.get_true_testcase_file('abcd.zip')

    self.mock.ZipFile.assert_has_calls([
        mock.call(os.path.expanduser(
            '~/.clusterfuzz/testcases/12345_testcase/abcd.zip'), 'r'),
        mock.call().extractall(
            os.path.expanduser('~/.clusterfuzz/testcases/12345_testcase'))])
    testcase_dir = os.path.expanduser(
        '~/.clusterfuzz/testcases/12345_testcase/')
    self.assert_exact_calls(self.mock.rename, [
        mock.call(os.path.join(testcase_dir, 'wrong_testcase.js'),
                  os.path.join(testcase_dir, 'testcase.js'))])

  def test_no_zipfile(self):
    """Tests when the downloaded file is not zipped."""

    self.test.absolute_path = '/absolute/path/to/wrong_testcase.js'
    self.test.get_true_testcase_file('abcd.js')

    self.assert_n_calls(0, [self.mock.ZipFile])
    testcase_dir = os.path.expanduser(
        '~/.clusterfuzz/testcases/12345_testcase/')
    self.assert_exact_calls(self.mock.rename, [
        mock.call(os.path.join(testcase_dir, 'abcd.js'),
                  os.path.join(testcase_dir, 'testcase.js'))])
