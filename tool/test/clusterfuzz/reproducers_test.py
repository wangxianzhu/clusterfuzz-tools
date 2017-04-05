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
import json
import mock

from test import helpers
from clusterfuzz import reproducers
from clusterfuzz import common

def patch_stacktrace_info(obj):
  """Patches get_stacktrace_info for initializing a Reproducer."""

  patcher = mock.patch('requests.post',
                       return_value=mock.Mock(text=json.dumps({
                           'crash_state': 'original\nstate',
                           'crash_type': 'original_type'})))
  patcher.start()
  obj.addCleanup(patcher.stop)


def create_chrome_reproducer():
  """Creates a LinuxChromeJobReproducer for use in testing."""

  binary_provider = mock.Mock(symbolizer_path='/path/to/symbolizer')
  testcase = mock.Mock(gestures=None, stacktrace_lines=[{'content': 'line'}],
                       job_type='job_type')
  reproducer = reproducers.LinuxChromeJobReproducer(
      binary_provider, testcase, 'UBSAN')
  reproducer.args = '--always-opt'
  return reproducer

class SetUpSymbolizersSuppressionsTest(helpers.ExtendedTestCase):
  """Tests the set_up_symbolizers_suppressions method."""

  def setUp(self):
    helpers.patch(self, ['os.path.dirname'])
    self.binary_provider = mock.Mock()
    self.testcase = mock.Mock(gestures=None, stacktrace_lines=[
        {'content': 'line'}], job_type='job_type')
    self.reproducer = reproducers.BaseReproducer(
        self.binary_provider, self.testcase, 'UBSAN')

  def test_set_up_correct_env(self):
    """Ensures all the setup methods work correctly."""

    self.mock.dirname.return_value = '/parent/dir'
    self.reproducer.symbolizer_path = '/parent/dir/llvm-symbolizer'
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
            'external_symbolizer_path': '/parent/dir/llvm-symbolizer',
            'other_option': '1',
            'suppressions': '/parent/dir/suppressions/ubsan_suppressions.txt'},
        'LSAN_OPTIONS': {
            'other': '0',
            'suppressions': '/parent/dir/suppressions/lsan_suppressions.txt',
            'option': '1'},
        'UBSAN_SYMBOLIZER_PATH': '/parent/dir/llvm-symbolizer',
        'DISPLAY': ':0.0'})


class SanitizerOptionsSerializerTest(helpers.ExtendedTestCase):
  """Test the serializer & deserializers for sanitizer options."""

  def setUp(self):
    self.binary_provider = mock.Mock(symbolizer_path='/path/to/symbolizer')
    self.testcase = mock.Mock(gestures=None, stacktrace_lines=[
        {'content': 'line'}], job_type='job_type')
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
        'clusterfuzz.reproducers.Blackbox.__exit__',
        'clusterfuzz.common.get_location',
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.post_run_symbolize'])
    self.mock.get_location.return_value = ('/chrome/source/folder/'
                                           'llvm-symbolizer')
    self.mock.wait_execute.return_value = (0, 'lines')
    self.mock.post_run_symbolize.return_value = 'symbolized'

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
                                environment=env, gestures=None,
                                stacktrace_lines=[{'content': 'line'}],
                                job_type='job_type')
    mocked_testcase.get_testcase_path.return_value = testcase_file
    mocked_provider = mock.Mock()
    self.mock.get_location = '/chrome/source/folder/llvm-symbolizer'
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
                                environment=env, gestures=None,
                                stacktrace_lines=[{'content': 'line'}],
                                job_type='job_type')
    mocked_testcase.get_testcase_path.return_value = testcase_file
    mocked_provider = mock.Mock(
        symbolizer_path='/chrome/source/folder/llvm-symbolizer')
    mocked_provider.get_binary_path.return_value = source

    reproducer = reproducers.LinuxChromeJobReproducer(
        mocked_provider, mocked_testcase, 'UBSAN')
    reproducer.gestures = ['gesture,1', 'gesture,2']
    err, text = reproducer.reproduce_crash()
    self.assertEqual(err, 0)
    self.assertEqual(text, 'symbolized')
    self.assert_exact_calls(self.mock.start_execute, [mock.call(
        ('/chrome/source/folder/d8 --turbo --always-opt --random-seed=12345 '
         '--user-data-dir=/tmp/clusterfuzz-user-profile-data %s/.'
         'clusterfuzz/123456_testcase/testcase.js' % os.path.expanduser('~')),
        '/chrome/source/folder', environment={
            'DISPLAY': ':display',
            'ASAN_OPTIONS': 'option2=false:option1=true',
            'UBSAN_SYMBOLIZER_PATH': '/chrome/source/folder/llvm-symbolizer'})])
    self.assert_exact_calls(self.mock.wait_execute, [mock.call(
        self.mock.start_execute.return_value, exit_on_error=False, timeout=15)])
    self.assert_exact_calls(self.mock.run_gestures, [mock.call(
        reproducer, self.mock.start_execute.return_value, ':display')])

