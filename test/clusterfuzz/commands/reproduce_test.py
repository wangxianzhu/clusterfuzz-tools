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

from __future__ import print_function

import json
import stat
import os
import mock
from pyfakefs import fake_filesystem_unittest

from clusterfuzz import common
from clusterfuzz.commands import reproduce
from test import helpers

class ExtendedTestCase(fake_filesystem_unittest.TestCase):
  """An extended version of TestCase with extra methods for fine-grained method
  call assertions."""

  def setup_fake_filesystem(self):
    """Sets up PyFakefs and creates aliases for filepaths."""

    self.setUpPyfakefs()
    self.clusterfuzz_dir = os.path.expanduser(os.path.join(
        '~', '.clusterfuzz'))
    self.auth_header_file = os.path.join(self.clusterfuzz_dir,
                                         'auth_header')

  def assert_file_permissions(self, filename, permissions):
    """Assert that 'filename' has specific permissions"""

    self.assertEqual(int(oct(os.stat(filename).st_mode)[4:]),
                     permissions)

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
    helpers.patch(self, ['clusterfuzz.commands.reproduce.get_testcase_info'])
    self.mock.get_testcase_info.return_value = {
        'id': 1234,
        'crash_type': 'Bad Crash',
        'crash_state': ['halted']}

  def test_grab_data(self):
    """Asserts that the testcase data is grabbed correctly."""

    reproduce.execute('1234', False)
    self.assert_exact_calls(self.mock.get_testcase_info, [mock.call('1234')])

