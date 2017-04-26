"""The main module for the CI server."""

import os
import subprocess
import shutil
import sys
import yaml
import requests

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
SANITY_CHECKS = '/python-daemon/daemon/sanity_checks.yml'
BINARY_LOCATION = '/python-daemon/clusterfuzz'
TOOL_SOURCE = os.path.join(HOME, 'clusterfuzz-tools')

def load_sanity_check_testcases():
  """Return a list of all testcases to try."""

  with open(SANITY_CHECKS) as stream:
    return yaml.load(stream)['testcases']


def build_command(args):
  """Returns the command to run the binary."""

  return '%s %s' % (BINARY_LOCATION, args)


def run_testcase(testcase_id):
  """Attempts to reproduce a testcase."""

  command = ('/python-daemon/clusterfuzz reproduce %s' % testcase_id)
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


def get_version():
  """Returns the version of the binary."""

  out = subprocess.check_output(build_command('supported_job_types'),
                                shell=True)
  return yaml.load(out)['Version']


def get_supported_jobtypes():
  """Returns a hash of supported job types."""

  out = subprocess.check_output(build_command('supported_job_types'),
                                shell=True)
  result = yaml.load(out)
  result.pop('Version', None)
  return result


def load_new_testcases(latest_testcase=None):
  """Returns a new list of testcases from clusterfuzz to run."""
  with open(AUTH_FILE_LOCATION, 'r') as f:
    auth_header = f.read()

  testcases = None
  page = 1
  supported_jobtypes = get_supported_jobtypes()
  while not testcases:
    r = requests.post('https://clusterfuzz.com/v2/testcases/load',
                      headers={'Authorization': auth_header},
                      json={'page': page, 'reproducible': 'yes'})
    testcases = r.json()['items']
    testcases = [testcase['id'] for testcase in testcases
                 if testcase['jobType'] in supported_jobtypes['chromium']]
    if latest_testcase in testcases:
      testcases = testcases[0:testcases.index(latest_testcase)]
    page += 1
  return testcases


def delete_if_exists(filename):
  """Delete filename if the file exists."""

  if os.path.exists(filename):
    shutil.rmtree(filename)


def call_with_depot_tools(command, cwd=CHROMIUM_SRC):
  """Run command with depot_tools in the path."""
  environment = os.environ.copy()
  path = environment.get('PATH')
  environment['PATH'] = '%s:%s' % (path, DEPOT_TOOLS) if path else DEPOT_TOOLS
  subprocess.check_call(command, cwd=cwd, env=environment, shell=True)


def checkout_build_master():
  """Checks out the latest master build and creates a new binary."""

  if not os.path.exists(TOOL_SOURCE):
    subprocess.check_call(('git clone https://github.com/google/clusterfuzz'
                           '-tools.git'), shell=True, cwd=HOME)
  subprocess.check_call('git pull', shell=True, cwd=TOOL_SOURCE)
  subprocess.check_call('./pants binary tool:clusterfuzz-ci', shell=True,
                        cwd=TOOL_SOURCE)
  os.remove(BINARY_LOCATION)
  shutil.copy(os.path.join(TOOL_SOURCE, 'dist', 'clusterfuzz-ci.pex'),
              BINARY_LOCATION)
  return subprocess.check_output('git rev-parse HEAD', shell=True,
                                 cwd=BINARY_LOCATION)


def reset_and_run_testcase(testcase_id, test_type, release):
  """Resets the chromium repo and runs the testcase."""

  delete_if_exists(CHROMIUM_OUT)
  delete_if_exists(CLUSTERFUZZ_DIR)
  version = get_version()
  if release == 'master':
    version = checkout_build_master()
  subprocess.check_call('git checkout -f master', shell=True, cwd=CHROMIUM_SRC)
  call_with_depot_tools('gclient sync')
  call_with_depot_tools('gclient runhooks')
  update_auth_header()
  stackdriver_logging.send_run(testcase_id, test_type, version,
                               run_testcase(testcase_id))


def main():
  release = sys.argv[1]
  clone_chromium.clone_chromium()
  testcases = load_sanity_check_testcases()
  for testcase in testcases:
    reset_and_run_testcase(testcase, 'sanity', release)
  latest_testcase = None
  while True:
    update_auth_header()
    testcases = load_new_testcases(latest_testcase)
    latest_testcase = testcases[0]
    for testcase in testcases:
      reset_and_run_testcase(testcase, 'continuous', release)

if __name__ == '__main__':
  main()
