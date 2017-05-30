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

import helpers
from clusterfuzz import stackdriver_logging

class TestSendLog(helpers.ExtendedTestCase):
  """Tests the send_log method to ensure all params are sent."""

  def setUp(self):
    self.mock_os_environment({'USER': 'name'})
    helpers.patch(self, [
        'clusterfuzz.stackdriver_logging.ServiceAccountCredentials',
        'httplib2.Http',
        'clusterfuzz.stackdriver_logging.get_session_id',
    ])

  def test_send_stacktrace(self):
    """Test to ensure stacktrace and params are sent properly."""
    self.mock.get_session_id.return_value = 'user:1234:sessionid'

    params = {'testcase_id': 123456,
              'success': True,
              'command': 'reproduce',
              'build': 'chromium',
              'current': True,
              'disable_goma': True}
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

    params = {'testcase_id': 123456,
              'success': True,
              'command': 'reproduce',
              'build': 'chromium',
              'current': True,
              'disable_goma': True}
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

    params = {'testcase_id': 123456,
              'command': 'reproduce',
              'build': 'chromium',
              'current': True,
              'disable_goma': True}
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


@stackdriver_logging.log
def raise_func(param):  # pylint: disable=unused-argument
  """Raise a normal exception."""
  raise Exception('Oops')


@stackdriver_logging.log
def raise_keyboard_interrupt(param):  # pylint: disable=unused-argument
  """Raise KeyboardInterrupt."""
  raise KeyboardInterrupt()


@stackdriver_logging.log
def not_raise(param):  # pylint: disable=unused-argument
  """Dummy function."""
  pass


class LogTest(helpers.ExtendedTestCase):
  """Tests the log method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.stackdriver_logging.send_start',
                         'clusterfuzz.stackdriver_logging.send_success',
                         'clusterfuzz.stackdriver_logging.send_failure'])

  def test_raise_exception(self):
    """Test raising a non clusterfuzz exception."""
    with self.assertRaises(Exception) as cm:
      raise_func(param='yes')

    self.assertEqual('Oops', cm.exception.message)
    self.mock.send_start.assert_called_once_with(
        {'command': 'stackdriver_logging_test', 'param': 'yes'})
    self.mock.send_failure.assert_called_once_with(
        'Exception', mock.ANY,
        {'command': 'stackdriver_logging_test', 'param': 'yes'})

  def test_keyboard_interrupt(self):
    """Test raising a KeyboardInterrupt exception."""
    with self.assertRaises(SystemExit) as cm:
      raise_keyboard_interrupt(param='yes')

    self.assertEqual(1, cm.exception.code)
    self.mock.send_start.assert_called_once_with(
        {'command': 'stackdriver_logging_test', 'param': 'yes'})
    self.mock.send_failure.assert_called_once_with(
        'KeyboardInterrupt', mock.ANY,
        {'command': 'stackdriver_logging_test', 'param': 'yes'})

  def test_success(self):
    """Test succeeding."""
    not_raise(param='yes')
    self.mock.send_start.assert_called_once_with(
        {'command': 'stackdriver_logging_test', 'param': 'yes'})
    self.mock.send_success.assert_called_once_with(
        {'command': 'stackdriver_logging_test', 'param': 'yes'})

  def test_on_positional_args(self):
    """Test error on positional arguments."""
    with self.assertRaises(Exception) as cm:
      not_raise('yes')
    self.assertEqual(
        'Invoking not_raise with positional arguments is not allowed.',
        cm.exception.message)


class GetSessionIdTest(helpers.ExtendedTestCase):
  """Tests the get session ID method"""

  def test_get_session(self):
    actual_user = os.environ.get('USER')

    session_id = stackdriver_logging.get_session_id()
    user, timestamp, random_string = session_id.split(':')
    self.assertEqual(user, actual_user)
    self.assertTrue(float(timestamp) < time.time())
    self.assertEqual(len(random_string), 40)


class SendSuccessFailureTest(helpers.ExtendedTestCase):
  """Test send_failure and send_success."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.stackdriver_logging.send_log'])

  def test_send_failure(self):
    """Test send failure."""
    stackdriver_logging.send_failure('Ex', 'trace', {'test': 'yes'})
    self.mock.send_log.assert_called_once_with(
        {'test': 'yes', 'exception': 'Ex', 'success': False}, 'trace')

  def test_send_success(self):
    """Test send success."""
    stackdriver_logging.send_success({'test': 'yes'})
    self.mock.send_log.assert_called_once_with({'test': 'yes', 'success': True})
