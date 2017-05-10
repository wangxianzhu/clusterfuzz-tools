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
from lru import LRUCacheDict


HOME = os.path.expanduser('~')
CLUSTERFUZZ_DIR = os.path.join(HOME, '.clusterfuzz')
CLUSTERFUZZ_CACHE_DIR = os.path.join(CLUSTERFUZZ_DIR, 'cache')
AUTH_FILE_LOCATION = os.path.join(CLUSTERFUZZ_CACHE_DIR, 'auth_header')
CHROMIUM_SRC = os.path.join(HOME, 'chromium', 'src')
CHROMIUM_OUT = os.path.join(CHROMIUM_SRC, 'out')
RELEASE_ENV = os.path.join(HOME, 'RELEASE_ENV')
DEPOT_TOOLS = os.path.join(HOME, 'depot_tools')
SANITY_CHECKS = '/python-daemon/daemon/sanity_checks.yml'
BINARY_LOCATION = '/python-daemon/clusterfuzz'
TOOL_SOURCE = os.path.join(HOME, 'clusterfuzz-tools')
TESTCASE_CACHE = LRUCacheDict(max_size=1000, expiration=172800)


def load_sanity_check_testcases():
  """Return a list of all testcases to try."""
  with open(SANITY_CHECKS) as stream:
    return yaml.load(stream)['testcases']


def build_command(args):
  """Returns the command to run the binary."""
  return '%s %s' % (BINARY_LOCATION, args)


def call(cmd, cwd='.', env=None, capture=False):
  """Call invoke command with additional envs and return output."""
  env = env or {}
  env_str = ' '.join(
      ['%s="%s"' % (k, v) for k, v in env.iteritems()])
  print ('Running:\n  cmd: %s %s\n  cwd: %s' % (env_str, cmd, cwd)).strip()

  final_env = os.environ.copy()
  final_env.update(env)

  fn = subprocess.check_output if capture else subprocess.check_call
  return fn(cmd, shell=True, cwd=cwd, env=final_env)


def run_testcase(testcase_id):
  """Attempts to reproduce a testcase."""
  try:
    call(
        '/python-daemon/clusterfuzz reproduce %s' % testcase_id,
        cwd=HOME,
        env={
            'CF_QUIET': '1',
            'USER': 'CI',
            'CHROMIUM_SRC': CHROMIUM_SRC,
            'GOMA_GCE_SERVICE_ACCOUNT': 'default',
            'PATH': '%s:%s' % (os.environ['PATH'], DEPOT_TOOLS)
        }
    )
    success = True
  except subprocess.CalledProcessError:
    success = False

  TESTCASE_CACHE[testcase_id] = success
  return success


def update_auth_header():
  """Sets the correct auth token in the clusterfuzz dir."""

  service_credentials = GoogleCredentials.get_application_default()
  if not os.path.exists(CLUSTERFUZZ_CACHE_DIR):
    os.makedirs(CLUSTERFUZZ_CACHE_DIR)
  new_auth_token = service_credentials.get_access_token()

  with open(AUTH_FILE_LOCATION, 'w') as f:
    f.write('Bearer %s' % new_auth_token.access_token)
  os.chmod(AUTH_FILE_LOCATION, 0600)


def get_binary_version():
  """Returns the version of the binary."""
  out = call(build_command('supported_job_types'), capture=True)
  return yaml.load(out)['Version']


def get_supported_jobtypes():
  """Returns a hash of supported job types."""
  out = call(build_command('supported_job_types'), capture=True)
  result = yaml.load(out)
  result.pop('Version', None)
  return result


def load_new_testcases():
  """Returns a new list of testcases from clusterfuzz to run."""

  with open(AUTH_FILE_LOCATION, 'r') as f:
    auth_header = f.read()

  testcases = []
  page = 1
  supported_jobtypes = get_supported_jobtypes()

  def _validate_testcase(testcase):
    """Filter by jobtype and whether it has been successfully reproduced."""
    return (testcase['jobType'] in supported_jobtypes['chromium'] and not
            (testcase['id'] in TESTCASE_CACHE and
             TESTCASE_CACHE[testcase['id']]))

  while len(testcases) < 40:
    r = requests.post('https://clusterfuzz.com/v2/testcases/load',
                      headers={'Authorization': auth_header},
                      json={'page': page, 'reproducible': 'yes'})
    new_testcases = r.json()['items']
    new_testcases = [testcase['id'] for testcase in new_testcases
                     if _validate_testcase(testcase)]
    testcases.extend(t for t in new_testcases if t not in testcases)
    page += 1
  return testcases


def delete_if_exists(path):
  """Delete filename if the file exists."""
  if os.path.isdir(path):
    shutil.rmtree(path, True)
  elif os.path.exists(path):
    os.remove(path)


def build_master_and_get_version():
  """Checks out the latest master build and creates a new binary."""
  if not os.path.exists(TOOL_SOURCE):
    call('git clone https://github.com/google/clusterfuzz-tools.git', cwd=HOME)
  call('git fetch', cwd=TOOL_SOURCE)
  call('git checkout origin/master -f', cwd=TOOL_SOURCE)
  call('./pants binary tool:clusterfuzz-ci', cwd=TOOL_SOURCE,
       env={'HOME': HOME})

  delete_if_exists(BINARY_LOCATION)
  shutil.copy(os.path.join(TOOL_SOURCE, 'dist', 'clusterfuzz-ci.pex'),
              BINARY_LOCATION)

  return call('git rev-parse HEAD', capture=True, cwd=TOOL_SOURCE).strip()


def prepare_binary_and_get_version(release):
  """Get version given the release name."""
  if release == 'master':
    return build_master_and_get_version()
  else:
    return get_binary_version()


def reset_and_run_testcase(testcase_id, test_type, release):
  """Resets the chromium repo and runs the testcase."""

  delete_if_exists(CHROMIUM_OUT)
  delete_if_exists(CLUSTERFUZZ_CACHE_DIR)
  call('git checkout -f HEAD', cwd=CHROMIUM_SRC)

  version = prepare_binary_and_get_version(release)
  update_auth_header()
  stackdriver_logging.send_run(
      testcase_id, test_type, version, run_testcase(testcase_id))


def main():
  release = sys.argv[1]
  clone_chromium.clone_chromium()

  for testcase in load_sanity_check_testcases():
    reset_and_run_testcase(testcase, 'sanity', release)

  while True:
    update_auth_header()
    for testcase in load_new_testcases():
      reset_and_run_testcase(testcase, 'continuous', release)


if __name__ == '__main__':
  main()
