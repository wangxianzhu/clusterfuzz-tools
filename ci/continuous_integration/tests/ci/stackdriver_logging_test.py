"""Tests the logging module of the CI service."""
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

import json
import mock

from ci import stackdriver_logging
import helpers


class SendLogTest(helpers.ExtendedTestCase):
  """Test the send_log method."""

  def setUp(self):
    helpers.patch(self, ['ci.stackdriver_logging.ServiceAccountCredentials'])

  def test_send_structure(self):
    """Ensures that the correct request structure is sent."""

    params = {
        'testcase_id': 1234,
        'version': '0.2.2rc3',
        'type': 'sanity'}

    structure = {
        'logName': 'projects/clusterfuzz-tools/logs/ci',
        'resource': {
            'type': 'project',
            'labels': {
                'project_id': 'clusterfuzz-tools'}},
        'entries': [{
            'jsonPayload': params,
            'severity': 'ERROR'}]}

    stackdriver_logging.send_log(params, False)

    self.assert_exact_calls(
        (self.mock.ServiceAccountCredentials.from_json_keyfile_name
         .return_value.authorize.return_value.request), [mock.call(
             uri='https://logging.googleapis.com/v2/entries:write',
             method='POST', body=json.dumps(structure))])


class SendRunTest(helpers.ExtendedTestCase):
  """Tests the send_run method."""

  def setUp(self):
    helpers.patch(self, ['ci.stackdriver_logging.send_log'])

  def test_send_params(self):
    stackdriver_logging.send_run(1234, 'sanity', '0.2.2rc3', True)
    self.assert_exact_calls(self.mock.send_log, [mock.call({
        'testcaseId': 1234, 'type': 'sanity', 'version': '0.2.2rc3'}, True)])
