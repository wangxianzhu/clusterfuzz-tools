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
import logging

import requests

from clusterfuzz import common
from clusterfuzz import stackdriver_logging
from clusterfuzz import testcase
from clusterfuzz import binary_providers
from clusterfuzz import reproducers


CLUSTERFUZZ_AUTH_HEADER = 'x-clusterfuzz-authorization'
CLUSTERFUZZ_TESTCASE_INFO_URL = (
    'https://%s/v2/testcase-detail/refresh' % common.DOMAIN_NAME)
GOMA_DIR = os.path.expanduser(os.path.join('~', 'goma'))
GOOGLE_OAUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth?%s' % (
    urllib.urlencode({
        'scope': 'email profile',
        'client_id': ('981641712411-sj50drhontt4m3gjc3hordjmp'
                      'c7bn50f.apps.googleusercontent.com'),
        'response_type': 'code',
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'}))
SUPPORTED_JOBS = {
    'standalone': {
        'linux_asan_pdfium': common.BinaryDefinition(
            binary_providers.PdfiumBuilder, 'PDFIUM_SRC',
            reproducers.BaseReproducer, 'pdfium_test', sanitizer='ASAN'),
        'linux_msan_pdfium': common.BinaryDefinition(
            binary_providers.PdfiumBuilder, 'PDFIUM_SRC',
            reproducers.BaseReproducer, 'pdfium_test', sanitizer='MSAN'),
        'linux_asan_d8_dbg': common.BinaryDefinition(
            binary_providers.V8Builder, 'V8_SRC', reproducers.BaseReproducer,
            'd8', sanitizer='ASAN'),
        'linux_asan_d8': common.BinaryDefinition(
            binary_providers.V8Builder, 'V8_SRC', reproducers.BaseReproducer,
            'd8', sanitizer='ASAN'),
        'linux_asan_d8_v8_mipsel_db': common.BinaryDefinition(
            binary_providers.V8Builder, 'V8_SRC', reproducers.BaseReproducer,
            'd8', sanitizer='ASAN'),
        'linux_v8_d8_tot': common.BinaryDefinition(
            binary_providers.V8Builder, 'V8_SRC', reproducers.BaseReproducer,
            'd8', sanitizer='ASAN')},
    'chromium': {
        'linux_asan_pdfium': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.BaseReproducer, 'pdfium_test', sanitizer='ASAN'),
        'linux_msan_pdfium': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.BaseReproducer, 'pdfium_test', sanitizer='MSAN'),
        'libfuzzer_chrome_asan': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.BaseReproducer, sanitizer='ASAN'),
        'libfuzzer_chrome_asan_debug': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.BaseReproducer, sanitizer='ASAN'),
        'libfuzzer_chrome_msan': common.BinaryDefinition(
            binary_providers.LibfuzzerMsanBuilder, 'CHROMIUM_SRC',
            reproducers.BaseReproducer, sanitizer='MSAN'),
        'libfuzzer_chrome_ubsan': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.BaseReproducer, sanitizer='UBSAN'),
        'linux_ubsan_chrome': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.LinuxChromeJobReproducer, 'chrome',
            sanitizer='UBSAN', target='chromium_builder_asan'),
        'linux_msan_chrome': common.BinaryDefinition(
            binary_providers.MsanChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.LinuxChromeJobReproducer, 'chrome',
            sanitizer='MSAN', target='chromium_builder_asan'),
        'linux_asan_chrome_mp': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.LinuxChromeJobReproducer, 'chrome',
            sanitizer='ASAN', target='chromium_builder_asan'),
        'linux_asan_chrome_chromeos': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.LinuxChromeJobReproducer, 'chrome',
            sanitizer='ASAN', target='chromium_builder_asan'),
        'linux_asan_chrome_media': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.LinuxChromeJobReproducer, 'chrome',
            sanitizer='ASAN', target='chromium_builder_asan'),
        'linux_cfi_chrome': common.BinaryDefinition(
            binary_providers.CfiChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.LinuxChromeJobReproducer, 'chrome',
            sanitizer='ASAN', target='chromium_builder_asan'),
        'linux_asan_chrome_gpu': common.BinaryDefinition(
            binary_providers.ChromiumBuilder, 'CHROMIUM_SRC',
            reproducers.LinuxChromeJobReproducer, 'chrome',
            sanitizer='ASAN', target='chromium_builder_asan')}}
