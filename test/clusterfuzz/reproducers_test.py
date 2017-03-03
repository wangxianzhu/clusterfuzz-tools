"""Test the reproducers."""
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
from clusterfuzz import reproducers

class SetUpSymbolizersSuppressionsTest(helpers.ExtendedTestCase):
  """Tests the set_up_symbolizers_suppressions method."""

  def setUp(self):
    helpers.patch(self, ['os.path.dirname'])
    self.binary_provider = mock.Mock(symbolizer_path='/path/to/symbolizer')
    self.testcase = mock.Mock()
    self.reproducer = reproducers.BaseReproducer(
        self.binary_provider, self.testcase, 'UBSAN')

  def test_set_up_correct_env(self):
    """Ensures all the setup methods work correctly."""

    self.mock.dirname.return_value = '/parent/dir'
    self.reproducer.environment = {
        'UBSAN_OPTIONS': ('external_symbolizer_path=/not/correct/path:other_'
                          'option=1:suppressions=/not/correct/path'),
        'LSAN_OPTIONS': 'other=0:suppressions=not/correct/path:option=1'}
    self.reproducer.set_up_symbolizers_suppressions()
    result = self.reproducer.environment
    for i in result:
      if '_OPTIONS' in i:
        result[i] = self.reproducer.deserialize_sanitizer_options(result[i])
    self.assertEqual(result, {
        'UBSAN_OPTIONS': {
            'external_symbolizer_path': '/path/to/symbolizer',
            'other_option': '1',
            'suppressions': '/parent/dir/suppressions/ubsan_suppressions.txt'},
        'LSAN_OPTIONS': {
            'other': '0',
            'suppressions': '/parent/dir/suppressions/lsan_suppressions.txt',
            'option': '1'},
        'UBSAN_SYMBOLIZER_PATH': '/path/to/symbolizer',
        'DISPLAY': ':0.0'})


class SanitizerOptionsSerializerTest(helpers.ExtendedTestCase):
  """Test the serializer & deserializers for sanitizer options."""

  def setUp(self):
    self.binary_provider = mock.Mock(symbolizer_path='/path/to/symbolizer')
    self.testcase = mock.Mock()
    self.reproducer = reproducers.BaseReproducer(
        self.binary_provider, self.testcase, 'UBSAN')

  def test_serialize(self):
    in_dict = {'suppressions': '/a/b/c/d/suppresions.txt',
               'option': '1',
               'symbolizer': 'abcde/llvm-symbolizer'}
    out_str = ('suppressions=/a/b/c/d/suppresions.txt:option=1'
               ':symbolizer=abcde/llvm-symbolizer')

    self.assertEqual(self.reproducer.serialize_sanitizer_options(in_dict),
                     out_str)

  def test_deserialize(self):
    out_dict = {'suppressions': '/a/b/c/d/suppresions.txt',
                'option': '1',
                'symbolizer': 'abcde/llvm-symbolizer'}
    in_str = ('suppressions=/a/b/c/d/suppresions.txt:option=1'
              ':symbolizer=abcde/llvm-symbolizer')

    self.assertEqual(self.reproducer.deserialize_sanitizer_options(in_str),
                     out_dict)

class ReproduceCrashTest(helpers.ExtendedTestCase):
  """Tests the reproduce_crash method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute'])

  def test_reproduce_crash(self):
    """Ensures that the crash reproduction is called correctly."""

    self.mock_os_environment({'ASAN_SYMBOLIZER_PATH': '/llvm/sym/path'})
    testcase_id = 123456
    testcase_file = os.path.expanduser(
        os.path.join('~', '.clusterfuzz', '%s_testcase' % testcase_id,
                     'testcase.js'))
    args = '--turbo --always-opt --random-seed=12345'
    source = '/chrome/source/folder/d8'
    env = {'ASAN_OPTIONS': 'option1=true:option2=false'}
    mocked_testcase = mock.Mock(id=1234, reproduction_args=args,
                                environment=env)
    mocked_testcase.get_testcase_path.return_value = testcase_file
    mocked_provider = mock.Mock(
        symbolizer_path='/chrome/source/folder/llvm-symbolizer')
    mocked_provider.get_binary_path.return_value = source

    reproducer = reproducers.BaseReproducer(mocked_provider, mocked_testcase,
                                            'ASAN')
    reproducer.reproduce_crash()
    self.assert_exact_calls(self.mock.execute, [mock.call(
        '%s %s %s' % (
            '/chrome/source/folder/d8', args, testcase_file),
        '/chrome/source/folder', environment={
            'ASAN_SYMBOLIZER_PATH': '/chrome/source/folder/llvm-symbolizer',
            'ASAN_OPTIONS': 'option2=false:option1=true', 'DISPLAY': ':0.0'},
        exit_on_error=False)])


class LinuxUbsanChromeReproducerTest(ReproduceCrashTest):
  """Tests the extra functions of LinuxUbsanChromeReproducer."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self,
                  ['clusterfuzz.reproducers.BaseReproducer.pre_build_steps'])
    os.makedirs('/tmp/clusterfuzz-user-profile-data')
    self.binary_provider = mock.Mock(symbolizer_path='/path/to/symbolizer')
    self.testcase = mock.Mock()
    self.reproducer = reproducers.LinuxUbsanChromeReproducer(
        self.binary_provider, self.testcase, 'UBSAN')
    self.reproducer.args = '--always-opt'


  def test_reproduce_crash(self):
    """Ensures pre-build steps run correctly."""

    self.reproducer.pre_build_steps()
    self.assertFalse(os.path.exists('/tmp/user-profile-data'))
    self.assert_exact_calls(self.mock.pre_build_steps,
                            [mock.call(self.reproducer)])
    self.assertEqual(
        self.reproducer.args,
        '--always-opt --user-data-dir=/tmp/clusterfuzz-user-profile-data')
