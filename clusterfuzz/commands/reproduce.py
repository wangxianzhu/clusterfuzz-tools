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
import sys
import json
import urllib
import webbrowser
import stat
import zipfile
import multiprocessing
import urlfetch

from clusterfuzz import common

CLUSTERFUZZ_DIR = os.path.expanduser(os.path.join('~', '.clusterfuzz'))
CLUSTERFUZZ_BUILDS_DIR = os.path.join(CLUSTERFUZZ_DIR, 'builds')
CLUSTERFUZZ_TESTCASES_DIR = os.path.join(CLUSTERFUZZ_DIR, 'testcases')
AUTH_HEADER_FILE = os.path.join(CLUSTERFUZZ_DIR, 'auth_header')
TOKENINFO_URL = ('https://www.googleapis.com/oauth2/v3/tokeninfo'
                 '?access_token=%s')
CLUSTERFUZZ_AUTH_HEADER = 'x-clusterfuzz-authorization'
CLUSTERFUZZ_TESTCASE_URL = ('https://cluster-fuzz.appspot.com/v2/testcase-'
                            'detail/download-testcase/oauth?id=%s')
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

def get_stored_auth_header():
  """Checks whether there is a valid auth key stored locally."""
  if not os.path.isfile(AUTH_HEADER_FILE):
    return None

  can_group_access = bool(os.stat(AUTH_HEADER_FILE).st_mode & 0070)
  can_other_access = bool(os.stat(AUTH_HEADER_FILE).st_mode & 0007)

  if can_group_access or can_other_access:
    raise common.PermissionsTooPermissiveError(
        AUTH_HEADER_FILE,
        oct(os.stat(AUTH_HEADER_FILE).st_mode & 0777))

  with open(AUTH_HEADER_FILE, 'r') as f:
    return f.read()


def get_verification_header():
  """Prompts the user for & returns a verification token."""

  webbrowser.open(GOOGLE_OAUTH_URL, new=1, autoraise=True)
  verification = raw_input('Please enter your verification code:')
  return 'VerificationCode %s' % verification


def store_auth_header(auth_header):
  """Stores 'auth_header' locally for future access."""

  if not os.path.exists(os.path.dirname(AUTH_HEADER_FILE)):
    os.makedirs(os.path.dirname(AUTH_HEADER_FILE))

  with open(AUTH_HEADER_FILE, 'w') as f:
    f.write(auth_header)
  os.chmod(AUTH_HEADER_FILE, stat.S_IWUSR|stat.S_IRUSR)


def send_request(url):
  """Get a clusterfuzz url that requires authentication.

  Attempts to authenticate and is guaranteed to either
  return a valid, authorized response or throw an exception."""

  header = get_stored_auth_header()
  response = None
  for _ in range(2):
    if not header or (response and response.status == 401):
      header = get_verification_header()
    response = urlfetch.fetch(url=url, headers={'Authorization': header})
    if response.status == 200:
      break

  if response.status != 200:
    raise common.ClusterfuzzAuthError(response.body)
  store_auth_header(response.headers[CLUSTERFUZZ_AUTH_HEADER])

  return response

def get_testcase_info(testcase_id):
  """Pulls testcase information from Clusterfuzz.

  Returns a dictionary with the JSON response if the
  authentication is successful.
  """

  url = CLUSTERFUZZ_TESTCASE_INFO_URL % testcase_id
  return json.loads(send_request(url).body)


def build_revision_to_sha_url(revision):
  return ('https://cr-rev.appspot.com/_ah/api/crrev/v1/get_numbering?%s' %
          urllib.urlencode({
              'number': revision,
              'numbering_identifier': 'refs/heads/master',
              'numbering_type': 'COMMIT_POSITION',
              'project': 'chromium',
              'repo': 'v8/v8'})) #TODO: Change this based on testcase JSON


def sha_from_revision(revision_number):
  """Converts a chrome revision number to it corresponding git sha."""

  response = urlfetch.fetch(build_revision_to_sha_url(revision_number))
  return json.loads(response.body)['git_sha']


def check_confirm(question):
  """Exits the program if the answer is negative, does nothing otherwise."""

  if not common.confirm(question):
    sys.exit()


def checkout_chrome_by_sha(sha, chrome_source):
  """Checks out the correct Chrome revision."""

  _, current_sha = common.execute('git rev-parse HEAD',
                                  chrome_source,
                                  print_output=False)
  if current_sha.strip() == sha:
    return

  command = 'git fetch && git checkout %s' % sha
  check_confirm('Proceed with the following command:\n%s in %s?' %
                (command, chrome_source))
  common.execute(command, chrome_source)


def get_build_directory(testcase_id):
  """Returns a build number's respective directory."""

  return os.path.join(
      CLUSTERFUZZ_BUILDS_DIR,
      str(testcase_id) + '_build')


def get_out_dir(chrome_source, testcase_id):
  return os.path.join(chrome_source, 'out', 'clusterfuzz_' + str(testcase_id))


def get_testcase_directory(testcase_id):
  """Returns a testcases' respective directory."""

  return os.path.join(
      CLUSTERFUZZ_TESTCASES_DIR,
      str(testcase_id) + '_testcase')


