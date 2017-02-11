"""Classes to download, build and provide binaries for reproduction."""
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
import stat
import zipfile
import multiprocessing
import urllib
import json
import urlfetch

from clusterfuzz import common

CLUSTERFUZZ_DIR = os.path.expanduser(os.path.join('~', '.clusterfuzz'))
CLUSTERFUZZ_BUILDS_DIR = os.path.join(CLUSTERFUZZ_DIR, 'builds')

def build_revision_to_sha_url(revision, repo):
  return ('https://cr-rev.appspot.com/_ah/api/crrev/v1/get_numbering?%s' %
          urllib.urlencode({
              'number': revision,
              'numbering_identifier': 'refs/heads/master',
              'numbering_type': 'COMMIT_POSITION',
              'project': 'chromium',
              'repo': repo}))


def sha_from_revision(revision, repo):
  """Converts a chrome revision number to it corresponding git sha."""

  response = urlfetch.fetch(build_revision_to_sha_url(revision, repo))
  return json.loads(response.body)['git_sha']


class BinaryProvider(object):
  """Downloads/builds and then provides the location of a binary."""

  def __init__(self, testcase_id, build_url):
    self.testcase_id = testcase_id
    self.build_url = build_url
    self.build_directory = None
    self.target = 'd8'

  def get_build_directory(self):
    """Get build directory. This method must be implemented by a subclass."""
    raise NotImplementedError

  def download_build_data(self):
    """Downloads a build and saves it locally."""

    build_dir = self.build_dir_name()
    if os.path.exists(build_dir):
      return build_dir

    print 'Downloading build data...'
    if not os.path.exists(CLUSTERFUZZ_BUILDS_DIR):
      os.makedirs(CLUSTERFUZZ_BUILDS_DIR)

    gsutil_path = self.build_url.replace(
        'https://storage.cloud.google.com/', 'gs://')
    common.execute('gsutil cp %s .' % gsutil_path, CLUSTERFUZZ_DIR)

    filename = os.path.split(gsutil_path)[1]
    saved_file = os.path.join(CLUSTERFUZZ_DIR, filename)

    print 'Extracting...'
    zipped_file = zipfile.ZipFile(saved_file, 'r')
    zipped_file.extractall(CLUSTERFUZZ_BUILDS_DIR)
    zipped_file.close()

    print 'Cleaning up...'
    os.remove(saved_file)
    os.rename(os.path.join(CLUSTERFUZZ_BUILDS_DIR,
                           os.path.splitext(filename)[0]), build_dir)
    binary_location = os.path.join(build_dir, self.target)
    stats = os.stat(binary_location)
    os.chmod(binary_location, stats.st_mode | stat.S_IEXEC)

  def get_binary_path(self):
    return '%s/%s' % (self.get_build_directory(), self.target)

  def build_dir_name(self):
    """Returns a build number's respective directory."""
    return os.path.join(CLUSTERFUZZ_BUILDS_DIR,
                        str(self.testcase_id) + '_build')


class V8DownloadedBinary(BinaryProvider):
  """Uses a downloaded binary."""

  def get_build_directory(self):
    """Returns the location of the correct build to use for reproduction."""

    if self.build_directory:
      return self.build_directory

    self.download_build_data()
    self.build_directory = self.build_dir_name()
    return self.build_directory


class V8Builder(BinaryProvider):
  """Builds a fresh v8 binary."""

  def __init__(self, testcase_id, build_url, revision, current, goma_dir,
               source):
    super(V8Builder, self).__init__(testcase_id, build_url)
    self.current = current
    self.goma_dir = goma_dir
    self.source_directory = source
    self.revision = revision
    self.git_sha = sha_from_revision(self.revision, 'v8/v8')

  def out_dir_name(self):
    return os.path.join(self.source_directory, 'out',
                        'clusterfuzz_' + str(self.testcase_id))

  def checkout_source_by_sha(self):
    """Checks out the correct revision."""

    _, current_sha = common.execute('git rev-parse HEAD',
                                    self.source_directory,
                                    print_output=False)
    if current_sha.strip() == self.git_sha:
      return

    command = 'git fetch && git checkout %s' % self.git_sha
    common.check_confirm('Proceed with the following command:\n%s in %s?' %
                         (command, self.source_directory))
    common.execute(command, self.source_directory)

  def setup_gn_args(self):
    """Ensures that args.gn is sety up properly."""

    args_gn_location = os.path.join(self.build_directory, 'args.gn')
    if os.path.isfile(args_gn_location):
      os.remove(args_gn_location)

    common.execute('gn gen %s' % self.build_directory, self.source_directory)

    lines = []
    with open(os.path.join(self.build_dir_name(), 'args.gn'), 'r') as f:
      lines = [l.strip() for l in f.readlines()]

    with open(args_gn_location, 'w') as f:
      for line in lines:
        if 'goma_dir' in line:
          line = 'goma_dir = ' + self.goma_dir
        f.write(line)
        f.write('\n')

  def build_target(self):
    """Build the correct revision in the source directory."""

    print 'Building revision %i in %s' % (
        self.revision,
        self.build_directory)

    self.setup_gn_args()
    goma_cores = 10 * multiprocessing.cpu_count()
    common.execute('GYP_DEFINES=asan=1 gclient runhooks', self.source_directory)
    common.execute('GYP_DEFINES=asan=1 gypfiles/gyp_v8', self.source_directory)
    common.execute(
        ('ninja -C %s -j %i %s'
         % (self.build_directory, goma_cores, self.target)),
        self.source_directory)

  def get_build_directory(self):
    """Returns the location of the correct build to use for reproduction."""

    if self.build_directory:
      return self.build_directory

    self.download_build_data()
    self.build_directory = self.build_dir_name()
    if not self.source_directory:
      message = ('This is a V8 testcase, please define $V8_SRC or enter'
                 ' your V8 source location here')
      self.source_directory = os.path.expanduser(
          common.ask(message, 'Please enter a valid directory',
                     lambda x: x and os.path.isdir(os.path.expanduser(x))))
    if not self.current:
      self.checkout_source_by_sha()
    self.build_directory = self.out_dir_name()
    self.build_target()

    return self.build_directory
