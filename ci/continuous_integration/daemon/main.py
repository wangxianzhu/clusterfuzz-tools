"""The main module for the CI server."""

import collections
import os
import shutil
import subprocess
import sys
import time
import yaml

import requests
from requests.packages.urllib3.util import retry
from requests import adapters
from oauth2client.client import GoogleCredentials
from lru import LRUCacheDict

import stackdriver_logging #pylint: disable=relative-import
import process #pylint: disable=relative-import


HOME = os.path.expanduser('~')
CLUSTERFUZZ_DIR = os.path.join(HOME, '.clusterfuzz')
CLUSTERFUZZ_CACHE_DIR = os.path.join(CLUSTERFUZZ_DIR, 'cache')
AUTH_FILE_LOCATION = os.path.join(CLUSTERFUZZ_CACHE_DIR, 'auth_header')
CHROMIUM_SRC = os.path.join(HOME, 'chromium', 'src')
CHROMIUM_OUT = os.path.join(CHROMIUM_SRC, 'out')
RELEASE_ENV = os.path.join(HOME, 'RELEASE_ENV')
DEPOT_TOOLS = os.path.join(HOME, 'depot_tools')
SANITY_CHECKS = '/python-daemon/daemon/sanity_checks.yml'
BINARY_LOCATION = '/python-daemon-data/clusterfuzz'
TOOL_SOURCE = os.path.join(HOME, 'clusterfuzz-tools')
TESTCASE_CACHE = LRUCacheDict(max_size=1000, expiration=172800)

# The number of seconds to sleep after each test run to avoid DDOS.
SLEEP_TIME = 30

Testcase = collections.namedtuple('Testcase', ['id', 'job_type'])


# Configuring backoff retrying because sending a request to ClusterFuzz
# might fail during a deployment.
http = requests.Session()
http.mount(
    'https://',
    adapters.HTTPAdapter(
        # backoff_factor is 0.5. Therefore, the max wait time is 16s.
        retry.Retry(
            total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504]))
)


def post(*args, **kwargs):  # pragma: no cover
  """Make a post request. This method is needed for mocking."""
  return http.post(*args, **kwargs)


def load_sanity_check_testcase_ids():
  """Return a list of all testcases to try."""
  with open(SANITY_CHECKS) as stream:
    return yaml.load(stream)['testcase_ids']


def build_command(args):
  """Returns the command to run the binary."""
  return '%s %s' % (BINARY_LOCATION, args)


def run_testcase(testcase_id):
  """Attempts to reproduce a testcase."""
  try:
    process.call(
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
  out = process.call(build_command('supported_job_types'), capture=True)
  return yaml.load(out)['Version']


def get_supported_jobtypes():
  """Returns a hash of supported job types."""
  out = process.call(build_command('supported_job_types'), capture=True)
  result = yaml.load(out)
  result.pop('Version', None)
  return result


def load_new_testcases():
  """Returns a new list of testcases from clusterfuzz to run."""

  with open(AUTH_FILE_LOCATION, 'r') as f:
    auth_header = f.read()

  testcases = []
  testcase_ids = set()
  page = 1
  supported_jobtypes = get_supported_jobtypes()

  def _is_valid(testcase):
    """Filter by jobtype and whether it has been successfully reproduced."""
    return (testcase['jobType'] in supported_jobtypes['chromium'] and
            not testcase['id'] in TESTCASE_CACHE and
            not testcase['id'] in testcase_ids)

  while len(testcases) < 40:
    r = post('https://clusterfuzz.com/v2/testcases/load',
             headers={'Authorization': auth_header},
             json={'page': page, 'reproducible': 'yes'})

    has_valid_testcase = False
    for testcase in r.json()['items']:
      if not _is_valid(testcase):
        continue

      testcases.append(Testcase(testcase['id'], testcase['jobType']))
      testcase_ids.add(testcase['id'])
      has_valid_testcase = True

    if not has_valid_testcase:
      break
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
    process.call(
        'git clone https://github.com/google/clusterfuzz-tools.git', cwd=HOME)
  process.call('git fetch', cwd=TOOL_SOURCE)
  process.call('git checkout origin/master -f', cwd=TOOL_SOURCE)
  process.call('./pants binary tool:clusterfuzz-ci', cwd=TOOL_SOURCE,
               env={'HOME': HOME})

  delete_if_exists(BINARY_LOCATION)
  shutil.copy(os.path.join(TOOL_SOURCE, 'dist', 'clusterfuzz-ci.pex'),
              BINARY_LOCATION)

  # The full SHA is too long and unpleasant to show in logs. So, we use the
  # first 7 characters of the SHA instead.
  return process.call(
      'git rev-parse HEAD', capture=True, cwd=TOOL_SOURCE).strip()[:7]


def prepare_binary_and_get_version(release):
  """Get version given the release name."""
  if release == 'master':
    return build_master_and_get_version()
  else:
    return get_binary_version()


def reset_and_run_testcase(testcase_id, category, release):
  """Resets the chromium repo and runs the testcase."""

  delete_if_exists(CHROMIUM_OUT)
  delete_if_exists(CLUSTERFUZZ_CACHE_DIR)
  process.call('git checkout -f HEAD', cwd=CHROMIUM_SRC)

  # Clean untracked files. Because untracked files in submodules are not removed
  # with `git checkout -f HEAD`.
  process.call('git clean -d -f -f', cwd=CHROMIUM_SRC)

  version = prepare_binary_and_get_version(release)
  update_auth_header()
  stackdriver_logging.send_run(
      testcase_id, category, version, release, run_testcase(testcase_id))


def main():
  release = sys.argv[1]

  for testcase_id in load_sanity_check_testcase_ids():
    reset_and_run_testcase(testcase_id, 'sanity', release)
    time.sleep(SLEEP_TIME)

  while True:
    update_auth_header()
    for testcase in load_new_testcases():
      reset_and_run_testcase(testcase.id, testcase.job_type, release)
      time.sleep(SLEEP_TIME)


if __name__ == '__main__':
  main()