class LinuxChromeJobReproducerTest(helpers.ExtendedTestCase):
  """Tests the extra functions of LinuxUbsanChromeReproducer."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self,
                  ['clusterfuzz.reproducers.BaseReproducer.pre_build_steps'])
    os.makedirs('/tmp/clusterfuzz-user-profile-data')
    patch_stacktrace_info(self)
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
    patch_stacktrace_info(self)
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
        'clusterfuzz.common.execute',
        'time.sleep'])
    patch_stacktrace_info(self)
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
    self.assert_exact_calls(self.mock.sleep, [mock.call(20)])


class GetProcessIdsTest(helpers.ExtendedTestCase):
  """Tests the get_process_ids method."""

  def setUp(self):
    helpers.patch(self, ['psutil.Process',
                         'psutil.pid_exists'])
    patch_stacktrace_info(self)
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
    patch_stacktrace_info(self)
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
    patch_stacktrace_info(self)
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
    patch_stacktrace_info(self)
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

  def test_correct_oserror_exception(self):
    """Ensures the correct exception is raised when Blackbox is not found."""

    def _raise_with_message(*_unused, **_kwunused):
      del _unused, _kwunused #Not used by this method
      raise OSError('[Errno 2] No such file or directory')

    self.mock.Popen.side_effect = _raise_with_message
    self.mock.Xvfb.return_value = mock.Mock(xvfb_cmd=['not_display',
                                                      ':display'])

    with self.assertRaises(common.BlackboxNotInstalledError):
      with reproducers.Blackbox(
          ['--disable-gl-drawing-for-tests']) as display_name:
        self.assertNotEqual(display_name, ':display')

    self.assert_n_calls(0, [self.mock.Popen.return_value.kill,
                            self.mock.sleep,
                            self.mock.Xvfb.return_value.stop])

  def test_incorrect_oserror_exception(self):
    """Ensures OSError raises when message is not Errno 2."""

    self.mock.Popen.side_effect = OSError
    self.mock.Xvfb.return_value = mock.Mock(xvfb_cmd=['not_display',
                                                      ':display'])

    with self.assertRaises(OSError):
      with reproducers.Blackbox(
          ['--disable-gl-drawing-for-tests']) as display_name:
        self.assertNotEqual(display_name, ':display')

    self.assert_n_calls(0, [self.mock.Popen.return_value.kill,
                            self.mock.sleep,
                            self.mock.Xvfb.return_value.stop])

  def test_start_stop_blackbox(self):
    """Tests that the context manager starts/stops xvfbwrapper and blackbox."""

    self.mock.Xvfb.return_value = mock.Mock(xvfb_cmd=['not_display',
                                                      ':display'])

    with reproducers.Blackbox(
        ['--disable-gl-drawing-for-tests']) as display_name:
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

  def test_no_blackbox(self):
    """Tests that the manager doesnt start blackbox when incorrect args."""

    self.mock.Xvfb.return_value = mock.Mock(xvfb_cmd=['not_display',
                                                      ':display'])

    with reproducers.Blackbox(['incorrect']) as display_name:
      self.assertEqual(display_name, None)

    self.assert_n_calls(0, [self.mock.Xvfb,
                            self.mock.Xvfb.return_value.start,
                            self.mock.Xvfb.return_value.stop,
                            self.mock.Popen,
                            self.mock.Popen.return_value.kill,
                            self.mock.sleep])


class ReproduceTest(helpers.ExtendedTestCase):
  """Tests the reproduce method within reproducers."""

  def setUp(self):
    patch_stacktrace_info(self)
    self.reproducer = create_chrome_reproducer()
    helpers.patch(self, [
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.reproduce_crash',
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.post_run_symbolize',
        'requests.post',
        'time.sleep'])
    self.mock.reproduce_crash.return_value = (0, ['stuff'])
    self.mock.post_run_symbolize.return_value = 'stuff'
    self.reproducer.crash_type = 'original_type'
    self.reproducer.crash_state = ['original', 'state']
    self.reproducer.job_type = 'linux_ubsan_chrome'

  def test_bad_stacktrace(self):
    """Tests system exit when the stacktrace doesn't match."""

    wrong_response = {
        'crash_type': 'wrong type',
        'crash_state': 'incorrect\nstate'}
    self.mock.post.side_effect = [
        mock.Mock(text=json.dumps(wrong_response)),
        mock.Mock(text=json.dumps(wrong_response))]

    with self.assertRaises(SystemExit):
      self.reproducer.reproduce(2)

  def test_good_stacktrace(self):
    """Tests functionality when the stacktrace matches"""
    correct_response = {
        'crash_type': 'original_type',
        'crash_state': 'original\nstate'}
    wrong_response = {
        'crash_type': 'wrong type',
        'crash_state': 'incorrect\nstate'}
    self.mock.post.side_effect = [
        mock.Mock(text=json.dumps(wrong_response)),
        mock.Mock(text=json.dumps(correct_response))]

    result = self.reproducer.reproduce(10)
    self.assertTrue(result)
    self.assert_exact_calls(self.mock.reproduce_crash, [
        mock.call(self.reproducer), mock.call(self.reproducer)])


