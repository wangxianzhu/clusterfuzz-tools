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
import zipfile
import mock

from clusterfuzz import common
from clusterfuzz.commands import reproduce
from test import helpers


class ExecuteTest(helpers.ExtendedTestCase):
  """Test execute."""

  def setUp(self):
    self.chrome_src = '/usr/local/google/home/user/repos/chromium/src'
    self.mock_os_environment({'CHROME_SRC': self.chrome_src})
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_testcase_info',
        'clusterfuzz.commands.reproduce.sha_from_revision',
        'clusterfuzz.commands.reproduce.checkout_chrome_by_sha',
        'clusterfuzz.commands.reproduce.download_build_data',
        'clusterfuzz.commands.reproduce.build_chrome',
        'clusterfuzz.commands.reproduce.get_reproduction_args',
        'clusterfuzz.commands.reproduce.download_testcase_file',
        'clusterfuzz.commands.reproduce.set_up_environment',
        'clusterfuzz.commands.reproduce.reproduce_crash'])
    self.mock.get_testcase_info.return_value = {
        'id': 1234,
        'crash_type': 'Bad Crash',
        'crash_state': ['halted'],
        'crash_revision': '123456',
        'metadata': {'build_url': 'chrome_build_url'},
        'crash_stacktrace': {'lines': ['Line 1', 'Line 2']}}
    self.mock.get_reproduction_args.return_value = '--random-seed=1234 --turbo'
    self.mock.download_testcase_file.return_value = os.path.join(
        reproduce.CLUSTERFUZZ_TESTCASES_DIR, '1234_testcase', 'testcase.js')
    self.mock.set_up_environment.return_value = 'NEW_ENV'

  def test_grab_data(self):
    """Ensures all method calls are made correctly."""
    self.mock.sha_from_revision.return_value = '1a2s3d4f'
    reproduce.execute('1234', False)

    self.assert_exact_calls(self.mock.get_testcase_info, [mock.call('1234')])
    self.assert_exact_calls(self.mock.sha_from_revision, [mock.call('123456')])
    self.assert_exact_calls(
        self.mock.checkout_chrome_by_sha,
        [mock.call('1a2s3d4f', self.chrome_src)])
    self.assert_exact_calls(self.mock.download_build_data,
                            [mock.call('chrome_build_url', 1234)])
    self.assert_exact_calls(self.mock.build_chrome,
                            [mock.call('123456', 1234, self.chrome_src)])


class GetTestcaseInfoTest(helpers.ExtendedTestCase):
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

class GetStoredAuthHeaderTest(helpers.ExtendedTestCase):
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

class StoreAuthHeaderTest(helpers.ExtendedTestCase):
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

class GetVerificationHeaderTest(helpers.ExtendedTestCase):
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


class BuildRevisionToShaUrlTest(helpers.ExtendedTestCase):
  """Tests the build_revision_to_sha_url method."""

  def setUp(self):
    helpers.patch(self, [
        'urlfetch.fetch'])

  def test_correct_url_building(self):
    """Tests if the SHA url is built correctly"""

    result = reproduce.build_revision_to_sha_url(12345)
    self.assertEqual(result, ('https://cr-rev.appspot.com/_ah/api/crrev/v1'
                              '/get_numbering?project=chromium&repo=v8%2Fv8'
                              '&number=12345&numbering_type='
                              'COMMIT_POSITION&numbering_identifier=refs'
                              '%2Fheads%2Fmaster'))


class ShaFromRevisionTest(helpers.ExtendedTestCase):
  """Tests the sha_from_revision method."""

  def setUp(self):
    helpers.patch(self, ['urlfetch.fetch'])

  def test_get_sha_from_response_body(self):
    """Tests to ensure that the sha is grabbed from the response correctly"""

    self.mock.fetch.return_value = mock.Mock(body=json.dumps({
        'id': 12345,
        'git_sha': '1a2s3d4f',
        'crash_type': 'Bad Crash'}))

    result = reproduce.sha_from_revision(123456)
    self.assertEqual(result, '1a2s3d4f')


