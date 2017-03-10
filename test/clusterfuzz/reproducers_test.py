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

def create_chrome_reproducer():
  """Creates a LinuxChromeJobReproducer for use in testing."""

  binary_provider = mock.Mock(symbolizer_path='/path/to/symbolizer')
  testcase = mock.Mock(gestures=None)
  reproducer = reproducers.LinuxChromeJobReproducer(
      binary_provider, testcase, 'UBSAN')
  reproducer.args = '--always-opt'
  return reproducer

class SetUpSymbolizersSuppressionsTest(helpers.ExtendedTestCase):
  """Tests the set_up_symbolizers_suppressions method."""

  def setUp(self):
    helpers.patch(self, ['os.path.dirname'])
    self.binary_provider = mock.Mock(symbolizer_path='/path/to/symbolizer')
    self.testcase = mock.Mock(gestures=None)
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
    self.testcase = mock.Mock(gestures=None)
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
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.start_execute', 'clusterfuzz.common.wait_execute',
        'clusterfuzz.common.execute',
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.run_gestures',
        'clusterfuzz.reproducers.Blackbox.__enter__',
        'clusterfuzz.reproducers.Blackbox.__exit__'])

  def test_base_reproduce_crash(self):
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
                                environment=env, gestures=None)
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

  def test_reproduce_crash(self):
    """Ensures that the crash reproduction is called correctly."""

    self.mock_os_environment({'ASAN_SYMBOLIZER_PATH': '/llvm/sym/path'})
    self.mock.start_execute.return_value = mock.Mock
    self.mock.__enter__.return_value = ':display'
    testcase_id = 123456
    testcase_file = os.path.expanduser(
        os.path.join('~', '.clusterfuzz', '%s_testcase' % testcase_id,
                     'testcase.js'))
    args = '--turbo --always-opt --random-seed=12345'
    source = '/chrome/source/folder/d8'
    env = {'ASAN_OPTIONS': 'option1=true:option2=false'}
    mocked_testcase = mock.Mock(id=1234, reproduction_args=args,
                                environment=env, gestures=None)
    mocked_testcase.get_testcase_path.return_value = testcase_file
    mocked_provider = mock.Mock(
        symbolizer_path='/chrome/source/folder/llvm-symbolizer')
    mocked_provider.get_binary_path.return_value = source

    reproducer = reproducers.LinuxChromeJobReproducer(
        mocked_provider, mocked_testcase, 'UBSAN')
    reproducer.gestures = ['gesture,1', 'gesture,2']
    reproducer.reproduce_crash()
    self.assert_exact_calls(self.mock.start_execute, [mock.call(
        ('/chrome/source/folder/d8 --turbo --always-opt --random-seed=12345 '
         '--user-data-dir=/tmp/clusterfuzz-user-profile-data %s/.'
         'clusterfuzz/123456_testcase/testcase.js' % os.path.expanduser('~')),
        '/chrome/source/folder', environment={
            'DISPLAY': ':display',
            'ASAN_OPTIONS': 'option2=false:option1=true',
            'UBSAN_SYMBOLIZER_PATH': '/chrome/source/folder/llvm-symbolizer'})])
    self.assert_exact_calls(self.mock.wait_execute, [mock.call(
        self.mock.start_execute.return_value, exit_on_error=False)])
    self.assert_exact_calls(self.mock.run_gestures, [mock.call(
        reproducer, self.mock.start_execute.return_value, ':display')])

class LinuxChromeJobReproducerTest(helpers.ExtendedTestCase):
  """Tests the extra functions of LinuxUbsanChromeReproducer."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self,
                  ['clusterfuzz.reproducers.BaseReproducer.pre_build_steps'])
    os.makedirs('/tmp/clusterfuzz-user-profile-data')
    self.reproducer = create_chrome_reproducer()

  def test_reproduce_crash(self):
    """Ensures pre-build steps run correctly."""

    self.reproducer.pre_build_steps()
    self.assertFalse(os.path.exists('/tmp/user-profile-data'))
    self.assert_exact_calls(self.mock.pre_build_steps,
                            [mock.call(self.reproducer)])
    self.assertEqual(
        self.reproducer.args,
        '--always-opt --user-data-dir=/tmp/clusterfuzz-user-profile-data')

class XdotoolCommandTest(helpers.ExtendedTestCase):
  """Tests the xdotool_command method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.start_execute',
                         'clusterfuzz.common.wait_execute'])
    self.mock.start_execute.return_value = mock.Mock()
    self.reproducer = create_chrome_reproducer()

  def test_call(self):
    """Tests calling the method."""

    self.reproducer.xdotool_command('command to run', ':2753')
    self.assert_exact_calls(self.mock.start_execute, [mock.call(
        'xdotool command to run', os.path.expanduser('~'),
        environment={'DISPLAY': ':2753'})])
    self.assert_exact_calls(self.mock.wait_execute, [mock.call(
        self.mock.start_execute.return_value, exit_on_error=False,
        capture_output=False, print_output=False)])


