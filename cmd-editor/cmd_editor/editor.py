"""Editor allows user to edit a content in an editor."""
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

import os
import subprocess
import tempfile


def get_full_path(binary):
  """Check if the binary exists."""
  try:
    return subprocess.check_output(['which', binary]).strip()
  except subprocess.CalledProcessError:
    raise Exception('%s is not found. Please ensure it is in PATH.' % binary)


def add_comment(content, comment):
  """Add comment to the content."""
  if not comment:
    return content

  comment_block = '\n'.join(['# %s' % line for line in comment.split('\n')])
  return comment_block + '\n\n' + content


def remove_comment(content):
  """Remove comment from the content."""
  lines = content.split('\n')
  return '\n'.join([line for line in lines if not line.startswith('#')]).strip()


def edit(
    content, prefix='edit-', editor_env='EDITOR', default_editor='vi',
    comment=''):
  """Open an editor to edit a content and return the edited content.

  Args:
    content: the content to be edited.
    prefix: the prefix for the temporary file name.
    editor_env: the path of the editor.
    default_editor: the default editor path if editor_env's value is not
      present.

  Return:
    The edited content.
  """
  editor_path = get_full_path(os.environ.get(editor_env, default_editor))

  with tempfile.NamedTemporaryFile(delete=False, prefix=prefix) as tmpfile:
    tmpfile.write(add_comment(content, comment))

  os.system('%s %s' % (editor_path, tmpfile.name))

  try:
    with open(tmpfile.name) as f:
      return remove_comment(f.read())
  finally:
    os.unlink(tmpfile.name)