class CheckConfirmTest(helpers.ExtendedTestCase):
  """Tests the check_confirm method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.confirm'])

  def test_answer_yes(self):
    self.mock.confirm.return_value = True
    reproduce.check_confirm('Question?')
    self.assert_exact_calls(self.mock.confirm, [mock.call('Question?')])

  def test_answer_no(self):
    self.mock.confirm.return_value = False
    with self.assertRaises(SystemExit):
      reproduce.check_confirm('Question?')
    self.assert_exact_calls(self.mock.confirm, [mock.call('Question?')])


class CheckoutChromeByShaTest(helpers.ExtendedTestCase):
  """Tests the checkout_chrome_by_sha method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.commands.reproduce.check_confirm'])
    self.chrome_source = '/usr/local/google/home/user/repos/chromium/src'
    self.command = ('git fetch && git checkout 1a2s3d4f'
                    ' in %s' % self.chrome_source)

  def test_not_already_checked_out(self):
    """Tests when the correct git sha is not already checked out."""

    self.mock.execute.return_value = [0, 'not_the_same']
    reproduce.checkout_chrome_by_sha('1a2s3d4f', self.chrome_source)

    self.assert_exact_calls(
        self.mock.execute,
        [mock.call('git rev-parse HEAD',
                   self.chrome_source,
                   print_output=False),
         mock.call('git fetch && git checkout 1a2s3d4f', self.chrome_source)])
    self.assert_exact_calls(self.mock.check_confirm,
                            [mock.call(
                                'Proceed with the following command:\n%s?' %
                                self.command)])
  def test_already_checked_out(self):
    """Tests when the correct git sha is already checked out."""

    self.mock.execute.return_value = [0, '1a2s3d4f']
    reproduce.checkout_chrome_by_sha('1a2s3d4f', self.chrome_source)

    self.assert_exact_calls(self.mock.execute,
                            [mock.call('git rev-parse HEAD',
                                       self.chrome_source,
                                       print_output=False)])
    self.assert_n_calls(0, [self.mock.check_confirm])


class DownloadBuildDataTest(helpers.ExtendedTestCase):
  """Tests the download_build_data test."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute'])

    self.setup_fake_filesystem()
    self.build_url = 'https://storage.cloud.google.com/abc.zip'

  def test_build_data_already_downloaded(self):
    """Tests the exit when build data is already returned."""

    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '12345_build')
    os.makedirs(build_dir)
    result = reproduce.download_build_data(self.build_url, 12345)
    self.assert_n_calls(0, [self.mock.execute])
    self.assertEqual(result, build_dir)

  def test_get_build_data(self):
    """Tests extracting, moving and renaming the build data.."""

    os.makedirs(self.clusterfuzz_dir)
    cf_builds_dir = os.path.join(self.clusterfuzz_dir, 'builds')

    with open(os.path.join(self.clusterfuzz_dir, 'args.gn'), 'w') as f:
      f.write('use_goma = True')
    fakezip = zipfile.ZipFile(
        os.path.join(self.clusterfuzz_dir, 'abc.zip'), 'w')
    fakezip.write(os.path.join(self.clusterfuzz_dir, 'args.gn'),\
                  'abc//args.gn', zipfile.ZIP_DEFLATED)
    fakezip.close()
    self.assertTrue(
        os.path.isfile(os.path.join(self.clusterfuzz_dir, 'abc.zip')))

    reproduce.download_build_data(self.build_url, 12345)

    self.assert_exact_calls(self.mock.execute, [mock.call(
        'gsutil cp gs://abc.zip .',
        self.clusterfuzz_dir)])
    self.assertFalse(
        os.path.isfile(os.path.join(self.clusterfuzz_dir, 'abc.zip')))
    self.assertTrue(os.path.isdir(
        os.path.join(cf_builds_dir, '12345_build')))
    self.assertTrue(os.path.isfile(os.path.join(
        cf_builds_dir,
        '12345_build',
        'args.gn')))
    with open(os.path.join(cf_builds_dir, '12345_build', 'args.gn'), 'r') as f:
      self.assertEqual('use_goma = True', f.read())


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
        mock.call('python goma_ctl.py ensure_start', goma_dir)])
    self.assertEqual(result, goma_dir)


class SetupGnArgsTest(helpers.ExtendedTestCase):
  """Tests the setup_gn_args method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.execute'])
    self.testcase_dir = os.path.expanduser(os.path.join('~', 'test_dir'))

  def test_args_setup(self):
    """Tests to ensure that the args.gn is setup correctly."""

    os.makedirs(self.testcase_dir)
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'w') as f:
      f.write('Not correct args.gn')
    build_dir = reproduce.get_build_directory(1234)
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir')

    reproduce.setup_gn_args(
        self.testcase_dir,
        1234,
        '/chrome/source/dir',
        '/goma/dir')

    self.assert_exact_calls(self.mock.execute, [
        mock.call('gn gen %s' % self.testcase_dir, '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(f.read(), 'goma_dir = /goma/dir\n')


class BuildChromeTest(helpers.ExtendedTestCase):
  """Tests the build_chrome method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.ensure_goma',
        'clusterfuzz.commands.reproduce.setup_gn_args',
        'multiprocessing.cpu_count',
        'clusterfuzz.common.execute'])
    self.mock.cpu_count.return_value = 12
    self.mock.ensure_goma.return_value = '/goma/dir'

  def test_correct_calls(self):
    """Tests the correct checks and commands are run to build."""

    revision_num = 12345
    testcase_id = 54321
    chrome_source = '/chrome/source'
    reproduce.build_chrome(revision_num, testcase_id, chrome_source)

    self.assert_exact_calls(self.mock.execute, [
        mock.call('GYP_DEFINES=asan=1 gclient runhooks', chrome_source),
        mock.call('GYP_DEFINES=asan=1 gypfiles/gyp_v8', chrome_source),
        mock.call(
            'ninja -C /chrome/source/out/clusterfuzz_54321 -j 120 d8',
            chrome_source)])
    self.assert_exact_calls(self.mock.ensure_goma, [mock.call()])
    self.assert_exact_calls(self.mock.setup_gn_args, [
        mock.call('/chrome/source/out/clusterfuzz_54321',
                  54321,
                  chrome_source,
                  '/goma/dir')])

class GetReproductionArgsTest(helpers.ExtendedTestCase):
  """Tests the get_reproduction_args method."""

  def test_join_args_strings(self):
    """Tests that the method joins all args correctly."""

    window_arg = '--random-seed=123456'
    min_arg = '--turbo --always-opt'
    args = {
        'window_argument': window_arg,
        'minimized_arguments': min_arg}
    testcase_info = {'testcase': args}

    result = reproduce.get_reproduction_args(testcase_info)
    self.assertEqual(result, '%s %s' % (window_arg, min_arg))

class DownloadTestcaseFileTest(helpers.ExtendedTestCase):
  """Tests the download_testcase_file method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_stored_auth_header',
        'clusterfuzz.common.execute'])
    self.mock.get_stored_auth_header.return_value = 'Bearer 1a2s3d4f'

  def test_already_downloaded(self):
    """Tests the scenario in which the testcase is already downloaded."""

    testcase_dir = reproduce.get_testcase_directory(1234567)
    filename = os.path.join(testcase_dir, 'testcase.js')
    os.makedirs(testcase_dir)
    with open(filename, 'w') as f:
      f.write('testcase exists')
    self.assertTrue(os.path.isfile(filename))

    result = reproduce.download_testcase_file(1234567)
    self.assertEqual(result, filename)
    self.assert_n_calls(0, [self.mock.get_stored_auth_header,
                            self.mock.execute])

  def test_not_already_downloaded(self):
    """Tests the creation of folders & downloading of the testcase"""
    testcase_dir = reproduce.get_testcase_directory(12345)
    filename = os.path.join(testcase_dir, 'testcase.js')
    self.assertFalse(os.path.exists(testcase_dir))

    result = reproduce.download_testcase_file(12345)

    self.assertEqual(result, filename)
    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.execute, [mock.call(
        ('wget --header="Authorization: %s" "%s" -O ./testcase.js' %
         (self.mock.get_stored_auth_header.return_value,
          reproduce.CLUSTERFUZZ_TESTCASE_URL % str(12345))),
        testcase_dir)])
    self.assertTrue(os.path.exists(testcase_dir))


