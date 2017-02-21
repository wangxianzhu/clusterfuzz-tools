"""Module for the 'reproduce' command.

Locally reproduces a testcase given a Clusterfuzz ID."""
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
import urllib
import webbrowser
import urlfetch

from clusterfuzz import common
from clusterfuzz import testcase
from clusterfuzz import binary_providers

CLUSTERFUZZ_AUTH_HEADER = 'x-clusterfuzz-authorization'
CLUSTERFUZZ_TESTCASE_INFO_URL = ('https://cluster-fuzz.appspot.com/v2/'
                                 'testcase-detail/oauth?testcaseId=%s')
GOMA_DIR = os.path.expanduser(os.path.join('~', 'goma'))
GOOGLE_OAUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth?%s' % (
    urllib.urlencode({
        'scope': 'email profile',
        'client_id': ('981641712411-sj50drhontt4m3gjc3hordjmp'
                      'c7bn50f.apps.googleusercontent.com'),
        'response_type': 'code',
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'}))

def get_verification_header():
  """Prompts the user for & returns a verification token."""

  webbrowser.open(GOOGLE_OAUTH_URL, new=1, autoraise=True)
  verification = common.ask('Please enter your verification code',
                            'Please enter a code', bool)
  return 'VerificationCode %s' % verification


def send_request(url):
  """Get a clusterfuzz url that requires authentication.

  Attempts to authenticate and is guaranteed to either
  return a valid, authorized response or throw an exception."""

  header = common.get_stored_auth_header()
  response = None
  for _ in range(2):
    if not header or (response and response.status == 401):
      header = get_verification_header()
    response = urlfetch.fetch(url=url, headers={'Authorization': header})
    if response.status == 200:
      break

  if response.status != 200:
    raise common.ClusterfuzzAuthError(response.body)
  common.store_auth_header(response.headers[CLUSTERFUZZ_AUTH_HEADER])

  return response

def get_testcase_info(testcase_id):
  """Pulls testcase information from Clusterfuzz.

  Returns a dictionary with the JSON response if the
  authentication is successful.
  """

  url = CLUSTERFUZZ_TESTCASE_INFO_URL % testcase_id
  return json.loads(send_request(url).body)

def ensure_goma():
  """Ensures GOMA is installed and ready for use, and starts it."""

  goma_dir = os.environ.get('GOMA_DIR', GOMA_DIR)
  if not os.path.isfile(os.path.join(goma_dir, 'goma_ctl.py')):
    raise common.GomaNotInstalledError()

  common.execute('python goma_ctl.py ensure_start', goma_dir)
  return goma_dir


def reproduce_crash(binary_path, current_testcase):
  """Reproduces a crash by running the downloaded testcase against a binary."""

  env = current_testcase.environment
  #This will need to be dynamic as more jobs are added:
  symbolizer_variable = 'ASAN_SYMBOLIZER_PATH'
  if not os.environ.get(symbolizer_variable):
    raise common.SymbolizerPathError(symbolizer_variable)

  env[symbolizer_variable] = os.environ[symbolizer_variable]
  env['ASAN_OPTIONS'] = env['ASAN_OPTIONS'].replace(
      'symbolize=0', 'symbolize=1')
  if 'symbolize=1' not in env['ASAN_OPTIONS']:
    env['ASAN_OPTIONS'] += ':symbolize=1'

  command = '%s %s %s' % (binary_path, current_testcase.reproduction_args,
                          current_testcase.get_testcase_path())
  common.execute(command, os.path.dirname(binary_path),
                 environment=env)


def execute(testcase_id, current, download):
  """Execute the reproduce command."""

  print 'Reproduce %s (current=%s)' % (testcase_id, current)
  print 'Downloading testcase information...'

  response = get_testcase_info(testcase_id)
  goma_dir = ensure_goma()
  current_testcase = testcase.Testcase(response)
  v8_keywords = ('d8', 'v8')
  if any(s in current_testcase.job_type for s in v8_keywords):
    target = 'd8'
  else:
    target = 'pdfium_test'

  if download:
    binary_provider = binary_providers.DownloadedBinary(
        current_testcase.id, current_testcase.build_url, target)
  else:
    if target == 'd8':
      binary_provider = binary_providers.V8Builder( # pylint: disable=redefined-variable-type
          current_testcase.id, current_testcase.build_url,
          current_testcase.revision, current, goma_dir,
          os.environ.get('V8_SRC'))
    else:
      binary_provider = binary_providers.ChromiumBuilder( # pylint: disable=redefined-variable-type
          current_testcase.id, current_testcase.build_url,
          current_testcase.revision, current, goma_dir, os.environ.get(
              'CHROME_SRC'), 'pdfium_test')


  reproduce_crash(binary_provider.get_binary_path(), current_testcase)
