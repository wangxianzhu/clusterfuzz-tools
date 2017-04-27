"""Tests the main module of the CI service."""
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

import cStringIO
import subprocess
import os
import sys
import mock
import yaml

from daemon import main
import helpers


class MainTest(helpers.ExtendedTestCase):
  """Test main."""

  def setUp(self):
    helpers.patch(self, ['daemon.main.load_sanity_check_testcases',
                         'daemon.main.reset_and_run_testcase',
                         'daemon.clone_chromium.clone_chromium',
                         'daemon.main.update_auth_header',
                         'daemon.main.load_new_testcases'])
    self.setup_fake_filesystem()
    self.mock.load_sanity_check_testcases.return_value = [1, 2]
    self.mock.load_new_testcases.side_effect = [[3, 4], [5]]
    self.mock.reset_and_run_testcase.side_effect = [None, None, None, None,
                                                    SystemExit]

  def test_correct_calls(self):
    """Ensure the main method makes the correct calls to reproduce."""

    with self.assertRaises(SystemExit):
      main.main()

    self.assert_exact_calls(self.mock.load_sanity_check_testcases,
                            [mock.call()])
    self.assert_exact_calls(self.mock.clone_chromium, [mock.call()])
    self.assert_exact_calls(self.mock.load_new_testcases, [mock.call(),
                                                           mock.call()])
    self.assert_exact_calls(self.mock.reset_and_run_testcase, [
        mock.call(1, 'sanity', sys.argv[1]),
        mock.call(2, 'sanity', sys.argv[1]),
        mock.call(3, 'continuous', sys.argv[1]),
        mock.call(4, 'continuous', sys.argv[1]),
        mock.call(5, 'continuous', sys.argv[1])])


class RunTestcaseTest(helpers.ExtendedTestCase):
  """Test the run_testcase method."""

  def setUp(self):
    helpers.patch(self, ['os.environ.copy',
                         'subprocess.Popen'])
    self.mock.Popen.return_value = mock.Mock(
        returncode=1, stdout=cStringIO.StringIO('Output\nChunks'))
    self.mock.copy.return_value = {'OS': 'ENVIRON'}

  def test_running_testcase(self):
    """Ensures testcases are run properly."""

    result = main.run_testcase(1234)
    home = os.path.expanduser('~')

    command = ('/bin/bash -c "export PATH=$PATH:%s/depot_tools && '
               '/python-daemon/clusterfuzz reproduce 1234"' % home)

    self.assertFalse(result)
    self.assert_exact_calls(self.mock.Popen, [mock.call(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.expanduser('~'),
        env={
            'OS': 'ENVIRON',
            'CF_QUIET': '1',
            'USER': 'CI',
            'CHROMIUM_SRC': main.CHROMIUM_SRC,
            'GOMA_GCE_SERVICE_ACCOUNT': 'default'},
        shell=True)])


class LoadSanityCheckTestcasesTest(helpers.ExtendedTestCase):
  """Tests the load_sanity_check_testcases method."""

  def setUp(self):
    self.setup_fake_filesystem()
    os.makedirs('/python-daemon/daemon')
    with open(main.SANITY_CHECKS, 'w') as f:
      f.write('testcases:\n')
      f.write('#ignore\n')
      f.write('        - 5899279404367872')

  def test_reading_testcases(self):
    """Ensures that testcases are read properly."""

    result = main.load_sanity_check_testcases()
    self.assertEqual(result, [5899279404367872])

