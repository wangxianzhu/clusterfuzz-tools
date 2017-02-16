"""Module for the Testcase class."""
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

from clusterfuzz import common

CLUSTERFUZZ_DIR = os.path.expanduser(os.path.join('~', '.clusterfuzz'))
CLUSTERFUZZ_TESTCASES_DIR = os.path.join(CLUSTERFUZZ_DIR, 'testcases')
CLUSTERFUZZ_TESTCASE_URL = ('https://cluster-fuzz.appspot.com/v2/testcase-'
                            'detail/download-testcase/oauth?id=%s')

class Testcase(object):
  """The Testase module, to abstract away logic using the testcase JSON."""

  def get_environment(self):
    """Sets up the environment by parsing stacktrace lines."""

    new_env = {}
    stacktrace_lines = [l['content']  for l in self.stacktrace_lines]
    for l in stacktrace_lines:
      if '[Environment] ' not in l:
        continue
      l = l.replace('[Environment] ', '')
      name, value = l.split(' = ')
      new_env[name] = value

    return new_env

  def __init__(self, testcase_json):

    self.id = testcase_json['id']
    self.stacktrace_lines = testcase_json['crash_stacktrace']['lines']
    self.environment = self.get_environment()
    self.revision = testcase_json['crash_revision']
    self.build_url = testcase_json['metadata']['build_url']
    self.job_type = testcase_json['testcase']['job_type']
    self.reproduction_args = (
        '%s %s' %(testcase_json['testcase']['window_argument'],
                  testcase_json['testcase']['minimized_arguments']))

  def testcase_dir_name(self):
    """Returns a testcases' respective directory."""
    return os.path.join(CLUSTERFUZZ_TESTCASES_DIR,
                        str(self.id) + '_testcase')

  def get_testcase_path(self):
    """Downloads & returns the location of the testcase file."""

    testcase_dir = self.testcase_dir_name()
    #TODO: Filename testcase.js is d8-specific
    file_extension = 'pdf' if 'pdfium' in self.job_type else 'js'
    filename = os.path.join(testcase_dir, 'testcase.%s' % file_extension)
    if os.path.isfile(filename):
      return filename

    print 'Downloading testcase data...'

    if not os.path.exists(CLUSTERFUZZ_TESTCASES_DIR):
      os.makedirs(CLUSTERFUZZ_TESTCASES_DIR)
    os.makedirs(testcase_dir)

    auth_header = common.get_stored_auth_header()
    command = 'wget --header="Authorization: %s" "%s" -O ./testcase.%s' % (
        auth_header, CLUSTERFUZZ_TESTCASE_URL % self.id, file_extension)
    common.execute(command, testcase_dir)

    return filename