class GetTestcaseInfoTest(ExtendedTestCase):
  """Test get_testcase_info."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_stored_auth_header',
        'clusterfuzz.commands.reproduce.store_auth_header',
        'clusterfuzz.commands.reproduce.get_verification_header',
        'urlfetch.fetch'])

  def test_correct_stored_authorization(self):
    """Ensures that the testcase info is returned when stored auth is correct"""

    response_headers = {'x-clusterfuzz-authorization': 'Bearer 12345'}
    response_dict = {
        'id': '12345',
        'crash_type': 'Bad Crash',
        'crash_state': ['Halted']}

    self.mock.get_stored_auth_header.return_value = 'Bearer 12345'
    self.mock.fetch.return_value = mock.Mock(
        status=200,
        body=json.dumps(response_dict),
        headers=response_headers)

    response = reproduce.get_testcase_info('12345')

    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.store_auth_header, [
        mock.call('Bearer 12345')])
    self.assert_exact_calls(self.mock.fetch, [mock.call(
        url=reproduce.CLUSTERFUZZ_TESTCASE_URL % '12345',
        headers={'Authorization': 'Bearer 12345'})])
    self.assertEqual(response, response_dict)

  def test_incorrect_stored_header(self):
    """Tests when the header is stored, but has expired/is invalid."""

    response_headers = {'x-clusterfuzz-authorization': 'Bearer 12345'}
    response_dict = {
        'id': '12345',
        'crash_type': 'Bad Crash',
        'crash_state': ['Halted']}

    self.mock.fetch.side_effect = [
        mock.Mock(status=401),
        mock.Mock(status=200,
                  body=json.dumps(response_dict),
                  headers=response_headers)]
    self.mock.get_stored_auth_header.return_value = 'Bearer 12345'
    self.mock.get_verification_header.return_value = 'VerificationCode 12345'

    response = reproduce.get_testcase_info('12345')

    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.get_verification_header, [mock.call()])
    self.assert_exact_calls(self.mock.fetch, [
        mock.call(
            url=reproduce.CLUSTERFUZZ_TESTCASE_URL % '12345',
            headers={'Authorization': 'Bearer 12345'}),
        mock.call(
            headers={'Authorization': 'VerificationCode 12345'},
            url=reproduce.CLUSTERFUZZ_TESTCASE_URL % '12345')])
    self.assert_exact_calls(self.mock.store_auth_header, [
        mock.call('Bearer 12345')])
    self.assertEqual(response, response_dict)


  def test_correct_verification_auth(self):
    """Tests grabbing testcase info when the local header is invalid."""

    response_headers = {'x-clusterfuzz-authorization': 'Bearer 12345'}
    response_dict = {
        'id': '12345',
        'crash_type': 'Bad Crash',
        'crash_state': ['Halted']}

    self.mock.get_stored_auth_header.return_value = None
    self.mock.get_verification_header.return_value = 'VerificationCode 12345'
    self.mock.fetch.return_value = mock.Mock(
        status=200,
        body=json.dumps(response_dict),
        headers=response_headers)

    response = reproduce.get_testcase_info('12345')

    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.get_verification_header, [mock.call()])
    self.assert_exact_calls(self.mock.store_auth_header, [
        mock.call('Bearer 12345')])
    self.assert_exact_calls(self.mock.fetch, [mock.call(
        headers={'Authorization': 'VerificationCode 12345'},
        url=reproduce.CLUSTERFUZZ_TESTCASE_URL % '12345')])
    self.assertEqual(response, response_dict)

  def test_incorrect_authorization(self):
    """Ensures that when auth is incorrect the right exception is thrown"""

    response_headers = {'x-clusterfuzz-authorization': 'Bearer 12345'}
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

    self.mock.get_stored_auth_header.return_value = 'Bearer 12345'
    self.mock.get_verification_header.return_value = 'VerificationCode 12345'
    self.mock.fetch.return_value = mock.Mock(
        status=401,
        body=json.dumps(response_dict),
        headers=response_headers)

    with self.assertRaises(common.ClusterfuzzAuthError) as cm:
      reproduce.get_testcase_info('12345')
    self.assertIn('Invalid verification code (12345)', cm.exception.message)
    self.assert_exact_calls(self.mock.fetch, [
        mock.call(
            url=reproduce.CLUSTERFUZZ_TESTCASE_URL % '12345',
            headers={'Authorization': 'Bearer 12345'}),
        mock.call(
            headers={'Authorization': 'VerificationCode 12345'},
            url=reproduce.CLUSTERFUZZ_TESTCASE_URL % '12345')])

class GetStoredAuthHeaderTest(ExtendedTestCase):
  """Tests the stored_auth_key method."""

  def setUp(self):
    self.setup_fake_filesystem()

  def test_file_missing(self):
    """Tests functionality when auth key file does not exist."""

    result = reproduce.get_stored_auth_header()
    self.assertEqual(result, None)

  def test_permissions_incorrect(self):
    """Tests functionality when file exists but permissions wrong."""

    self.fs.CreateFile(self.auth_header_file)
    os.chmod(self.auth_header_file, stat.S_IWGRP)

    with self.assertRaises(common.PermissionsTooPermissiveError) as ex:
      result = reproduce.get_stored_auth_header()
      self.assertEqual(result, None)
    self.assertIn(
        'File permissions too permissive to open',
        ex.exception.message)

  def test_file_valid(self):
    """Tests when file is accessible and auth key is returned."""

    self.fs.CreateFile(self.auth_header_file, contents='Bearer 1234')
    os.chmod(self.auth_header_file, stat.S_IWUSR|stat.S_IRUSR)

    result = reproduce.get_stored_auth_header()
    self.assertEqual(result, 'Bearer 1234')

class StoreAuthHeaderTest(ExtendedTestCase):
  """Tests the store_auth_header method."""

  def setUp(self):
    self.setup_fake_filesystem()
    self.auth_header = 'Bearer 12345'

  def test_folder_absent(self):
    """Tests storing when the folder has not been created prior."""

    self.assertFalse(os.path.exists(self.clusterfuzz_dir))
    reproduce.store_auth_header(self.auth_header)

    self.assertTrue(os.path.exists(self.clusterfuzz_dir))
    with open(self.auth_header_file, 'r') as f:
      self.assertEqual(f.read(), self.auth_header)
    self.assert_file_permissions(self.auth_header_file, 600)

  def test_folder_present(self):
    """Tests storing when the folder has already been created."""

    self.fs.CreateFile(self.auth_header_file)
    reproduce.store_auth_header(self.auth_header)

    with open(self.auth_header_file, 'r') as f:
      self.assertEqual(f.read(), self.auth_header)
    self.assert_file_permissions(self.auth_header_file, 600)

class GetVerificationHeaderTest(ExtendedTestCase):
  """Tests the get_verification_header method"""

  def setUp(self):
    helpers.patch(self, [
        'webbrowser.open',
        '__builtin__.raw_input'])
    self.mock.raw_input.return_value = '12345'

  def test_returns_correct_header(self):
    """Tests that the correct token with header is returned."""

    response = reproduce.get_verification_header()

    self.mock.open.assert_has_calls([mock.call(
        reproduce.GOOGLE_OAUTH_URL,
        new=1,
        autoraise=True)])
    self.assertEqual(response, 'VerificationCode 12345')
