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

import helpers
from clusterfuzz import common
from clusterfuzz import output_transformer
from clusterfuzz import reproducers
from tests import libs

def patch_stacktrace_info(obj):
  """Patches get_stacktrace_info for initializing a Reproducer."""

  patcher = mock.patch('clusterfuzz.common.post',
                       return_value=mock.Mock(text=json.dumps({
                           'crash_state': 'original\nstate',
                           'crash_type': 'original_type'})))
  patcher.start()
  obj.addCleanup(patcher.stop)


def create_reproducer(klass):
  """Creates a LinuxChromeJobReproducer for use in testing."""

  binary_provider = mock.Mock(symbolizer_path='/path/to/symbolizer')
  binary_provider.get_binary_path.return_value = '/fake/build_dir/test_binary'
  binary_provider.get_build_directory.return_value = '/fake/build_dir'
  testcase = mock.Mock(gestures=None, stacktrace_lines=[{'content': 'line'}],
                       job_type='job_type', reproduction_args='--original')
  reproducer = klass(
      definition=mock.Mock(),
      binary_provider=binary_provider,
      testcase=testcase,
      sanitizer='UBSAN',
      options=libs.make_options(target_args='--test'))
  reproducer.args = '--always-opt'
  reproducer.environment = {}
  reproducer.source_directory = '/fake/source_dir'
  reproducer.original_testcase_path = '/fake/original_testcase_dir/testcase'
  reproducer.testcase_path = '/fake/testcase_dir/testcase'
  return reproducer

