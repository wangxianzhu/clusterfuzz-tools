"""Sends the results of CI testing to stackdriver."""

import json

from httplib2 import Http
from oauth2client.service_account import ServiceAccountCredentials


def send_log(params, success):
  """Send a log to Stackdriver with the result of a testcase run."""

  scopes = ['https://www.googleapis.com/auth/logging.write']
  filename = '/python-daemon/service-account-credentials.json'

  credentials = ServiceAccountCredentials.from_json_keyfile_name(
      filename, scopes=scopes)

  http_auth = credentials.authorize(Http())

  structure = {
      'logName': 'projects/clusterfuzz-tools/logs/ci',
      'resource': {
          'type': 'project',
          'labels': {
              'project_id': 'clusterfuzz-tools'}},
      'entries': [{
          'jsonPayload': params,
          'severity': 'INFO' if success else 'ERROR'}]}

  http_auth.request(
      uri='https://logging.googleapis.com/v2/entries:write',
      method='POST',
      body=json.dumps(structure))


def send_run(testcase_id, testcase_type, version, success):
  if success:
    message = '%s reproduced %s successfully.' % (version, testcase_id)
  else:
    message = '%s failed to reproduce %s.' % (version, testcase_id)

  send_log(
      params={
          'testcaseId': testcase_id,
          'type': testcase_type, # Sanity check or pulled testcase
          'version': version,
          'message': message
      },
      success=success)
