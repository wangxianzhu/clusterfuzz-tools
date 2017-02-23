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
import multiprocessing
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
STANDALONE_SUPPORTED_JOBS = {
    'linux_asan_pdfium': common.BinaryDefinition(binary_providers.PdfiumBuilder,
                                                 'PDFIUM_SRC', 'pdfium_test'),
    'linux_asan_d8_dbg': common.BinaryDefinition(binary_providers.V8Builder,
                                                 'V8_SRC', 'd8'),
    'linux_asan_d8': common.BinaryDefinition(binary_providers.V8Builder,
                                             'V8_SRC', 'd8'),
    'linux_asan_d8_v8_mipsel_db': common.BinaryDefinition(
        binary_providers.V8Builder, 'V8_SRC', 'd8'),
    'linux_v8_d8_tot': common.BinaryDefinition(binary_providers.V8Builder,
                                               'V8_SRC', 'd8')}

CHROMIUM_SUPPORTED_JOBS = {
    'linux_asan_pdfium': common.BinaryDefinition(binary_providers.PdfiumBuilder,
                                                 'PDFIUM_SRC', 'pdfium_test')}


class SuppressOutput(object):
  """Suppress stdout and stderr. We need this because there's no way to suppress
    webbrowser's stdout and stderr."""

  def __enter__(self):
    self.stdout = os.dup(1)
    self.stderr = os.dup(2)
    os.close(1)
    os.close(2)
    os.open(os.devnull, os.O_RDWR)

  def __exit__(self, unused_type, unused_value, unused_traceback):
    os.dup2(self.stdout, 1)
    os.dup2(self.stderr, 2)


def get_verification_header():
  """Prompts the user for & returns a verification token."""
  print
  print ('We need to authenticate you in order to get information from '
         'ClusterFuzz.')
  print

  print 'Open: %s' % GOOGLE_OAUTH_URL
  with SuppressOutput():
    webbrowser.open(GOOGLE_OAUTH_URL, new=1, autoraise=True)
  print

  verification = common.ask(
      'Please login on the opened webpage and enter your verification code',
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

  cpu_count = multiprocessing.cpu_count()
  # We need to discount cpu_count, otherwise the whole machine would lag because
  # goma would be using all cpus.
  cpu_count -= int(cpu_count / 4)
  common.execute(
      'python goma_ctl.py restart', goma_dir,
      # According to: https://groups.google.com/a/google.com/forum/#!topic/chrome-security-bugs--/iYlumEXRWto  # pylint: disable=line-too-long
      environment=dict(
          os.environ,
          GOMA_MAX_SUBPROCS_HEAVY=str(int(cpu_count / 2)),
          GOMA_MAX_SUBPROCS=str(cpu_count),
          GOMA_MAX_SUBPROCS_LOW=str(cpu_count),
      ))

  return goma_dir


def reproduce_crash(binary_path, symbolizer_path, current_testcase):
  """Reproduces a crash by running the downloaded testcase against a binary."""

  env = current_testcase.environment
  env['ASAN_SYMBOLIZER_PATH'] = symbolizer_path
  env['ASAN_OPTIONS'] = env['ASAN_OPTIONS'].replace(
      'symbolize=0', 'symbolize=1')
  if 'symbolize=1' not in env['ASAN_OPTIONS']:
    env['ASAN_OPTIONS'] += ':symbolize=1'
  env['LSAN_OPTIONS'] = ''

  command = '%s %s %s' % (binary_path, current_testcase.reproduction_args,
                          current_testcase.get_testcase_path())
  common.execute(command, os.path.dirname(binary_path),
                 environment=env)


def get_binary_definition(job_type, supported_dict):
  if job_type not in supported_dict:
    raise common.JobTypeNotSupportedError(job_type)
  return supported_dict[job_type]


def execute(testcase_id, current, build):
  """Execute the reproduce command."""

  print 'Reproduce %s (current=%s)' % (testcase_id, current)
  print 'Downloading testcase information...'

  response = get_testcase_info(testcase_id)
  goma_dir = ensure_goma()
  current_testcase = testcase.Testcase(response)

  if build == 'download':
    definition = get_binary_definition(current_testcase.job_type,
                                       STANDALONE_SUPPORTED_JOBS)
    binary_provider = binary_providers.DownloadedBinary(
        current_testcase.id, current_testcase.build_url, definition.binary_name)
  elif build == 'standalone':
    definition = get_binary_definition(current_testcase.job_type,
                                       STANDALONE_SUPPORTED_JOBS)
    binary_provider = definition.builder( # pylint: disable=redefined-variable-type
        current_testcase.id, current_testcase.build_url,
        current_testcase.revision, current, goma_dir,
        os.environ.get(definition.source_var), **definition.kwargs)
  else:
    definition = get_binary_definition(current_testcase.job_type,
                                       CHROMIUM_SUPPORTED_JOBS)
    binary_provider = binary_providers.ChromiumBuilder( # pylint: disable=redefined-variable-type
        current_testcase.id, current_testcase.build_url,
        current_testcase.revision, current, goma_dir, os.environ.get(
            'CHROME_SRC'), definition.binary_name)

  reproduce_crash(binary_provider.get_binary_path(),
                  binary_provider.get_symbolizer_path(), current_testcase)