class SetUpSymbolizersSuppressionsTest(helpers.ExtendedTestCase):
  """Tests the set_up_symbolizers_suppressions method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.get_resource'
    ])

  def test_set_up_correct_env(self):
    """Ensures all the setup methods work correctly."""
    root_path = '/fake'
    self.fs.CreateFile('/fake/resources/llvm-symbolizer', contents='t')
    self.fs.CreateFile(
        '/fake/resources/suppressions/lsan_suppressions.txt', contents='t')
    self.fs.CreateFile(
        '/fake/resources/suppressions/ubsan_suppressions.txt', contents='t')

    def get(_, *paths):
      return os.path.join(root_path, *paths)
    self.mock.get_resource.side_effect = get

    self.binary_provider = mock.Mock()
    self.definition = mock.Mock()
    self.testcase = mock.Mock(gestures=None, stacktrace_lines=[
        {'content': 'line'}], job_type='job_type', reproduction_args='--orig')
    self.reproducer = reproducers.BaseReproducer(
        self.definition, self.binary_provider, self.testcase, 'UBSAN',
        libs.make_options(target_args='--test'))

    self.reproducer.environment = {
        'UBSAN_OPTIONS': ('external_symbolizer_path=/not/correct/path:other_'
                          'option=1:suppressions=/not/correct/path:'
                          'coverage_dir=test'),
        'LSAN_OPTIONS': 'other=0:suppressions=not/correct/path:option=1'}
    self.reproducer.set_up_symbolizers_suppressions()
    result = self.reproducer.environment
    for i in result:
      if '_OPTIONS' in i:
        result[i] = reproducers.deserialize_sanitizer_options(result[i])
    self.assertEqual(result, {
        'UBSAN_OPTIONS': {
            'external_symbolizer_path':
                '%s/resources/llvm-symbolizer' % root_path,
            'other_option': '1',
            'suppressions': (
                '%s/resources/suppressions/ubsan_suppressions.txt' % root_path)
        },
        'LSAN_OPTIONS': {
            'other': '0',
            'suppressions': (
                '%s/resources/suppressions/lsan_suppressions.txt' % root_path),
            'option': '1'},
        'UBSAN_SYMBOLIZER_PATH':
            '%s/resources/llvm-symbolizer' % root_path,
        'DISPLAY': ':0.0'})


class SanitizerOptionsSerializerTest(helpers.ExtendedTestCase):
  """Test the serializer & deserializers for sanitizer options."""

  def test_serialize(self):
    in_dict = {'suppressions': '/a/b/c/d/suppresions.txt',
               'option': '1',
               'symbolizer': 'abcde/llvm-symbolizer'}
    out_str = ('suppressions=/a/b/c/d/suppresions.txt:option=1'
               ':symbolizer=abcde/llvm-symbolizer')

    self.assertEqual(reproducers.serialize_sanitizer_options(in_dict), out_str)

  def test_deserialize(self):
    out_dict = {'suppressions': '/a/b/c/d/suppresions.txt',
                'option': '1',
                'symbolizer': 'abcde/llvm-symbolizer'}
    in_str = ('suppressions=/a/b/c/d/suppresions.txt:option=1'
              ':symbolizer=abcde/llvm-symbolizer')

    self.assertEqual(
        reproducers.deserialize_sanitizer_options(in_str), out_dict)

class ReproduceCrashTest(helpers.ExtendedTestCase):
  """Tests the reproduce_crash method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.start_execute',
        'clusterfuzz.common.wait_execute',
        'clusterfuzz.common.execute',
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.run_gestures',
        'clusterfuzz.reproducers.Xvfb.__enter__',
        'clusterfuzz.reproducers.Xvfb.__exit__',
        'clusterfuzz.common.get_resource',
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.post_run_symbolize'])
    self.mock.get_resource.return_value = (
        '/chrome/source/folder/llvm-symbolizer')
    self.mock.wait_execute.return_value = (0, 'lines')
    self.mock.post_run_symbolize.return_value = 'symbolized'
    self.app_directory = '/chrome/source/folder'
    self.testcase_path = os.path.expanduser(
        os.path.join('~', '.clusterfuzz', '1234_testcase', 'testcase.js'))
    self.definition = mock.Mock()

  def test_base(self):
    """Test base's reproduce_crash."""

    mocked_testcase = mock.Mock(
        id=1234, reproduction_args='--repro',
        environment={'ASAN_OPTIONS': 'test-asan'}, gestures=None,
        stacktrace_lines=[{'content': 'line'}],
        job_type='job_type')
    mocked_testcase.get_testcase_path.return_value = self.testcase_path
    mocked_provider = mock.Mock(
        symbolizer_path='%s/llvm-symbolizer' % self.app_directory)
    mocked_provider.get_binary_path.return_value = '%s/d8' % self.app_directory
    mocked_provider.get_build_directory.return_value = self.app_directory

    reproducer = reproducers.BaseReproducer(
        self.definition, mocked_provider, mocked_testcase, 'UBSAN',
        libs.make_options(target_args='--test'))
    reproducer.setup_args()
    reproducer.reproduce_crash()
    self.assert_exact_calls(self.mock.execute, [
        mock.call(
            '/chrome/source/folder/d8',
            '--repro --test %s' % self.testcase_path,
            '/chrome/source/folder',
            env={'ASAN_OPTIONS': 'test-asan'},
            exit_on_error=False,
            timeout=30,
            stdout_transformer=mock.ANY,
            redirect_stderr_to_stdout=True)
    ])

  def test_base_with_env_args(self):
    """Test base's reproduce_crash with environment args."""

    mocked_testcase = mock.Mock(
        id=1234, reproduction_args='--app-dir=%APP_DIR% --testcase=%TESTCASE%',
        environment={'ASAN_OPTIONS': 'test-asan'}, gestures=None,
        stacktrace_lines=[{'content': 'line'}],
        job_type='job_type')
    mocked_testcase.get_testcase_path.return_value = self.testcase_path
    mocked_provider = mock.Mock(
        symbolizer_path='%s/llvm-symbolizer' % self.app_directory)
    mocked_provider.get_binary_path.return_value = '%s/d8' % self.app_directory
    mocked_provider.get_build_directory.return_value = self.app_directory

    reproducer = reproducers.BaseReproducer(
        self.definition, mocked_provider, mocked_testcase, 'UBSAN',
        libs.make_options(target_args='--test'))
    reproducer.setup_args()
    reproducer.reproduce_crash()
    self.assert_exact_calls(self.mock.execute, [
        mock.call(
            '/chrome/source/folder/d8',
            '--app-dir=%s --testcase=%s --test' % (self.app_directory,
                                                   self.testcase_path),
            '/chrome/source/folder',
            env={'ASAN_OPTIONS': 'test-asan'},
            exit_on_error=False,
            timeout=30,
            stdout_transformer=mock.ANY,
            redirect_stderr_to_stdout=True)
    ])

  def test_chromium(self):
    """Test chromium's reproduce_crash."""

    self.mock.start_execute.return_value = mock.Mock()
    self.mock.__enter__.return_value = ':display'
    mocked_testcase = mock.Mock(
        id=1234, reproduction_args='--repro',
        environment={'ASAN_OPTIONS': 'test-asan'}, gestures=None,
        stacktrace_lines=[{'content': 'line'}],
        job_type='job_type')
    mocked_testcase.get_testcase_path.return_value = self.testcase_path
    mocked_provider = mock.Mock(
        symbolizer_path='%s/llvm-symbolizer' % self.app_directory)
    mocked_provider.get_binary_path.return_value = '%s/d8' % self.app_directory
    mocked_provider.get_build_directory.return_value = self.app_directory

    reproducer = reproducers.LinuxChromeJobReproducer(
        self.definition, mocked_provider, mocked_testcase, 'UBSAN',
        libs.make_options(target_args='--test'))
    reproducer.gestures = ['gesture,1', 'gesture,2']
    reproducer.setup_args()
    err, text = reproducer.reproduce_crash()
    self.assertEqual(err, 0)
    self.assertEqual(text, 'symbolized')
    self.assert_exact_calls(self.mock.start_execute, [
        mock.call(
            '/chrome/source/folder/d8',
            '--repro --test %s' % self.testcase_path,
            '/chrome/source/folder',
            env={
                'DISPLAY': ':display',
                'ASAN_OPTIONS': 'test-asan',
            },
            redirect_stderr_to_stdout=True)
    ])
    self.assert_exact_calls(self.mock.wait_execute, [
        mock.call(
            self.mock.start_execute.return_value, exit_on_error=False,
            timeout=30,
            stdout_transformer=mock.ANY)
    ])
    self.assert_exact_calls(self.mock.run_gestures, [mock.call(
        reproducer, self.mock.start_execute.return_value, ':display')])


