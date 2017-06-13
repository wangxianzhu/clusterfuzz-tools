"""Test the module for the 'supported_job_types' command"""
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
import yaml

from clusterfuzz.commands import supported_job_types
from test_libs import helpers


class ExecuteTest(helpers.ExtendedTestCase):
  """Tests the printing of supported job types."""

  def setUp(self):
    helpers.patch(self, ['yaml.load'])
    self.mock.load.return_value = {
        'chromium': {
            'chromium_job': 'stuff'},
        'standalone': {
            'pdfium_job': 'pdf_stuff'}}

  def test_print_supported_jobs(self):
    """Tests that printing is formatted correctly."""

    helpers.patch(self, ['logging.getLogger'])
    reload(supported_job_types)

    supported_job_types.execute()

    printed = yaml.dump({'chromium': ['chromium_job'],
                         'standalone': ['pdfium_job']})

    self.assert_exact_calls(self.mock.getLogger.return_value.debug, [
        mock.call('Printing supported job types')])
    self.assert_exact_calls(self.mock.getLogger.return_value.info, [
        mock.call(printed)])
