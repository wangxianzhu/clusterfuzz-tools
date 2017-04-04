"""Test the 'stackdriver_logging' module."""
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
import time
import mock

from test import helpers
from clusterfuzz import stackdriver_logging

class TestSendLog(helpers.ExtendedTestCase):
  """Tests the send_log method to ensure all params are sent."""

  def setUp(self):
    self.mock_os_environment({'USER': 'name'})
    helpers.patch(self, [
        'clusterfuzz.stackdriver_logging.ServiceAccountCredentials',
        'httplib2.Http',
        'clusterfuzz.stackdriver_logging.get_session_id'])

  def test_send_stacktrace(self):
    """Test to ensure stacktrace and params are sent properly."""
    self.mock.get_session_id.return_value = 'user:1234:sessionid'

    params = {'testcaseId': 123456,
              'success': True,
              'command': 'reproduce',
              'buildType': 'chromium',
              'current': True,
              'disableGoma': True}
    stackdriver_logging.send_log(params, 'Stacktrace')

    params['user'] = 'name'
    params['sessionId'] = 'user:1234:sessionid'
    params['message'] = ('name successfully finished running reproduce with '
                         'testcase=123456, build_type=chromium, current=True, '
                         'and goma=disabled\nStacktrace')
    structure = {
        'logName': 'projects/clusterfuzz-tools/logs/client',
        'resource': {
            'type': 'project',
            'labels': {
                'project_id': 'clusterfuzz-tools'}},
        'entries': [{
            'jsonPayload': params,
            'severity': 'ERROR'}]}
    self.assert_exact_calls(
        (self.mock.ServiceAccountCredentials.from_json_keyfile_name
         .return_value.authorize.return_value.request), [mock.call(
             uri='https://logging.googleapis.com/v2/entries:write',
             method='POST', body=json.dumps(structure))])

  def test_send_log_params(self):
    """Test to ensure params are sent properly."""
    self.mock.get_session_id.return_value = 'user:1234:sessionid'

    params = {'testcaseId': 123456,
              'success': True,
              'command': 'reproduce',
              'buildType': 'chromium',
              'current': True,
              'disableGoma': True}
    stackdriver_logging.send_log(params)

    params['user'] = 'name'
    params['sessionId'] = 'user:1234:sessionid'
    params['message'] = ('name successfully finished running reproduce with '
                         'testcase=123456, build_type=chromium, current=True, '
                         'and goma=disabled')
    structure = {
        'logName': 'projects/clusterfuzz-tools/logs/client',
        'resource': {
            'type': 'project',
            'labels': {
                'project_id': 'clusterfuzz-tools'}},
        'entries': [{
            'jsonPayload': params,
            'severity': 'INFO'}]}
    self.assert_exact_calls(
        (self.mock.ServiceAccountCredentials.from_json_keyfile_name
         .return_value.authorize.return_value.request), [mock.call(
             uri='https://logging.googleapis.com/v2/entries:write',
             method='POST', body=json.dumps(structure))])


  def test_send_log_start(self):
    """Test to ensure params are sent properly."""
    self.mock.get_session_id.return_value = 'user:1234:sessionid'

    params = {'testcaseId': 123456,
              'command': 'reproduce',
              'buildType': 'chromium',
              'current': True,
              'disableGoma': True}
    stackdriver_logging.send_log(params)

    params['user'] = 'name'
    params['sessionId'] = 'user:1234:sessionid'
    params['message'] = ('name started running reproduce with '
                         'testcase=123456, build_type=chromium, current=True, '
                         'and goma=disabled')
    structure = {
        'logName': 'projects/clusterfuzz-tools/logs/client',
        'resource': {
            'type': 'project',
            'labels': {
                'project_id': 'clusterfuzz-tools'}},
        'entries': [{
            'jsonPayload': params,
            'severity': 'INFO'}]}
    self.assert_exact_calls(
        (self.mock.ServiceAccountCredentials.from_json_keyfile_name
         .return_value.authorize.return_value.request), [mock.call(
             uri='https://logging.googleapis.com/v2/entries:write',
             method='POST', body=json.dumps(structure))])


class LogTest(helpers.ExtendedTestCase):
  """Tests the log method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.stackdriver_logging.send_start',
                         'clusterfuzz.stackdriver_logging.send_success',
                         'clusterfuzz.stackdriver_logging.send_failure'])

  def raise_func(self):
    raise Exception('Oops')

  def test_raise_exception(self):
    """Test raising a non clusterfuzz exception."""

    to_call = stackdriver_logging.log(self.raise_func)
    with self.assertRaises(Exception):
      to_call()


class TestGetSessionId(helpers.ExtendedTestCase):
  """Tests the get session ID method"""

  def test_get_session(self):
    actual_user = os.environ.get('USER')

    session_id = stackdriver_logging.get_session_id()
    user, timestamp, random_string = session_id.split(':')
    self.assertEqual(user, actual_user)
    self.assertTrue(float(timestamp) < time.time())
    self.assertEqual(len(random_string), 40)