class SetupArgsTest(helpers.ExtendedTestCase):
  """Test setup_args."""

  def setUp(self):
    helpers.patch(self, [
        'cmd_editor.editor.edit'
    ])
    self.testcase = mock.Mock(
        id=1234, reproduction_args='--repro',
        environment={'ASAN_OPTIONS': 'test-asan'}, gestures=None,
        stacktrace_lines=[{'content': 'line'}],
        job_type='job_type')
    self.testcase_path = os.path.expanduser(
        os.path.join('~', '.clusterfuzz', '1234_testcase', 'testcase.js'))
    self.testcase.get_testcase_path.return_value = self.testcase_path
    self.provider = mock.Mock(
        symbolizer_path='/chrome/source/folder/llvm-symbolizer')
    self.provider.get_binary_path.return_value = '/chrome/source/folder/d8'
    self.provider.get_build_directory.return_value = '/chrome/source/folder'
    self.definition = mock.Mock()

  def test_disable_xvfb(self):
    """Test disable xvfb."""
    reproducer = reproducers.LinuxChromeJobReproducer(
        self.definition, self.provider, self.testcase, 'UBSAN',
        libs.make_options(
            disable_xvfb=True,
            target_args='--test --disable-gl-drawing-for-tests'))

    reproducer.setup_args()
    self.assertEqual('--repro --test %s' % self.testcase_path,
                     reproducer.args)

  def test_enable_xvfb(self):
    """Test enable xvfb and edit args."""
    def edit(content, prefix, comment):  # pylint: disable=unused-argument
      return '--new-argument' + ' ' + content
    self.mock.edit.side_effect = edit

    reproducer = reproducers.LinuxChromeJobReproducer(
        self.definition, self.provider, self.testcase, 'UBSAN',
        libs.make_options(target_args='--test', edit_mode=True))

    reproducer.setup_args()
    self.assertEqual(
        '--new-argument --repro --test %s' % self.testcase_path,
        reproducer.args)

