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
import yaml

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

  header = common.get_stored_auth_header() or get_verification_header()
  response = None
  for _ in range(2):
    response = requests.post(
        url=url, headers={
            'Authorization': header,
            'User-Agent': 'clusterfuzz-tools'},
        allow_redirects=True, data=data)

    if response.status_code == 401:  # The access token expired.
      header = get_verification_header()
    else:  # Other errors or success
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

  common.execute('python', 'goma_ctl.py ensure_start', goma_dir)
  return goma_dir


def parse_job_definition(job_definition, presets):
  """Reads in a job definition hash and parses it."""

  to_return = {}
  if 'preset' in job_definition:
    to_return = parse_job_definition(presets[job_definition['preset']], presets)
  for key, val in job_definition.iteritems():
    if key == 'preset':
      continue
    to_return[key] = val

  return to_return


def build_binary_definition(job_definition, presets):
  """Converts a job definition hash into a binary definition."""

  builders = {
      'Chromium_32': binary_providers.ChromiumBuilder32Bit,
      'CfiChromium': binary_providers.CfiChromiumBuilder,
      'Chromium': binary_providers.ChromiumBuilder,
      'Pdfium': binary_providers.PdfiumBuilder,
      'V8': binary_providers.V8Builder,
      'V8_32': binary_providers.V8Builder32Bit,
  }
  reproducer_map = {'Base': reproducers.BaseReproducer,
                    'LibfuzzerJob': reproducers.LibfuzzerJobReproducer,
                    'LinuxChromeJob': reproducers.LinuxChromeJobReproducer}

  result = parse_job_definition(job_definition, presets)

  return common.BinaryDefinition(
      builders[result['builder']], result['source'],
      reproducer_map[result['reproducer']], result.get('binary'),
      result.get('sanitizer'), result.get('target'))


def get_supported_jobs():
  """Reads in supported jobs from supported_jobs.yml."""

  to_return = {
      'standalone': {},
      'chromium': {}}

  with open(common.get_resource(
      0640, 'resources', 'supported_job_types.yml')) as stream:
    job_types_yaml = yaml.load(stream)

  for build_type in ['standalone', 'chromium']:
    for job_type, job_definition in job_types_yaml[build_type].iteritems():
      try:
        to_return[build_type][job_type] = build_binary_definition(
            job_definition, job_types_yaml['presets'])
      except KeyError:
        raise common.BadJobTypeDefinitionError(
            '%s %s' % (build_type, job_type))

  return to_return


def get_binary_definition(job_type, build_param):
  supported_jobs = get_supported_jobs()
  if build_param != 'download' and job_type in supported_jobs[build_param]:
    return supported_jobs[build_param][job_type]
  else:
    for i in ['chromium', 'standalone']:
      if job_type in supported_jobs[i]:
        return supported_jobs[i][job_type]
  raise common.JobTypeNotSupportedError(job_type)


def maybe_warn_unreproducible(current_testcase):
  """Print warning if the testcase is unreproducible."""
  if not current_testcase.reproducible:
    print
    logger.info(
        'WARNING: The testcase %s is marked as unreproducible. Therefore, it '
        'might not be reproduced correctly here.', current_testcase.id)
    print
    # We need to return True to make the method testable because we can't mock
    # print.
    return True

@stackdriver_logging.log
def execute(testcase_id, current, build, disable_goma, j, iterations,
            disable_xvfb, target_args, edit_mode):
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
        current_testcase, definition, current, goma_dir, j, edit_mode)

  reproducer = definition.reproducer(
      binary_provider, current_testcase, definition.sanitizer, disable_xvfb,
      target_args, edit_mode)
  try:
    reproducer.reproduce(iterations)
  finally:
    maybe_warn_unreproducible(current_testcase)
