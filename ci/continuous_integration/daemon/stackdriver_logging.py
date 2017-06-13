"""Sends the results of CI testing to stackdriver."""

import json

from httplib2 import Http
from oauth2client.service_account import ServiceAccountCredentials
from error import error


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


def send_run(testcase_id, testcase_type, version, release, return_code):
  """Send log to Stackdriver."""
  error_name = ''
  success = return_code == 0

  if success:
    message = '%s (%s) reproduced %s successfully (%s).' % (
        version, release, testcase_id, testcase_type)
  else:
    error_name = error.get_class_name(return_code)
    message = (
        '%s (%s) failed to reproduce %s (%s, %s).' %
        (version, release, testcase_id, testcase_type, error_name))

  send_log(
      params={
          'testcaseId': testcase_id,
          'type': testcase_type, # Sanity check or pulled testcase
          'version': version,
          'message': message,
          'release': release,
          'returnCode': return_code,
          'error': error_name
      },
      success=success)