class LinuxChromeJobReproducerTest(helpers.ExtendedTestCase):
  """Tests the extra functions of LinuxUbsanChromeReproducer."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.reproducers.BaseReproducer.pre_build_steps',
        'clusterfuzz.reproducers.ensure_user_data_dir_if_needed',
        'clusterfuzz.reproducers.update_testcase_path_in_layout_test',
        'clusterfuzz.common.get_resource',
        'pyfakefs.fake_filesystem.FakeFilesystem.RenameObject',
    ])
    self.mock.get_resource.return_value = 'llvm'
    self.mock.ensure_user_data_dir_if_needed.side_effect = (
        lambda args, require_user_data_dir: args + ' --test-user-data-dir')
    self.mock.update_testcase_path_in_layout_test.return_value = '/new-path'
    patch_stacktrace_info(self)
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)
    self.reproducer.definition.require_user_data_dir = False
    self.reproducer.original_testcase_path = '/fake/LayoutTests/testcase'

  def test_reproduce_crash(self):
    """Ensures pre-build steps run correctly."""

    self.reproducer.pre_build_steps()
    self.assertEqual(self.reproducer.testcase_path, '/new-path')
    self.assert_exact_calls(
        self.mock.pre_build_steps, [mock.call(self.reproducer)])
    self.assertEqual(
        self.reproducer.args, '--always-opt --test-user-data-dir')
    self.mock.ensure_user_data_dir_if_needed.assert_called_once_with(
        '--always-opt', False)
    self.mock.update_testcase_path_in_layout_test.assert_called_once_with(
        '/fake/testcase_dir/testcase', '/fake/LayoutTests/testcase',
        '/fake/source_dir')


class XdotoolCommandTest(helpers.ExtendedTestCase):
  """Tests the xdotool_command method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute'])
    patch_stacktrace_info(self)
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)

  def test_call(self):
    """Tests calling the method."""

    self.reproducer.xdotool_command('command to run', ':2753')
    self.assert_exact_calls(self.mock.execute, [
        mock.call('xdotool', 'command to run', '.', env={'DISPLAY': ':2753'})
    ])


