"""Test the module for the 'reproduce' command"""
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
import unittest
import mock

from clusterfuzz import common
from clusterfuzz.commands import reproduce
from test import helpers

class ExtendedTestCase(unittest.TestCase):
  """An extended version of TestCase with extra methods for fine-grained method
  call assertions."""

  def assert_n_calls(self, n, methods):
    """Assert that all patched methods in 'methods' have been called n times"""

    for m in methods:
      self.assertEqual(n, m.call_count)

  def assert_exact_calls(self, method, calls):
    """Assert that 'method' only has calls defined in 'calls', and no others"""

    method.assert_has_calls(calls)
    self.assertEqual(len(calls), method.call_count)


class ExecuteTest(ExtendedTestCase):
  """Test execute."""

  def setUp(self):
    helpers.patch(self, [
        'webbrowser.open',
        'clusterfuzz.commands.reproduce.get_testcase_info',
        '__builtin__.raw_input'])

    self.mock.raw_input.return_value = '12345'
    self.mock.get_testcase_info.return_value = {
        'id': 1234,
        'crash_type': 'Bad Crash',
        'crash_state': ['halted']}

  def test_oauth_calls(self):
    """Asserts that the correct API calls are made for authentication."""

    reproduce.execute('1234', False)

    self.mock.open.assert_has_calls([mock.call(
        reproduce.GOOGLE_OAUTH_URL,
        autoraise=True,
        new=1)])

    self.assert_exact_calls(
        self.mock.get_testcase_info,
        [mock.call('1234', 'VerificationCode 12345')])

class GetTestcaseInfoTest(ExtendedTestCase):
  """Test get_testcase_info."""

  def setUp(self):
    helpers.patch(self, [
        'urlfetch.fetch'])

  def test_correct_authorization(self):
    """Ensures that the testcase info is returned when the auth is correct"""

    response_dict = {
        'id': '12345',
        'crash_type': 'Bad Crash',
        'crash_state': ['Halted']}

    self.mock.fetch.return_value = mock.Mock(
        status=200,
        body=json.dumps(response_dict))

    response = reproduce.get_testcase_info('12345', 'Test Auth')

    self.assert_n_calls(1, [self.mock.fetch])
    self.assertEqual(response, response_dict)

  def test_incorrect_authorization(self):
    """Ensures that when auth is incorrect the right exception is thrown"""

    response_dict = {
        'status': 401,
        'type': 'UnauthorizedException',
        'message': {
            'Invalid verification code (12345)': {
                'error': 'invalid_grant',
                'error_description': 'Bad Request'}},
        'params': {
            'testcaseId': ['1234']},
        'email': 'test@email.com'}

    self.mock.fetch.return_value = mock.Mock(
        status=401,
        body=json.dumps(response_dict))

    with self.assertRaises(common.ClusterfuzzAuthError) as cm:
      reproduce.get_testcase_info('12345', 'Bad Auth')
    self.assertIn('Invalid verification code (12345)', cm.exception.message)
