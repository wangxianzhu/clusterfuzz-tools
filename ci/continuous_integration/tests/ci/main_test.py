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
import mock

from ci import main
import helpers


class MainTest(helpers.ExtendedTestCase):
  """Test main."""

  def setUp(self):
    helpers.patch(self, ['ci.main.install_latest_release',
                         'ci.main.load_sanity_check_testcases',
                         'ci.stackdriver_logging.send_run',
                         'ci.main.run_testcase',
                         'ci.clone_chromium.clone_chromium',
                         'ci.main.update_auth_header'])
    self.setup_fake_filesystem()
    self.mock.load_sanity_check_testcases.return_value = [1, 2]

  def test_correct_calls(self):
    """Ensure the main method makes the correct calls to reproduce."""

    os.makedirs(main.CHROMIUM_OUT)
    os.makedirs(main.CLUSTERFUZZ_BUILD)
    self.assertTrue(os.path.exists(main.CHROMIUM_OUT))
    self.assertTrue(os.path.exists(main.CLUSTERFUZZ_BUILD))
    main.main()

    self.assertFalse(os.path.exists(main.CHROMIUM_OUT))
    self.assertFalse(os.path.exists(main.CLUSTERFUZZ_BUILD))
    self.assert_exact_calls(self.mock.install_latest_release, [mock.call()])
    self.assert_exact_calls(self.mock.load_sanity_check_testcases,
                            [mock.call()])
    self.assert_exact_calls(self.mock.clone_chromium, [mock.call()])
    self.assert_n_calls(2, [self.mock.send_run, self.mock.run_testcase,
                            self.mock.update_auth_header])


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

    command = ('/bin/bash -c "export PATH=$PATH:%s/depot_tools && source'
               ' %s/RELEASE_ENV/bin/activate && %s/RELEASE_ENV/bin/clusterfuzz'
               ' reproduce 1234 -i 3"' % (home, home, home))

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
    os.makedirs('/python-daemon/ci')
    with open(main.SANITY_CHECKS, 'w') as f:
      f.write('testcases:\n')
      f.write('#ignore\n')
      f.write('        - 5899279404367872')

  def test_reading_testcases(self):
    """Ensures that testcases are read properly."""

    result = main.load_sanity_check_testcases()
    self.assertEqual(result, [5899279404367872])


class InstallLatestReleaseTest(helpers.ExtendedTestCase):
  """Tests the install_latest_release method."""

  def setUp(self):
    helpers.patch(self, ['subprocess.call'])

  def test_correct_calls(self):
    """Ensure the correct installation calls are made."""

    main.install_latest_release()

    self.assert_exact_calls(self.mock.call, [
        mock.call('virtualenv %s' % main.RELEASE_ENV, shell=True),
        mock.call(('/bin/bash -c "source %s/bin/activate && %s install'
                   ' --no-cache-dir clusterfuzz==0.2.2rc3"' %
                   (main.RELEASE_ENV, os.path.join(main.RELEASE_ENV,
                                                   'bin', 'pip'))),
                  shell=True)])


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
