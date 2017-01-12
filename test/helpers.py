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

import mock
import time


# _Object is needed because we want to add attribute to its instance.
class _Object(object):
  pass


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
    setattr(getattr(testcase_obj.mock, attr_name), '__name__', attr_name)

