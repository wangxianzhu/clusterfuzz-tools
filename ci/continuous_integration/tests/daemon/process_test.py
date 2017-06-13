"""Tests process"""
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
import signal
import subprocess

import mock

from daemon import process
from test_libs import helpers


class CallTest(helpers.ExtendedTestCase):
  """Tests call."""

  def setUp(self):
    self.mock_os_environment({'TEST': '1'})
    self.popen = mock.Mock(spec=subprocess.Popen)
    helpers.patch(self, [
        'daemon.process.kill_last_pid',
        'daemon.process.store_last_pid',
        'os.setsid',
        'subprocess.Popen',
    ])

    self.mock.Popen.return_value = self.popen
    self.popen.pid = 123

  def test_capture(self):
    """Test capturing output."""
    self.popen.returncode = 0
    self.popen.communicate.return_value = ('Test', None)
    self.assertEqual(
        'Test',
        process.call('test', cwd='path', env={'NEW': '2'}, capture=True))

    self.mock.Popen.assert_called_once_with(
        'test', shell=True, cwd='path', env={'TEST': '1', 'NEW': '2'},
        stdout=subprocess.PIPE, preexec_fn=os.setsid)
    self.popen.communicate.assert_called_once_with()
    self.mock.store_last_pid.assert_called_once_with(123)
    self.assert_exact_calls(self.mock.kill_last_pid, [mock.call()] * 2)

  def test_not_capture(self):
    """Test not capture."""
    self.popen.returncode = 0
    self.popen.communicate.return_value = (None, None)
    self.assertIsNone(
        process.call('test', cwd='path', env={'NEW': '2'}, capture=False))

    self.mock.Popen.assert_called_once_with(
        'test', shell=True, cwd='path', env={'TEST': '1', 'NEW': '2'},
        stdout=None, preexec_fn=os.setsid)
    self.popen.communicate.assert_called_once_with()
    self.mock.store_last_pid.assert_called_once_with(123)
    self.assert_exact_calls(self.mock.kill_last_pid, [mock.call()] * 2)

  def test_error(self):
    """Test raising exception if returncode is not zero."""
    self.popen.returncode = 1
    self.popen.communicate.return_value = ('Test', None)

    with self.assertRaises(subprocess.CalledProcessError) as cm:
      process.call('test', cwd='path', env={'NEW': '2'}, capture=False)

    self.mock.Popen.assert_called_once_with(
        'test', shell=True, cwd='path', env={'TEST': '1', 'NEW': '2'},
        stdout=None, preexec_fn=os.setsid)
    self.popen.communicate.assert_called_once_with()
    self.mock.store_last_pid.assert_called_once_with(123)
    self.assert_exact_calls(self.mock.kill_last_pid, [mock.call()] * 2)

    self.assertEqual(1, cm.exception.returncode)
    self.assertEqual('Test', cm.exception.output)
    self.assertEqual('test', cm.exception.cmd)


class StoreLastPidTest(helpers.ExtendedTestCase):
  """Tests store_last_pid."""

  def setUp(self):
    self.setup_fake_filesystem()

  def test_store(self):
    """Test store pid."""
    self.fs.CreateFile(process.LAST_PID_FILE, contents='test')
    process.store_last_pid(1234)

    with open(process.LAST_PID_FILE, 'r') as f:
      self.assertEqual('1234', f.read())


class KillLastPidTest(helpers.ExtendedTestCase):
  """Tests kill_last_pid."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, ['os.killpg'])

  def test_kill(self):
    """Test kill and remove the file."""
    self.fs.CreateFile(process.LAST_PID_FILE, contents='1234')
    process.kill_last_pid()

    self.assertFalse(os.path.exists(process.LAST_PID_FILE))
    self.mock.killpg.assert_called_once_with(1234, signal.SIGKILL)

  def test_not_kill(self):
    """Test kill and remove the file."""
    process.kill_last_pid()

    self.assertFalse(os.path.exists(process.LAST_PID_FILE))
    self.assertEqual(0, self.mock.killpg.call_count)