class SetUpEnvironmentTest(helpers.ExtendedTestCase):
  """Tests the set_up_environment method."""

  def test_get_env_from_stacktrace(self):
    """Tests grabbing the os environment and adding the new vars from lines."""
    stacktrace_lines = [
        {'content': '[Environment] ASAN_OPTIONS = option1=true:option2=false'},
        {'content': '======== Stacktrace ======'},
        {'content':
         '[Environment] GOMA_OPTIONS = goma_dir=/goma/dir:use_goma=true'}]
    correct_env = {}
    correct_env['ASAN_OPTIONS'] = 'option1=true:option2=false'
    correct_env['GOMA_OPTIONS'] = 'goma_dir=/goma/dir:use_goma=true'

    result = reproduce.set_up_environment(stacktrace_lines)
    self.assertEqual(correct_env, result)


class ReproduceCrashTest(helpers.ExtendedTestCase):
  """Tests the reproduce_crash method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute'])

  def test_reproduce_crash(self):
    """Ensures that the crash reproduction is called correctly."""

    testcase_id = 123456
    testcase_file = '%s/testcase.js' % reproduce.get_testcase_directory(
        testcase_id)
    args = '--turbo --always-opt --random-seed=12345'
    source = '/chrome/source/folder'
    env = {'ASAN_OPTIONS': 'option1=true:option2=false'}

    reproduce.reproduce_crash(testcase_id, testcase_file, args, source, env)
    self.assert_exact_calls(self.mock.execute, [mock.call(
        '%s %s %s' % ('/chrome/source/folder/out/clusterfuzz_123456/d8',
                      args, testcase_file),
        '/chrome/source/folder/out/clusterfuzz_123456',
        environment=env)])