class FindWindowsForProcessTest(helpers.ExtendedTestCase):
  """Tests the find_windows_for_process method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.get_process_ids',
        'clusterfuzz.common.execute',
        'time.sleep'])
    patch_stacktrace_info(self)
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)

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
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)

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
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)
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
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)

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
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)
    self.reproducer.gestures = ['windowsize,2', 'type,\'ValeM1khbW4Gt!\'']

  def test_call_execute_gesture(self):
    """Test parsing gestures."""

    for gesture in self.reproducer.gestures:
      self.reproducer.execute_gesture(gesture, '12345', ':display')

    self.assert_exact_calls(self.mock.xdotool_command, [
        mock.call(self.reproducer, 'windowsize 12345 2', ':display'),
        mock.call(self.reproducer, 'type -- \'ValeM1khbW4Gt!\'', ':display')])


class XvfbTest(helpers.ExtendedTestCase):
  """Used to test the Xvfb context manager."""

  def setUp(self):
    helpers.patch(self, ['xvfbwrapper.Xvfb',
                         'subprocess.Popen',
                         'time.sleep'])

  def test_correct_oserror_exception(self):
    """Ensures the correct exception is raised when Xvfb is not found."""

    def _raise_with_message(*_unused, **_kwunused):
      del _unused, _kwunused #Not used by this method
      raise OSError('[Errno 2] No such file or directory')

    self.mock.Popen.side_effect = _raise_with_message
    self.mock.Xvfb.return_value = mock.Mock(xvfb_cmd=['not_display',
                                                      ':display'])

    with self.assertRaises(common.NotInstalledError):
      with reproducers.Xvfb(False) as display_name:
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
      with reproducers.Xvfb(False) as display_name:
        self.assertNotEqual(display_name, ':display')

    self.assert_n_calls(0, [self.mock.Popen.return_value.kill,
                            self.mock.sleep,
                            self.mock.Xvfb.return_value.stop])

  def test_start_stop_blackbox(self):
    """Tests that the context manager starts/stops xvfbwrapper and blackbox."""

    self.mock.Xvfb.return_value = mock.Mock(xvfb_cmd=['not_display',
                                                      ':display'])

    with reproducers.Xvfb(False) as display_name:
      self.assertEqual(display_name, ':display')

    self.assert_exact_calls(self.mock.Xvfb, [mock.call(
        width=1280, height=1024)])
    self.assert_exact_calls(self.mock.Xvfb.return_value.start, [mock.call()])
    self.assert_exact_calls(self.mock.Xvfb.return_value.stop,
                            [mock.call.stop()])
    self.assert_exact_calls(self.mock.Popen, [
        mock.call(['blackbox'], env={'DISPLAY': ':display'})])
    self.assert_exact_calls(self.mock.Popen.return_value.kill, [mock.call()])
    self.assert_exact_calls(self.mock.sleep, [mock.call(3)])

  def test_no_blackbox(self):
    """Tests that the manager doesnt start blackbox when disabled."""

    self.mock.Xvfb.return_value = mock.Mock(xvfb_cmd=['not_display',
                                                      ':display'])

    with reproducers.Xvfb(True) as display_name:
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
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)
    helpers.patch(self, [
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.reproduce_crash',
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.post_run_symbolize',
        'clusterfuzz.common.post',
        'time.sleep'])
    self.mock.reproduce_crash.return_value = (0, 'stuff')
    self.mock.post_run_symbolize.return_value = 'stuff'
    self.reproducer.crash_type = 'original_type'
    self.reproducer.crash_state = ['original', 'state']
    self.reproducer.job_type = 'linux_ubsan_chrome'

  def test_bad_stacktrace(self):
    """Tests system exit when the stacktrace doesn't match."""

    wrong_response = {
        'crash_type': 'wrong type',
        'crash_state': 'incorrect\nstate2'}
    self.mock.post.side_effect = [
        mock.Mock(text=json.dumps(wrong_response)),
        mock.Mock(text=json.dumps(wrong_response))]

    with self.assertRaises(common.UnreproducibleError):
      self.reproducer.reproduce(2)

  def test_good_stacktrace(self):
    """Tests functionality when the stacktrace matches"""
    correct_response = {
        'crash_type': 'original_type',
        'crash_state': 'original\nstate'}
    wrong_response = {
        'crash_type': 'wrong type',
        'crash_state': 'incorrect\nstate2'}
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
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.common.get_resource',
        'clusterfuzz.reproducers.LinuxChromeJobReproducer.get_stacktrace_info'
    ])
    self.reproducer = create_reproducer(reproducers.LinuxChromeJobReproducer)
    self.reproducer.source_directory = '/path/to/chromium'
    self.mock.get_resource.return_value = 'asan_sym_proxy.py'
    self.mock.execute.return_value = (0, 'symbolized')

  def test_symbolize_no_output(self):
    """Test to ensure no symbolization is done with no output."""
    output = ' '
    result = self.reproducer.post_run_symbolize(output)

    self.assert_exact_calls(self.mock.execute, [])
    self.assertEqual(result, '')

  def test_symbolize_output(self):
    """Test to ensure the correct symbolization call are made."""
    result = self.reproducer.post_run_symbolize('output_lines')

    self.mock.execute.assert_called_once_with(
        '/path/to/chromium/tools/valgrind/asan/asan_symbolize.py',
        '',
        os.path.expanduser('~'),
        env={'LLVM_SYMBOLIZER_PATH': 'asan_sym_proxy.py',
             'CHROMIUM_SRC': '/path/to/chromium'},
        stdout_transformer=mock.ANY,
        capture_output=True,
        exit_on_error=True,
        input_str='output_lines\0',
        redirect_stderr_to_stdout=True)
    self.assertIsInstance(
        self.mock.execute.call_args[1]['stdout_transformer'],
        output_transformer.Identity)
    self.assertEqual(result, 'symbolized')


