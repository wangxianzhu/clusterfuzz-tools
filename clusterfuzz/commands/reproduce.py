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
import urlfetch

from clusterfuzz import common

AUTH_HEADER_FILE = os.path.expanduser(
    os.path.join('~', '.clusterfuzz', 'auth_header'))
TOKENINFO_URL = ('https://www.googleapis.com/oauth2/v3/tokeninfo'
                 '?access_token=%s')
CLUSTERFUZZ_AUTH_HEADER = 'x-clusterfuzz-authorization'
CLUSTERFUZZ_TESTCASE_URL = ('https://cluster-fuzz.appspot.com/v2/'
                            'testcase-detail/oauth?testcaseId=%s')
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


def get_testcase_info(testcase_id):
  """Pulls testcase information from Clusterfuzz.

  Returns a dictionary with the JSON response if the
  authentication is successful, or throws a
  ClusterfuzzAuthError otherwise.
  """

  header = get_stored_auth_header()
  response = None
  for _ in range(2):
    if not header or (response and response.status == 401):
      header = get_verification_header()
    response = urlfetch.fetch(
        url=CLUSTERFUZZ_TESTCASE_URL % testcase_id,
        headers={'Authorization': header})
    if response.status == 200:
      break

  body = json.loads(response.body)
  if response.status != 200:
    raise common.ClusterfuzzAuthError(body)

  store_auth_header(response.headers[CLUSTERFUZZ_AUTH_HEADER])
  return body


def build_revision_to_sha_url(revision):
  return ('https://cr-rev.appspot.com/_ah/api/crrev/v1/get_numbering?%s' %
          urllib.urlencode({
              'number': revision,
              'numbering_identifier': 'refs/heads/master',
              'numbering_type': 'COMMIT_POSITION',
              'project': 'chromium',
              'repo': 'chromium/src'}))


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

  command = 'git fetch && git checkout %s' % sha
  check_confirm('Proceed with the following command:\n%s in %s?' %
                (command, chrome_source))
  common.execute(command, chrome_source)


def execute(testcase_id, current):
  """Execute the reproduce command."""

  print 'Reproduce %s (current=%s)' % (testcase_id, current)
  print 'Downloading testcase information...'

  response = get_testcase_info(testcase_id)
  chrome_source = os.environ['CHROME_SRC']

  if not current:
    git_sha = sha_from_revision(response['crash_revision'])
    checkout_chrome_by_sha(git_sha, chrome_source)

  print 'Testcase ID: %i' % response['id']
  print 'Crash Type: %s' % response['crash_type']
  print 'Crash State: %s' % ', '.join(response['crash_state'])