def download_build_data(build_url, testcase_id):
  """Downloads a build and saves it locally."""

  build_dir = get_build_directory(testcase_id)
  if os.path.exists(build_dir):
    return build_dir

  print 'Downloading build data...'

  if not os.path.exists(CLUSTERFUZZ_BUILDS_DIR):
    os.makedirs(CLUSTERFUZZ_BUILDS_DIR)

  gsutil_path = build_url.replace('https://storage.cloud.google.com/', 'gs://')
  common.execute('gsutil cp %s .' % gsutil_path, CLUSTERFUZZ_DIR)

  filename = os.path.split(gsutil_path)[1]
  saved_file = os.path.join(CLUSTERFUZZ_DIR, filename)

  print 'Extracting...'
  zipped_file = zipfile.ZipFile(saved_file, 'r')
  zipped_file.extractall(CLUSTERFUZZ_BUILDS_DIR)
  zipped_file.close()

  print 'Cleaning up...'
  os.remove(saved_file)
  os.rename(os.path.join(CLUSTERFUZZ_BUILDS_DIR, os.path.splitext(filename)[0]),
            build_dir)


def ensure_goma():
  """Ensures GOMA is installed and ready for use, and starts it."""

  goma_dir = os.environ.get('GOMA_DIR', GOMA_DIR)
  if not os.path.isfile(os.path.join(goma_dir, 'goma_ctl.py')):
    raise common.GomaNotInstalledError()

  common.execute('python goma_ctl.py ensure_start', goma_dir)
  return goma_dir


def setup_gn_args(testcase_source_dir, testcase_id, chrome_source, goma_dir):
  """Ensures that args.gn is sety up properly."""

  args_gn_location = os.path.join(testcase_source_dir, 'args.gn')
  if os.path.isfile(args_gn_location):
    os.remove(args_gn_location)

  common.execute('gn gen %s' % testcase_source_dir, chrome_source)

  lines = []
  with open(os.path.join(
      get_build_directory(testcase_id),
      'args.gn'), 'r') as f:
    lines = [l.strip() for l in f.readlines()]

  with open(args_gn_location, 'w') as f:
    for line in lines:
      if 'goma_dir' in line:
        line = 'goma_dir = ' + goma_dir
      f.write(line)
      f.write('\n')


def build_chrome(revision_number, testcase_id, chrome_source):
  """Build the correct revision of chrome in the source directory."""

  testcase_source_dir = get_out_dir(chrome_source, testcase_id)
  print 'Building Chrome revision %i in %s' % (
      revision_number,
      testcase_source_dir)

  goma_dir = ensure_goma()
  setup_gn_args(testcase_source_dir, testcase_id, chrome_source, goma_dir)

  goma_cores = 10 * multiprocessing.cpu_count()
  common.execute('GYP_DEFINES=asan=1 gclient runhooks', chrome_source)
  common.execute('GYP_DEFINES=asan=1 gypfiles/gyp_v8', chrome_source)
  common.execute(
      ('ninja -C %s -j %i d8'
       % (testcase_source_dir, goma_cores)),
      chrome_source)


def get_reproduction_args(testcase_info):
  """Gets all needed args from testcase info and returns a single string"""

  return '%s %s' % (testcase_info['testcase']['window_argument'],
                    testcase_info['testcase']['minimized_arguments'])


def download_testcase_file(testcase_id):
  """Downloads & saves the correct testcase for reproduction."""

  testcase_dir = get_testcase_directory(testcase_id)
  filename = os.path.join(testcase_dir, 'testcase.js')
  if os.path.isfile(filename):
    return filename

  print 'Downloading testcase data...'

  if not os.path.exists(CLUSTERFUZZ_TESTCASES_DIR):
    os.makedirs(CLUSTERFUZZ_TESTCASES_DIR)
  os.makedirs(testcase_dir)

  auth_header = get_stored_auth_header()
  command = 'wget --header="Authorization: %s" "%s" -O ./testcase.js' % (
      auth_header, CLUSTERFUZZ_TESTCASE_URL % testcase_id)
  common.execute(command, testcase_dir)

  return filename


def set_up_environment(stacktrace_lines):
  """Sets up the environment by parsing stacktrace lines."""

  new_env = {}
  stacktrace_lines = [l['content']  for l in stacktrace_lines]
  for l in stacktrace_lines:
    if '[Environment] ' not in l:
      continue
    l = l.replace('[Environment] ', '')
    name, value = l.split(' = ')
    new_env[name] = value

  return new_env


def reproduce_crash(testcase_id, testcase_file, args, source, env):
  """Reproduces a specific crash."""

  binary_dir = get_out_dir(source, testcase_id)
  binary = '%s/d8' % binary_dir
  command = '%s %s %s' % (binary, args, testcase_file)

  common.execute(command, binary_dir, environment=env)

def execute(testcase_id, current):
  """Execute the reproduce command."""

  print 'Reproduce %s (current=%s)' % (testcase_id, current)
  print 'Downloading testcase information...'

  response = get_testcase_info(testcase_id)

  chrome_source = os.environ['CHROME_SRC']
  crash_revision = response['crash_revision']
  testcase_id = response['id']
  if not current:
    git_sha = sha_from_revision(crash_revision)
    checkout_chrome_by_sha(git_sha, chrome_source)

  download_build_data(
      response['metadata']['build_url'],
      testcase_id)
  build_chrome(crash_revision, testcase_id, chrome_source)

  reproduction_args = get_reproduction_args(response)
  testcase_file = download_testcase_file(testcase_id)
  env = set_up_environment(response['crash_stacktrace']['lines'])
  reproduce_crash(testcase_id, testcase_file,
                  reproduction_args, chrome_source, env)