class StripHtmlTest(helpers.ExtendedTestCase):
  """Test strip_html."""

  def test_strip_html(self):
    """Test strip <a> tag."""
    self.assertEqual(
        ['aa test &'],
        reproducers.strip_html(['aa <a href="sadfsd">test</a> &amp;']))


class GetOnlyFirstStacktraceTest(helpers.ExtendedTestCase):
  """Test get_only_first_stacktrace."""

  def test_one_trace(self):
    """Test having only one trace."""
    self.assertEqual(
        ['aa', 'bb'],
        reproducers.get_only_first_stacktrace(['  ', 'aa  ', 'bb']))

  def test_unsymbolized_stacktrace(self):
    """Test unsymbolized stacktrace."""
    self.assertEqual(
        ['+------- fake trace ----+', 'aa', 'bb'],
        reproducers.get_only_first_stacktrace([
            '   ',
            '+------- fake trace ----+',
            'aa',
            'bb',
            '+------Release Build Unsymbolized Stacktrace (diff)------+',
            'cc'
        ]))


class LibfuzzerJobReproducerPreBuildStepsTest(helpers.ExtendedTestCase):
  """Test Libfuzzer.pre_build_steps."""

  def test_set_args(self):
    """Test fixing dict."""
    reproducer = create_reproducer(reproducers.LibfuzzerJobReproducer)
    reproducer.args = '-aaa=bbb -dict=/a/b/c/fuzzer.dict -ccc=ddd'
    reproducer.pre_build_steps()

    self.assertEqual(
        '-aaa=bbb -ccc=ddd -dict=/fake/build_dir/fuzzer.dict'
        ' --test /fake/testcase_dir/testcase',
        reproducer.args)


class DeserializeLibfuzzerArgsTest(helpers.ExtendedTestCase):
  """Test deserializer_libfuzzer_args."""

  def test_empty(self):
    """Test empty string."""
    self.assertEqual({}, reproducers.deserialize_libfuzzer_args('   '))

  def test_parse(self):
    """Test parsing."""
    self.assertEqual(
        {'aaa': 'bbb', 'ccc': 'ddd', 'eee': 'fff'},
        reproducers.deserialize_libfuzzer_args(' -aaa=bbb   -ccc=ddd  -eee=fff')
    )


class SerializeLibfuzzerArgsTest(helpers.ExtendedTestCase):
  """Test serializer_libfuzzer_args."""

  def test_empty(self):
    """Test empty dict."""
    self.assertEqual('', reproducers.serialize_libfuzzer_args({}))

  def test_serialize(self):
    """Test serializing."""
    self.assertEqual(
        '-aaa=bbb -ccc=ddd -eee=fff',
        reproducers.serialize_libfuzzer_args(
            {'aaa': 'bbb', 'eee': 'fff', 'ccc': 'ddd'})
    )


class MaybeFixDictArgTest(helpers.ExtendedTestCase):
  """Test maybe_fix_dict_args."""

  def test_no_dict_arg(self):
    """Test no dict arg."""
    args = reproducers.maybe_fix_dict_args({'aaa': 'bbb'}, '/fake/path')
    self.assertEqual({'aaa': 'bbb'}, args)

  def test_dict_arg(self):
    """Test fix dict arg."""
    args = reproducers.maybe_fix_dict_args(
        {'aaa': 'bbb', 'dict': '/a/b/c/fuzzer.dict', 'c': 'd'}, '/fake/path')
    self.assertEqual(
        {'aaa': 'bbb', 'dict': '/fake/path/fuzzer.dict', 'c': 'd'}, args)


