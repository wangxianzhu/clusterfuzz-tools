"""Tests for editor."""
# Copyright 2017 Google Inc.
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

import subprocess

import helpers
from cmd_editor import editor


class GetFullPathTest(helpers.ExtendedTestCase):
  """Test get_editor_path."""

  def setUp(self):
    helpers.patch(self, ['subprocess.check_output'])

  def test_get(self):
    """Test get from env."""
    self.mock.check_output.return_value = 'test-full'
    self.assertEqual('test-full', editor.get_full_path('binary'))
    self.mock.check_output.assert_called_once_with(['which', 'binary'])

  def test_error(self):
    """Test get default."""
    self.mock.check_output.side_effect = subprocess.CalledProcessError(0, None)

    with self.assertRaises(Exception) as cm:
      editor.get_full_path('binary')

    self.mock.check_output.assert_called_once_with(['which', 'binary'])
    self.assertEqual(
        'binary is not found. Please ensure it is in PATH.',
        cm.exception.message)


class EditTest(helpers.ExtendedTestCase):
  """Test edit."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'os.system',
        'cmd_editor.editor.get_full_path'
    ])

  def test_edit(self):
    """Test edit."""
    self.saved_filepath = ''
    def modify_file(cmd):
      _, self.saved_filepath = cmd.split(' ')
      with open(self.saved_filepath, 'a') as f:
        f.write('\nAdded content')

    self.mock.system.side_effect = modify_file
    self.mock.get_full_path.return_value = 'test-binary'

    self.assertEqual(
        'Test\nAdded content', editor.edit('Test', comment='comment'))
    self.mock.system.assert_called_once_with(
        'test-binary %s' % self.saved_filepath)
    self.mock.get_full_path.assert_called_once_with('vi')


class AddCommentTest(helpers.ExtendedTestCase):
  """Test add_comment."""

  def test_empty(self):
    """Test empty comment."""
    self.assertEqual('test', editor.add_comment('test', ''))

  def test_add(self):
    """Test add."""
    self.assertEqual(
        '# comment\n\ntest', editor.add_comment('test', 'comment'))


class RemoveCommentTest(helpers.ExtendedTestCase):
  """Test remove_comment."""

  def test_empty(self):
    """Test empty comment."""
    self.assertEqual('test', editor.remove_comment('\n\ntest\n'))

  def test_remove(self):
    """Test remove comment."""
    self.assertEqual('test', editor.remove_comment('# comment\n\ntest\n'))