class PostRunSymbolizeTest(helpers.ExtendedTestCase):
  """Tests the post_run_symbolize method."""

  def setUp(self):
    self.reproducer = create_chrome_reproducer()
    self.reproducer.source_directory = '/path/to/chromium'
    helpers.patch(self, ['clusterfuzz.common.start_execute',
                         'clusterfuzz.common.get_location',
                         'os.chmod'])
    self.mock.get_location.return_value = 'asan_sym_proxy.py'
    (self.mock.start_execute.return_value.
     communicate.return_value) = ('symbolized', 0)

  def test_symbolize_output(self):
    """Test to ensure the correct symbolization call are made."""
    output = 'output_lines'

    result = self.reproducer.post_run_symbolize(output)

    self.assert_exact_calls(self.mock.start_execute, [
        mock.call(('/path/to/chromium/tools/valgrind/asan/asan_symbolize.py'),
                  os.path.expanduser('~'),
                  {'LLVM_SYMBOLIZER_PATH': 'asan_sym_proxy.py',
                   'CHROMIUM_SRC': '/path/to/chromium'})])
    self.assert_exact_calls(self.mock.start_execute.return_value.communicate,
                            [mock.call(input='output_lines\x00')])
    self.assert_exact_calls(self.mock.chmod, [
        mock.call('asan_sym_proxy.py', 0755)])
    self.assertEqual(result, 'symbolized')


class StripHtmlTest(helpers.ExtendedTestCase):
  """Test strip_html."""

  def test_strip_html(self):
    """Test strip <a> tag."""
    self.assertEqual(
        ['aa test &'],
        reproducers.strip_html(['aa <a href="sadfsd">test</a> &amp;']))


class RemoveUnsymbolizedStacktraceTest(helpers.ExtendedTestCase):
  """Test remove_unsymbolized_stacktrace."""

  def test_no_unsymbolized_stacktrace(self):
    """Test no unsymbolized stacktrace."""
    self.assertEqual(
        ['aa', 'bb'],
        reproducers.strip_html(['aa', 'bb']))

  def test_unsymbolized_stacktrace(self):
    """Test unsymbolized stacktrace."""
    self.assertEqual(
        ['aa', 'bb'],
        reproducers.remove_unsymbolized_stacktrace([
            'aa',
            'bb',
            '+------Release Build Unsymbolized Stacktrace (diff)------+',
            'cc'
        ]))
