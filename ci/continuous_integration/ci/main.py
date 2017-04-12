"""The main module for the CI server."""

import os
import subprocess
import shutil
import yaml

import stackdriver_logging #pylint: disable=relative-import
import clone_chromium #pylint: disable=relative-import

from oauth2client.client import GoogleCredentials

HOME = os.path.expanduser('~')
CLUSTERFUZZ_DIR = os.path.join(HOME, '.clusterfuzz')
AUTH_FILE_LOCATION = os.path.join(CLUSTERFUZZ_DIR, 'auth_header')
CLUSTERFUZZ_BUILD = os.path.join(CLUSTERFUZZ_DIR, 'builds')
CHROMIUM_SRC = os.path.join(HOME, 'chromium', 'src')
CHROMIUM_OUT = os.path.join(CHROMIUM_SRC, 'out')
RELEASE_ENV = os.path.join(HOME, 'RELEASE_ENV')
DEPOT_TOOLS = os.path.join(HOME, 'depot_tools')
SANITY_CHECKS = '/python-daemon/ci/sanity_checks.yml'

def install_latest_release():
  """Ensures the installed release of clusterfuzz is up to date."""
  subprocess.call('virtualenv %s' % RELEASE_ENV, shell=True)
  subprocess.call(('/bin/bash -c "source %s/bin/activate && %s install '
                   '--no-cache-dir clusterfuzz==0.2.2rc3"' %
                   (RELEASE_ENV, os.path.join(RELEASE_ENV, 'bin', 'pip'))),
                  shell=True)


def load_sanity_check_testcases():
  """Return a list of all testcases to try."""

  with open(SANITY_CHECKS) as stream:
    return yaml.load(stream)['testcases']


def run_testcase(testcase_id):
  """Attempts to reproduce a testcase."""

  command = ('source %s/bin/activate && %s reproduce %s -i 3'
             % (RELEASE_ENV, os.path.join(RELEASE_ENV, 'bin', 'clusterfuzz'),
                testcase_id))
  command = '/bin/bash -c "export PATH=$PATH:%s && %s"' % (DEPOT_TOOLS, command)
  environment = os.environ.copy()
  environment['CF_QUIET'] = '1'
  environment['USER'] = 'CI'
  environment['CHROMIUM_SRC'] = CHROMIUM_SRC
  environment['GOMA_GCE_SERVICE_ACCOUNT'] = 'default'
  print environment
  print command
  proc = subprocess.Popen(
      command,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      cwd=os.path.expanduser('~'),
      env=environment,
      shell=True)
  output_chunks = []
  for chunk in iter(lambda: proc.stdout.read(100), b''):
    output_chunks.append(chunk)
  proc.wait()
  resulting_output = ''.join(output_chunks)
  print resulting_output
  return proc.returncode == 0


def update_auth_header():
  """Sets the correct auth token in the clusterfuzz dir."""

  service_credentials = GoogleCredentials.get_application_default()
  if not os.path.exists(CLUSTERFUZZ_DIR):
    os.makedirs(CLUSTERFUZZ_DIR)
  new_auth_token = service_credentials.get_access_token()
  with open(AUTH_FILE_LOCATION, 'w') as f:
    f.write('Bearer %s' % new_auth_token.access_token)
  os.chmod(AUTH_FILE_LOCATION, 0600)


def main():
  clone_chromium.clone_chromium()
  install_latest_release()
  testcases = load_sanity_check_testcases()
  for testcase in testcases:
    if os.path.exists(CHROMIUM_OUT):
      shutil.rmtree(CHROMIUM_OUT)
    if os.path.exists(CLUSTERFUZZ_DIR):
      shutil.rmtree(CLUSTERFUZZ_DIR)
    update_auth_header()

    stackdriver_logging.send_run(
        testcase, 'sanity', '0.2.2rc3', run_testcase(testcase))


if __name__ == '__main__':
  main()
