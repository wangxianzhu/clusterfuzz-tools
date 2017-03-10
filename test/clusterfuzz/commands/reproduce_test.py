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
import os
import mock

from clusterfuzz import common
from clusterfuzz import binary_providers
from clusterfuzz.commands import reproduce
from test import helpers


class MaybeWarnUnreproducible(helpers.ExtendedTestCase):
  """Test maybe_warn_unreproducible."""

  def test_warn(self):
    """Test warn."""
    self.assertTrue(reproduce.maybe_warn_unreproducible(
        mock.Mock(reproducible=False)))

  def test_not_warn(self):
    """Test warn."""
    self.assertIsNone(reproduce.maybe_warn_unreproducible(
        mock.Mock(reproducible=True)))


class ExecuteTest(helpers.ExtendedTestCase):
  """Test execute."""

  def setUp(self):
    self.suppress_logging_methods()
    self.chrome_src = '/usr/local/google/home/user/repos/chromium/src'
    self.mock_os_environment({'V8_SRC': '/v8/src', 'CHROME_SRC': '/pdf/src'})
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_testcase_info',
        'clusterfuzz.testcase.Testcase',
        'clusterfuzz.commands.reproduce.ensure_goma',
        'clusterfuzz.binary_providers.DownloadedBinary',
        'clusterfuzz.binary_providers.V8Builder',
        'clusterfuzz.binary_providers.ChromiumBuilder'])
    self.response = {
        'testcase': {},
        'id': 1234,
        'crash_type': 'Bad Crash',
        'crash_state': ['halted'],
        'crash_revision': '123456',
        'metadata': {'build_url': 'chrome_build_url'},
        'crash_stacktrace': {'lines': ['Line 1', 'Line 2']}}
    self.mock.get_testcase_info.return_value = self.response
    self.mock.ensure_goma.return_value = '/goma/dir'

  def test_gesture_job(self):
    """Ensures an excpetion is thrown when running a job with gestures."""

    self.mock.get_testcase_info.return_value = {'testcase': {'gestures': 'yes'}}
    self.mock.Testcase.return_value = mock.Mock(job_type='good_job')

    with self.assertRaises(SystemExit):
      reproduce.execute(testcase_id='1234', current=False, build='standalone')

  def test_unsupported_job(self):
    """Tests to ensure an exception is thrown with an unsupported job type."""

    self.mock.get_testcase_info.return_value = {'testcase': {}}
    testcase = mock.Mock(id=1234, build_url='chrome_build_url',
                         revision=123456, job_type='fuzzlibber_xunil')
    self.mock.Testcase.return_value = testcase
    with self.assertRaises(SystemExit):
      reproduce.execute(testcase_id='1234', current=False, build='standalone')

  def test_download_no_defined_binary(self):
    """Test what happens when no binary name is defined."""
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_binary_definition'])
    self.mock.get_binary_definition.return_value = mock.Mock(
        binary_name=None, sanitizer='ASAN')
    self.mock.DownloadedBinary.return_value = mock.Mock(symbolizer_path=(
        '/path/to/symbolizer'))
    self.mock.DownloadedBinary.return_value.get_binary_path.return_value = (
        '/path/to/binary')
    stacktrace = [
        {'content': 'incorrect'}, {'content': '[Environment] A = b'},
        {'content': ('Running command: path/to/binary --args --arg2 '
                     '/path/to/testcase')}]
    testcase = mock.Mock(id=1234, build_url='chrome_build_url',
                         revision=123456, job_type='linux_asan_d8',
                         stacktrace_lines=stacktrace, reproducible=True,
                         reproduction_args='--always-opt')
    self.mock.Testcase.return_value = testcase
    reproduce.execute(testcase_id='1234', current=False, build='download')

    self.assert_exact_calls(self.mock.get_testcase_info, [mock.call('1234')])
    self.assert_n_calls(0, [self.mock.ensure_goma])
    self.assert_exact_calls(self.mock.Testcase, [mock.call(self.response)])
    self.assert_exact_calls(self.mock.DownloadedBinary,
                            [mock.call(1234, 'chrome_build_url', 'binary')])
    self.assert_exact_calls(
        self.mock.get_binary_definition.return_value.reproducer,
        [mock.call(self.mock.DownloadedBinary.return_value, testcase, 'ASAN')])

  def test_grab_data_with_download(self):
    """Ensures all method calls are made correctly when downloading."""

    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_binary_definition'])
    self.mock.get_binary_definition.return_value = mock.Mock(
        binary_name='binary', sanitizer='ASAN')
    self.mock.DownloadedBinary.return_value = mock.Mock(symbolizer_path=(
        '/path/to/symbolizer'))
    self.mock.DownloadedBinary.return_value.get_binary_path.return_value = (
        '/path/to/binary')
    stacktrace = [
        {'content': 'incorrect'}, {'content': '[Environment] A = b'},
        {'content': ('Running command: path/to/binary --args --arg2 '
                     '/path/to/testcase')}]
    testcase = mock.Mock(id=1234, build_url='chrome_build_url',
                         revision=123456, job_type='linux_asan_d8',
                         stacktrace_lines=stacktrace, reproducible=True)
    self.mock.Testcase.return_value = testcase
    reproduce.execute(testcase_id='1234', current=False, build='download')

    self.assert_exact_calls(self.mock.get_testcase_info, [mock.call('1234')])
    self.assert_n_calls(0, [self.mock.ensure_goma])
    self.assert_exact_calls(self.mock.Testcase, [mock.call(self.response)])
    self.assert_exact_calls(self.mock.DownloadedBinary,
                            [mock.call(1234, 'chrome_build_url', 'binary')])
    self.assert_exact_calls(
        self.mock.get_binary_definition.return_value.reproducer,
        [mock.call(self.mock.DownloadedBinary.return_value, testcase, 'ASAN')])

  def test_grab_data_standalone(self):
    """Ensures all method calls are made correctly when building locally."""

    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_binary_definition'])
    self.mock.get_binary_definition.return_value = mock.Mock(
        kwargs={}, source_var='V8_SRC', sanitizer='ASAN')
    (self.mock.get_binary_definition.return_value.builder.return_value
     .get_binary_path.return_value) = '/path/to/binary'
    (self.mock.get_binary_definition.return_value.builder.return_value
     .symbolizer_path) = '/path/to/symbolizer'
    testcase = mock.Mock(id=1234, build_url='chrome_build_url',
                         revision=123456, job_type='linux_asan_d8',
                         reproducible=True, reproduction_args='--always-opt')
    self.mock.Testcase.return_value = testcase
    reproduce.execute(testcase_id='1234', current=False, build='standalone')

    self.assert_exact_calls(self.mock.get_testcase_info, [mock.call('1234')])
    self.assert_exact_calls(self.mock.ensure_goma, [mock.call()])
    self.assert_exact_calls(self.mock.Testcase, [mock.call(self.response)])
    self.assert_exact_calls(
        self.mock.get_binary_definition.return_value.builder, [
            mock.call(testcase, self.mock.get_binary_definition.return_value,
                      False, '/goma/dir')])
    self.assert_exact_calls(
        self.mock.get_binary_definition.return_value.reproducer,
        [mock.call((self.mock.get_binary_definition.return_value.builder
                    .return_value), testcase, 'ASAN')])