logger = logging.getLogger('clusterfuzz')

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
  logger.info(('We need to authenticate you in order to get information from '
               'ClusterFuzz.'))
  print

  logger.info('Open: %s', GOOGLE_OAUTH_URL)
  with SuppressOutput():
    webbrowser.open(GOOGLE_OAUTH_URL, new=1, autoraise=True)
  print

  verification = common.ask(
      'Please login on the opened webpage and enter your verification code',
      'Please enter a code', bool)
  return 'VerificationCode %s' % verification


def send_request(url, data):
  """Get a clusterfuzz url that requires authentication.

  Attempts to authenticate and is guaranteed to either
  return a valid, authorized response or throw an exception."""

  header = common.get_stored_auth_header()
  response = None
  for _ in range(2):
    if not header or (response is not None and response.status_code == 401):
      header = get_verification_header()
    response = requests.post(
        url=url, headers={
            'Authorization': header,
            'User-Agent': 'clusterfuzz-tools'},
        allow_redirects=True, data=data)
    if response.status_code == 200:
      break

  if response.status_code != 200:
    raise common.ClusterfuzzAuthError(response.text)
  common.store_auth_header(response.headers[CLUSTERFUZZ_AUTH_HEADER])

  return response

def get_testcase_info(testcase_id):
  """Pulls testcase information from Clusterfuzz.

  Returns a dictionary with the JSON response if the
  authentication is successful.
  """

  data = json.dumps({'testcaseId': testcase_id})
  return json.loads(send_request(CLUSTERFUZZ_TESTCASE_INFO_URL, data).text)

def ensure_goma():
  """Ensures GOMA is installed and ready for use, and starts it."""

  goma_dir = os.environ.get('GOMA_DIR', GOMA_DIR)
  if not os.path.isfile(os.path.join(goma_dir, 'goma_ctl.py')):
    raise common.GomaNotInstalledError()

  common.execute(
      'python goma_ctl.py ensure_start', goma_dir,
      environment=os.environ.copy())

  return goma_dir


def get_binary_definition(job_type, build_param):
  if build_param == 'download':
    for i in ['chromium', 'standalone']:
      if job_type in SUPPORTED_JOBS[i]:
        return SUPPORTED_JOBS[i][job_type]
  else:
    if job_type in SUPPORTED_JOBS[build_param]:
      return SUPPORTED_JOBS[build_param][job_type]
  raise common.JobTypeNotSupportedError(job_type)


def maybe_warn_unreproducible(current_testcase):
  """Print warning if the testcase is unreproducible."""
  if not current_testcase.reproducible:
    print
    logger.info(('WARNING: The testcase %s is marked as unreproducible. '
                 'Therefore, it might not be reproduced correctly here.'))
    print
    # We need to return True to make the method testable because we can't mock
    # print.
    return True

@stackdriver_logging.log
def execute(testcase_id, current, build, disable_goma, j,
            disable_gclient_commands, iterations):
  """Execute the reproduce command."""
  logger.info('Reproducing testcase %s', testcase_id)
  logger.debug('(testcase_id:%s, current=%s, build=%s, disable_goma=%s)',
               testcase_id, current, build, disable_goma)
  logger.info('Downloading testcase information...')

  response = get_testcase_info(testcase_id)
  current_testcase = testcase.Testcase(response)

  if 'gestures' in response['testcase']:
    logger.info(('Warning: testcases using gestures are still in development '
                 'and are not guaranteed to reproduce correctly.'))

  definition = get_binary_definition(current_testcase.job_type, build)

  maybe_warn_unreproducible(current_testcase)

  if build == 'download':
    if definition.binary_name:
      binary_name = definition.binary_name
    else:
      binary_name = common.get_binary_name(current_testcase.stacktrace_lines)
    binary_provider = binary_providers.DownloadedBinary(
        current_testcase.id, current_testcase.build_url, binary_name)
  else:
    goma_dir = None if disable_goma else ensure_goma()
    binary_provider = definition.builder( # pylint: disable=redefined-variable-type
        current_testcase, definition, current, goma_dir, j,
        disable_gclient_commands)

  reproducer = definition.reproducer(binary_provider, current_testcase,
                                     definition.sanitizer)
  reproducer.reproduce(iterations)
  maybe_warn_unreproducible(current_testcase)