class UpdateAuthHeadertest(helpers.ExtendedTestCase):
  """Tests the update_auth_header method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, ['oauth2client.client.GoogleCredentials'])
    (self.mock.GoogleCredentials._get_implicit_credentials.return_value. #pylint: disable=protected-access
     get_access_token.return_value) = mock.Mock(access_token='Access token')

  def test_proper_update(self):
    """Ensures that the auth key is updated properly."""

    self.assertFalse(os.path.exists(main.CLUSTERFUZZ_DIR))
    main.update_auth_header()

    with open(main.AUTH_FILE_LOCATION, 'r') as f:
      self.assertEqual(f.read(), 'Bearer Access token')


class GetVersionTest(helpers.ExtendedTestCase):
  """Tests the get_version method."""

  def setUp(self):
    helpers.patch(self, ['subprocess.check_output'])
    self.result = yaml.dump({
        'chromium': ['chrome_job', 'libfuzzer_job'],
        'standalone': ['pdf_job', 'v8_job'],
        'Version': '0.2.2rc11'})
    self.mock.check_output.return_value = self.result

  def test_get_version(self):
    result = main.get_version()
    self.assertEqual(result, '0.2.2rc11')


class GetSupportedJobtypesTest(helpers.ExtendedTestCase):
  """Tests the get_supported_jobtypes method."""

  def setUp(self):
    helpers.patch(self, ['subprocess.check_output'])
    self.result = yaml.dump({
        'chromium': ['chrome_job', 'libfuzzer_job'],
        'standalone': ['pdf_job', 'v8_job'],
        'Version': '0.2.2rc11'})
    self.mock.check_output.return_value = self.result

  def test_get_supported_jobtypes(self):
    """Tests get_supported_jobtypes."""

    result = main.get_supported_jobtypes()
    correct = yaml.load(self.result)
    correct.pop('Version')
    self.assertEqual(result, correct)


class LoadNewTestcasesTest(helpers.ExtendedTestCase):
  """Tests the load_new_testcases method."""

  def setUp(self): #pylint: disable=missing-docstring
    self.setup_fake_filesystem()
    os.makedirs(os.path.expanduser('~/.clusterfuzz'))
    with open(main.AUTH_FILE_LOCATION, 'w') as f:
      f.write('Bearer xyzabc')

    helpers.patch(self, ['daemon.main.get_supported_jobtypes',
                         'requests.post',
                         'random.randint'])
    self.mock.randint.return_value = 6
    self.mock.get_supported_jobtypes.return_value = {'chromium': [
        'supported', 'support']}

  def test_no_latest_testcase(self):
    """Tests when no previous tests have been run."""

    returned_json = {
        'items': [{'jobType': 'supported',
                   'id': 12345},
                  {'jobType': 'unsupported',
                   'id': 98765},
                  {'jobType': 'support',
                   'id': 23456},
                  {'jobType': 'supported',
                   'id': 23456}]}
    for i in range(0, 40):
      returned_json['items'].append({'jobType': 'supported', 'id': i})

    self.mock.post.return_value.json.return_value = returned_json

    main.TESTCASE_CACHE[39] = True
    main.TESTCASE_CACHE[38] = False
    result = main.load_new_testcases()
    correct_result = [12345, 23456]
    correct_result.extend(range(0, 39))
    self.assertEqual(result, correct_result)
    self.assert_exact_calls(self.mock.post, [mock.call(
        'https://clusterfuzz.com/v2/testcases/load',
        headers={'Authorization': 'Bearer xyzabc'},
        json={'page': 1,
              'reproducible': 'yes'})])


class ResetAndRunTestcaseTest(helpers.ExtendedTestCase):
  """Tests the reset_and_run_testcase method."""

  def setUp(self): #pylint: disable=missing-docstring
    self.setup_fake_filesystem()
    os.makedirs(main.CHROMIUM_OUT)
    os.makedirs(main.CLUSTERFUZZ_DIR)

    helpers.patch(self, ['subprocess.check_call',
                         'daemon.stackdriver_logging.send_run',
                         'daemon.main.update_auth_header',
                         'daemon.main.get_version',
                         'daemon.main.run_testcase',
                         'daemon.main.checkout_build_master'])
    self.mock.checkout_build_master.return_value = '0.2.2rc11'
    self.mock.get_version.return_value = '0.2.2rc10'
    self.mock.run_testcase.return_value = 'run_testcase'

  def test_reset_run_testcase(self):
    """Tests resetting a testcase properly prior to running."""

    self.assertTrue(os.path.exists(main.CHROMIUM_OUT))
    self.assertTrue(os.path.exists(main.CLUSTERFUZZ_DIR))
    main.reset_and_run_testcase(1234, 'sanity', 'master')
    self.assertFalse(os.path.exists(main.CHROMIUM_OUT))
    self.assertFalse(os.path.exists(main.CLUSTERFUZZ_DIR))
    self.assert_exact_calls(self.mock.update_auth_header, [
        mock.call()])
    self.assert_exact_calls(self.mock.send_run, [
        mock.call(1234, 'sanity', '0.2.2rc11', 'run_testcase')])
    environment = os.environ.copy()
    environment['PATH'] += ':%s' % main.DEPOT_TOOLS
    self.assert_exact_calls(self.mock.checkout_build_master, [mock.call()])
    self.assert_exact_calls(self.mock.check_call, [
        mock.call('git checkout -f master', shell=True, cwd=main.CHROMIUM_SRC),
        mock.call('gclient sync', shell=True, cwd=main.CHROMIUM_SRC,
                  env=environment),
        mock.call('gclient runhooks', shell=True, cwd=main.CHROMIUM_SRC,
                  env=environment)])


class CheckoutBuildMasterTest(helpers.ExtendedTestCase):
  """Tests the checkout_build_master method."""

  def setUp(self):
    helpers.patch(self, ['subprocess.check_call',
                         'subprocess.check_output',
                         'os.remove',
                         'shutil.copy',
                         'os.path.exists'])
    self.mock.exists.return_value = False

  def test_run_checkout_build_master(self):
    """Tests checking out & building from master."""

    main.checkout_build_master()
    self.assert_exact_calls(self.mock.check_call, [
        mock.call('git clone https://github.com/google/clusterfuzz-tools.git',
                  shell=True, cwd=main.HOME),
        mock.call('git pull', shell=True, cwd=main.TOOL_SOURCE),
        mock.call('./pants binary tool:clusterfuzz-ci', shell=True,
                  cwd=main.TOOL_SOURCE)])
    self.assert_exact_calls(self.mock.remove, [
        mock.call(main.BINARY_LOCATION)])
    self.assert_exact_calls(self.mock.copy, [
        mock.call(os.path.join(main.TOOL_SOURCE, 'dist', 'clusterfuzz-ci.pex'),
                  main.BINARY_LOCATION)])
    self.assert_exact_calls(self.mock.check_output, [
        mock.call('git rev-parse HEAD', shell=True, cwd=main.BINARY_LOCATION)])