class FindWindowsForProcessTest(helpers.ExtendedTestCase):
  """Tests the find_windows_for_process method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.get_process_ids',
        'clusterfuzz.common.execute'])
    self.reproducer = create_chrome_reproducer()

  def test_no_pids(self):
    """Tests when no PIDs are available."""

    self.mock.get_process_ids.return_value = []

    self.reproducer.find_windows_for_process(1234, ':45434')
    self.assert_n_calls(0, [self.mock.execute])

  def test_dedup_pids(self):
    """Tests when duplicate pids are introduced."""

    self.mock.get_process_ids.return_value = [1234, 5678]
    self.mock.execute.side_effect = [(0, '234\n567\nabcd\n890'),
                                     (0, '123\n567\n345')]

    result = self.reproducer.find_windows_for_process(1234, ':45434')
    self.assertEqual(result, set(['234', '567', '890', '123', '345']))


class GetProcessIdsTest(helpers.ExtendedTestCase):
  """Tests the get_process_ids method."""

  def setUp(self):
    helpers.patch(self, ['psutil.Process',
                         'psutil.pid_exists'])
    self.reproducer = create_chrome_reproducer()

  def test_process_not_running(self):
    """Tests exiting when psutil is not supported."""
    self.mock.pid_exists.return_value = False

    result = self.reproducer.get_process_ids(1234)
    self.assertEqual(result, [])
    self.assert_n_calls(0, [self.mock.Process])

  def test_psutil_working(self):
    """Tests grabbing process IDs when process is running."""

    self.mock.pid_exists.return_value = True
    psutil_handle = mock.Mock()
    psutil_handle.children.return_value = [mock.Mock(pid=123),
                                           mock.Mock(pid=456)]
    self.mock.Process.return_value = psutil_handle

    result = self.reproducer.get_process_ids(1234)
    self.assertEqual(result, [1234, 123, 456])

  def _raise(self, _):
    raise Exception('Oops')

  def test_exception_handling(self):
    """Tests functionality when an exception is raised."""

    self.mock.Process.side_effect = self._raise

    with self.assertRaises(Exception):
      self.reproducer.get_process_ids(1234)


class RunGesturesTest(helpers.ExtendedTestCase):
  """Tests the run_gestures method."""

  def setUp(self):
    helpers.patch(self, [
        'time.sleep',
        ('clusterfuzz.reproducers.LinuxChromeJobReproducer.get_gesture_start_'
         'time'),
        ('clusterfuzz.reproducers.LinuxChromeJobReproducer.find_windows_for'
         '_process'),
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.xdotool_command',
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.execute_gesture'])
    self.reproducer = create_chrome_reproducer()
    self.mock.get_gesture_start_time.return_value = 5
    self.mock.find_windows_for_process.return_value = ['123']
    self.reproducer.gestures = ['windowsize,2', 'type,\'ValeM1khbW4Gt!\'',
                                'Trigger:2']
    self.reproducer.gesture_start_time = 5

  def test_execute_gestures(self):
    """Tests executing the gestures."""

    self.reproducer.run_gestures(mock.Mock(pid=1234), ':display')

    self.assert_exact_calls(self.mock.xdotool_command, [
        mock.call(self.reproducer, 'windowactivate --sync 123', ':display')])
    self.assert_exact_calls(self.mock.sleep, [mock.call(5)])


class GetGestureStartTimeTest(helpers.ExtendedTestCase):
  """Test the get_gesture_start_time method."""

  def setUp(self):
    self.reproducer = create_chrome_reproducer()

  def test_with_trigger(self):
    self.reproducer.gestures = ['windowsize,2', 'type,\'ValeM1khbW4Gt!\'',
                                'Trigger:2']
    result = self.reproducer.get_gesture_start_time()
    self.assertEqual(result, 2)

  def test_no_trigger(self):
    self.reproducer.gestures = ['windowsize,2', 'type,\'ValeM1khbW4Gt!\'']
    result = self.reproducer.get_gesture_start_time()
    self.assertEqual(result, 5)


class ExecuteGestureTest(helpers.ExtendedTestCase):
  """Test the execute_gesture method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.xdotool_command'])
    self.reproducer = create_chrome_reproducer()
    self.reproducer.gestures = ['windowsize,2', 'type,\'ValeM1khbW4Gt!\'']

  def test_call_execute_gesture(self):
    """Test parsing gestures."""

    for gesture in self.reproducer.gestures:
      self.reproducer.execute_gesture(gesture, '12345', ':display')

    self.assert_exact_calls(self.mock.xdotool_command, [
        mock.call(self.reproducer, 'windowsize 12345 2', ':display'),
        mock.call(self.reproducer, 'type -- \'ValeM1khbW4Gt!\'', ':display')])


class BlackboxTest(helpers.ExtendedTestCase):
  """Used to test the Blackbox context manager."""

  def setUp(self):
    helpers.patch(self, ['xvfbwrapper.Xvfb',
                         'subprocess.Popen',
                         'time.sleep'])

  def test_start_stop_blackbox(self):
    """Tests that the context manager starts/stops xvfbwrapper and blackbox."""

    self.mock.Xvfb.return_value = mock.Mock(xvfb_cmd=['not_display',
                                                      ':display'])

    with reproducers.Blackbox() as display_name:
      self.assertEqual(display_name, ':display')

    self.assert_exact_calls(self.mock.Xvfb, [mock.call(
        width=1280, height=1024)])
    self.assert_exact_calls(self.mock.Xvfb.return_value.start, [mock.call()])
    self.assert_exact_calls(self.mock.Xvfb.return_value.stop,
                            [mock.call.stop()])
    self.assert_exact_calls(self.mock.Popen, [
        mock.call(['blackbox'], env={'DISPLAY': ':display'})])
    self.assert_exact_calls(self.mock.Popen.return_value.kill, [mock.call()])
    self.assert_exact_calls(self.mock.sleep, [mock.call(30)])
