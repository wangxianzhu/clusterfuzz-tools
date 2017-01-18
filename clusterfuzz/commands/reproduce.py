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

import json
import urllib
import webbrowser
import urlfetch

from clusterfuzz.common import ClusterfuzzAuthError

CLUSTERFUZZ_AUTH_HEADER = 'x-clusterfuzz-authorization'
CLUSTERFUZZ_TESTCASE_URL = 'https://cluster-fuzz.appspot.com/v2/testcase-detail/oauth?testcaseId=%s'
GOOGLE_OAUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth?%s' % (
    urllib.urlencode({
        'scope': 'email profile',
        'client_id': ('981641712411-sj50drhontt4m3gjc3hordjmp'
                      'c7bn50f.apps.googleusercontent.com'),
        'response_type': 'code',
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'}))


def get_testcase_info(testcase_id, auth):
  """Pulls testcase information from Clusterfuzz.

  Returns a dictionary with the JSON response if the
  authentication is successful, or throws a
  ClusterfuzzAuthError otherwise.
  """

  response = urlfetch.fetch(
      url=CLUSTERFUZZ_TESTCASE_URL % testcase_id,
      headers={'Authorization': auth})

  body = json.loads(response.body)

  if response.status != 200:
    raise ClusterfuzzAuthError(body)

  return body

def execute(testcase_id, current):
  """Execute the reproduce command."""

  print 'Reproduce %s (current=%s)' % (testcase_id, current)

  webbrowser.open(GOOGLE_OAUTH_URL, new=1, autoraise=True)
  code = raw_input('Please enter your verification code:')

  print 'Downloading testcase information...'

  response = get_testcase_info(
      testcase_id,
      'VerificationCode %s' % code)

  print 'Testcase ID: %i' % response['id']
  print 'Crash Type: %s' % response['crash_type']
  print 'Crash State: %s' % ', '.join(response['crash_state'])