class IsSimilarTest(helpers.ExtendedTestCase):
  """Test is_similar."""

  def test_not_similar(self):
    """Test not similar."""
    self.assertFalse(reproducers.is_similar(
        common.CrashSignature('t', ['a']),
        common.CrashSignature('z', ['b'])))
    self.assertFalse(reproducers.is_similar(
        common.CrashSignature('t', ['a', 'b']),
        common.CrashSignature('t', ['a', 'c', 'd'])))
    self.assertFalse(reproducers.is_similar(
        common.CrashSignature('t', ['a']),
        common.CrashSignature('t', ['a', 'c', 'b'])))

  def test_similar(self):
    """Test similar."""
    self.assertTrue(reproducers.is_similar(
        common.CrashSignature('t', ['a']),
        common.CrashSignature('z', ['a'])))
    self.assertTrue(reproducers.is_similar(
        common.CrashSignature('t', ['a', 'b']),
        common.CrashSignature('t', ['a', 'c'])))
    self.assertTrue(reproducers.is_similar(
        common.CrashSignature('t', ['a']),
        common.CrashSignature('t', ['a', 'c'])))
    self.assertTrue(reproducers.is_similar(
        common.CrashSignature('t', ['a', 'b', 'd']),
        common.CrashSignature('t', ['a', 'b', 'c'])))
    self.assertTrue(reproducers.is_similar(
        common.CrashSignature('t', ['a', 'b']),
        common.CrashSignature('t', ['a', 'b', 'c'])))


class EnsureUserDataDirIfNeededTest(helpers.ExtendedTestCase):
  """Test ensure_user_data_dir_if_needed."""

  def setUp(self):
    self.setup_fake_filesystem()
    os.makedirs(reproducers.USER_DATA_DIR_PATH)
    self.assertTrue(os.path.exists(reproducers.USER_DATA_DIR_PATH))

  def test_doing_nothing(self):
    """Test doing nothing."""
    self.assertEqual(
        '--something',
        reproducers.ensure_user_data_dir_if_needed('--something', False))

  def test_add_because_it_should(self):
    """Test adding arg because it should have."""
    self.assertEqual(
        '--something --user-data-dir=%s' % reproducers.USER_DATA_DIR_PATH,
        reproducers.ensure_user_data_dir_if_needed('--something', True))
    self.assertFalse(os.path.exists(reproducers.USER_DATA_DIR_PATH))

  def test_add_because_of_previous_args(self):
    """Test replacing arg because it exists."""
    self.assertEqual(
        '--something  --user-data-dir=%s' % reproducers.USER_DATA_DIR_PATH,
        reproducers.ensure_user_data_dir_if_needed(
            '--something --user-data-dir=/tmp/random', False))
    self.assertFalse(os.path.exists(reproducers.USER_DATA_DIR_PATH))


class UpdateTestcasePathInLayoutTestTest(helpers.ExtendedTestCase):
  """Test update_testcase_path_in_layout_test."""

  def setUp(self):
    self.setup_fake_filesystem()
    os.makedirs('/testcase_dir')
    self.fs.CreateFile('/testcase_dir/testcase', contents='Some test')
    os.makedirs('/source/third_party/WebKit/LayoutTests/original_dir')

  def test_doing_nothing(self):
    """Test doing nothing."""
    self.assertEqual(
        '/testpath/testcase',
        reproducers.update_testcase_path_in_layout_test(
            '/testpath/testcase', '/original/testcase', '/source'))

  def test_update(self):
    """Update the testcase path."""
    new_path = (
        '/source/third_party/WebKit/LayoutTests/original_dir/original_file')
    self.assertEqual(
        new_path,
        reproducers.update_testcase_path_in_layout_test(
            '/testcase_dir/testcase',
            '/original/LayoutTests/original_dir/original_file',
            '/source/'))
    with open(new_path) as f:
      self.assertEqual('Some test', f.read())