class GetTestcaseInfoTest(helpers.ExtendedTestCase):
  """Test get_testcase_info."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.get_stored_auth_header',
        'clusterfuzz.common.store_auth_header',
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
        url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345',
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
            url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345',
            headers={'Authorization': 'Bearer 12345'}),
        mock.call(
            headers={'Authorization': 'VerificationCode 12345'},
            url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345')])
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
        url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345')])
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
            url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345',
            headers={'Authorization': 'Bearer 12345'}),
        mock.call(
            headers={'Authorization': 'VerificationCode 12345'},
            url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345')])

class GetVerificationHeaderTest(helpers.ExtendedTestCase):
  """Tests the get_verification_header method"""

  def setUp(self):
    helpers.patch(self, [
        'webbrowser.open',
        'clusterfuzz.common.ask'])
    self.mock.ask.return_value = '12345'

  def test_returns_correct_header(self):
    """Tests that the correct token with header is returned."""

    response = reproduce.get_verification_header()

    self.mock.open.assert_has_calls([mock.call(
        reproduce.GOOGLE_OAUTH_URL,
        new=1,
        autoraise=True)])
    self.assertEqual(response, 'VerificationCode 12345')


class EnsureGomaTest(helpers.ExtendedTestCase):
  """Tests the ensure_goma method."""

  def setUp(self):
    self.setup_fake_filesystem()
    self.mock_os_environment(
        {'GOMA_DIR': os.path.expanduser(os.path.join('~', 'goma'))})
    helpers.patch(self, ['clusterfuzz.common.execute'])

  def test_goma_not_installed(self):
    """Tests what happens when GOMA is not installed."""

    with self.assertRaises(common.GomaNotInstalledError) as ex:
      reproduce.ensure_goma()
      self.assertTrue('goma is not installed' in ex.message)

  def test_goma_installed(self):
    """Tests what happens when GOMA is installed."""

    goma_dir = os.path.expanduser(os.path.join('~', 'goma'))
    os.makedirs(goma_dir)
    f = open(os.path.join(goma_dir, 'goma_ctl.py'), 'w')
    f.close()

    result = reproduce.ensure_goma()

    self.assert_exact_calls(self.mock.execute, [
        mock.call(
            'python goma_ctl.py ensure_start', goma_dir,
            environment=os.environ)
    ])
    self.assertEqual(result, goma_dir)


class SuppressOutputTest(helpers.ExtendedTestCase):
  """Test SuppressOutput."""

  def setUp(self):
    helpers.patch(self, ['os.dup', 'os.open', 'os.close', 'os.dup2'])

    def dup(number):
      if number == 1:
        return 'out'
      elif number == 2:
        return 'err'
    self.mock.dup.side_effect = dup

  def test_suppress(self):
    """Test suppressing output."""
    with reproduce.SuppressOutput():
      pass

    self.assert_exact_calls(self.mock.dup, [mock.call(1), mock.call(2)])
    self.assert_exact_calls(self.mock.close, [mock.call(1), mock.call(2)])
    self.mock.open.assert_called_once_with(os.devnull, os.O_RDWR)
    self.assert_exact_calls(
        self.mock.dup2, [mock.call('out', 1), mock.call('err', 2)])

  def test_exception(self):
    """Test propagate exception."""
    with self.assertRaises(Exception) as cm:
      with reproduce.SuppressOutput():
        raise Exception('test_exc')

    self.assertEqual('test_exc', cm.exception.message)

    self.assert_exact_calls(self.mock.dup, [mock.call(1), mock.call(2)])
    self.assert_exact_calls(self.mock.close, [mock.call(1), mock.call(2)])
    self.mock.open.assert_called_once_with(os.devnull, os.O_RDWR)
    self.assert_exact_calls(
        self.mock.dup2, [mock.call('out', 1), mock.call('err', 2)])


class GetBinaryDefinitionTest(helpers.ExtendedTestCase):
  """Tests getting binary definitions."""

  def test_download_param(self):
    """Tests when the build_param is download"""

    result = reproduce.get_binary_definition('libfuzzer_chrome_msan',
                                             'download')
    self.assertEqual(result.builder, binary_providers.LibfuzzerMsanBuilder)

    with self.assertRaises(common.JobTypeNotSupportedError):
      result = reproduce.get_binary_definition('fuzzlibber_nasm', 'download')

  def test_build_param(self):
    """Tests when build_param is an option that requires building."""

    result = reproduce.get_binary_definition('libfuzzer_chrome_msan',
                                             'chromium')
    self.assertEqual(result.builder, binary_providers.LibfuzzerMsanBuilder)

    with self.assertRaises(common.JobTypeNotSupportedError):
      result = reproduce.get_binary_definition('fuzzlibber_nasm', 'chromium')
