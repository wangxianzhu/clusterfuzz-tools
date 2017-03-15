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
import base64
import string
import logging
import urlfetch

from clusterfuzz import common

CLUSTERFUZZ_DIR = os.path.expanduser(os.path.join('~', '.clusterfuzz'))
CLUSTERFUZZ_BUILDS_DIR = os.path.join(CLUSTERFUZZ_DIR, 'builds')
logger = logging.getLogger('clusterfuzz')

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


def get_pdfium_sha(chromium_sha):
  """Gets the correct Pdfium sha using the Chromium sha."""
  response = urlfetch.fetch(
      ('https://chromium.googlesource.com/chromium/src.git/+/%s/DEPS?'
       'format=TEXT' % chromium_sha))
  body = base64.b64decode(response.body)
  sha_line = [l for l in body.split('\n') if "'pdfium_revision':" in l][0]
  sha_line = sha_line.translate(None, string.punctuation).replace(
      'pdfiumrevision', '')
  return sha_line.strip()


class BinaryProvider(object):
  """Downloads/builds and then provides the location of a binary."""

  def __init__(self, testcase_id, build_url, binary_name):
    self.testcase_id = testcase_id
    self.build_url = build_url
    self.build_directory = None
    self.binary_name = binary_name

  def get_build_directory(self):
    """Get build directory. This method must be implemented by a subclass."""
    raise NotImplementedError

  def download_build_data(self):
    """Downloads a build and saves it locally."""

    build_dir = self.build_dir_name()
    binary_location = os.path.join(build_dir, self.binary_name)
    if os.path.exists(build_dir):
      return build_dir

    logger.info('Downloading build data...')
    if not os.path.exists(CLUSTERFUZZ_BUILDS_DIR):
      os.makedirs(CLUSTERFUZZ_BUILDS_DIR)

    gsutil_path = self.build_url.replace(
        'https://storage.cloud.google.com/', 'gs://')
    common.execute('gsutil cp %s .' % gsutil_path, CLUSTERFUZZ_DIR)

    filename = os.path.split(gsutil_path)[1]
    saved_file = os.path.join(CLUSTERFUZZ_DIR, filename)

    logger.info('Extracting...')
    zipped_file = zipfile.ZipFile(saved_file, 'r')
    zipped_file.extractall(CLUSTERFUZZ_BUILDS_DIR)
    zipped_file.close()

    logger.info('Cleaning up...')
    os.remove(saved_file)
    os.rename(os.path.join(CLUSTERFUZZ_BUILDS_DIR,
                           os.path.splitext(filename)[0]), build_dir)
    stats = os.stat(binary_location)
    os.chmod(binary_location, stats.st_mode | stat.S_IEXEC)

  def get_binary_path(self):
    return '%s/%s' % (self.get_build_directory(), self.binary_name)

  def build_dir_name(self):
    """Returns a build number's respective directory."""
    return os.path.join(CLUSTERFUZZ_BUILDS_DIR,
                        str(self.testcase_id) + '_build')


class DownloadedBinary(BinaryProvider):
  """Uses a downloaded binary."""

  def get_build_directory(self):
    """Returns the location of the correct build to use for reproduction."""

    if self.build_directory:
      return self.build_directory

    self.download_build_data()
    self.build_directory = self.build_dir_name()
    return self.build_directory


class GenericBuilder(BinaryProvider):
  """Provides a base for binary builders."""

  def __init__(self, testcase_id, build_url, revision, current, goma_dir,
               source, binary_name, target=None):
    """self.git_sha must be set in a subclass, or some of these
    instance methods may not work."""
    super(GenericBuilder, self).__init__(testcase_id, build_url, binary_name)
    self.target = target if target else binary_name
    self.current = current
    self.goma_dir = goma_dir
    self.source_directory = source
    self.revision = revision
    self.gn_args_options = None
    self.gn_flags = '--check'

  def get_current_sha(self):
    _, current_sha = common.execute('git rev-parse HEAD',
                                    self.source_directory,
                                    print_output=False)
    return current_sha.strip()

  def out_dir_name(self):
    """Returns the correct out dir in which to build the revision.

    Directory name is of the format clusterfuzz_<testcase_id>_<git_sha>,
    with a possible '_dirty' on the end. Based on the current git sha, and
    whether changes have been made to the repo."""

    dir_name = os.path.join(self.source_directory, 'out',
                            'clusterfuzz_%s_%s' % (str(self.testcase_id),
                                                   self.get_current_sha()))
    _, diff_result = common.execute('git diff', self.source_directory,
                                    print_output=False)
    if diff_result:
      dir_name += '_dirty'
    return dir_name

  def checkout_source_by_sha(self):
    """Checks out the correct revision."""

    if self.get_current_sha() == self.git_sha:
      return

    command = 'git fetch && git checkout %s' % self.git_sha
    common.check_confirm('Proceed with the following command:\n%s in %s?' %
                         (command, self.source_directory))
    common.execute(command, self.source_directory)

  def deserialize_gn_args(self, args):
    """Convert gn args into a dict."""

    args_hash = {}
    for line in args:
      key, val = line.split(' = ')
      args_hash[key] = val
    return args_hash

  def serialize_gn_args(self, args_hash):
    args = []
    for key, val in args_hash.iteritems():
      args.append('%s = %s' % (key, val))
    return args

  def setup_gn_goma_params(self, gn_args):
    """Ensures that goma_dir and gn_goma are used correctly."""

    if not self.goma_dir or (
        'use_goma' in gn_args and gn_args['use_goma'] == 'false'):
      self.goma_dir = False
      gn_args.pop('goma_dir', None)
      gn_args['use_goma'] = 'false'
    else:
      gn_args['goma_dir'] = '"%s"' % self.goma_dir
    return gn_args

  def setup_gn_args(self):
    """Ensures that args.gn is set up properly."""

    args_gn_location = os.path.join(self.build_directory, 'args.gn')
    if os.path.isfile(args_gn_location):
      os.remove(args_gn_location)

    if not os.path.exists(self.build_directory):
      os.makedirs(self.build_directory)

    lines = []
    with open(os.path.join(self.build_dir_name(), 'args.gn'), 'r') as f:
      lines = [l.strip() for l in f.readlines()]

    args_hash = self.deserialize_gn_args(lines)
    args_hash = self.setup_gn_goma_params(args_hash)
    lines = self.serialize_gn_args(args_hash)

    with open(args_gn_location, 'w') as f:
      for line in lines:
        f.write(line)
        f.write('\n')
      if self.gn_args_options:
        for k, v in self.gn_args_options.iteritems():
          f.write('%s = %s\n' % (k, v))

    common.execute('gn gen %s %s' % (self.gn_flags, self.build_directory),
                   self.source_directory)

  def pre_build_steps(self):
    """Steps to be run before the target is built."""

    pass

  def get_goma_cores(self):
    """Choose the correct amount of GOMA cores for a build."""

    cpu_count = multiprocessing.cpu_count()
    return 10 * cpu_count if self.goma_dir else (3 * cpu_count) / 4

  def build_target(self):
    """Build the correct revision in the source directory."""

    self.pre_build_steps()
    common.execute('gclient sync', self.source_directory)
    #Note: gclient sync must be run before setting up the gn args
    self.setup_gn_args()
    goma_cores = self.get_goma_cores()
    common.execute(
        ("ninja -w 'dupbuild=err' -C %s -j %i -l %i %s" % (
            self.build_directory, goma_cores, goma_cores,
            self.target)), self.source_directory, capture_output=False)

  def get_build_directory(self):
    """Returns the location of the correct build to use for reproduction."""

    if self.build_directory:
      return self.build_directory

    self.download_build_data()
    self.build_directory = self.build_dir_name()
    if not self.source_directory:
      message = ('This is a %(name)s testcase, please define $%(env_name)s_SRC'
                 ' or enter your %(name)s source location here' %
                 {'name': self.name, 'env_name': self.name.upper()})
      self.source_directory = os.path.expanduser(
          common.ask(message, 'Please enter a valid directory',
                     lambda x: x and os.path.isdir(os.path.expanduser(x))))
    if not self.current:
      self.checkout_source_by_sha()
    self.build_directory = self.out_dir_name()
    self.build_target()

    return self.build_directory


class PdfiumBuilder(GenericBuilder):
  """Build a fresh Pdfium binary."""

  def __init__(self, testcase, binary_definition, current, goma_dir):
    super(PdfiumBuilder, self).__init__(
        testcase.id, testcase.build_url, testcase.revision, current,
        goma_dir, os.environ.get(binary_definition.source_var), 'pdfium_test')
    self.chromium_sha = sha_from_revision(self.revision, 'chromium/src')
    self.name = 'Pdfium'
    self.git_sha = get_pdfium_sha(self.chromium_sha)
    self.gn_args_options = {'pdf_is_standalone': 'true'}
    self.gn_flags = ''


class V8Builder(GenericBuilder):
  """Builds a fresh v8 binary."""

  def __init__(self, testcase, binary_definition, current, goma_dir):

    super(V8Builder, self).__init__(
        testcase.id, testcase.build_url, testcase.revision, current, goma_dir,
        os.environ.get(binary_definition.source_var), 'd8')
    self.git_sha = sha_from_revision(self.revision, 'v8/v8')
    self.name = 'V8'

  def pre_build_steps(self):
    common.execute('GYP_DEFINES=asan=1 gclient runhooks', self.source_directory)
    common.execute('GYP_DEFINES=asan=1 gypfiles/gyp_v8', self.source_directory)


class ChromiumBuilder(GenericBuilder):
  """Builds a specific target from inside a Chromium source repository."""

  def __init__(self, testcase, binary_definition, current, goma_dir):

    target_name = None
    binary_name = binary_definition.binary_name
    if binary_definition.target:
      target_name = binary_definition.target
    if not binary_name:
      binary_name = common.get_binary_name(testcase.stacktrace_lines)
    super(ChromiumBuilder, self).__init__(
        testcase.id, testcase.build_url, testcase.revision, current,
        goma_dir, os.environ.get(binary_definition.source_var), binary_name,
        target_name)
    self.git_sha = sha_from_revision(self.revision, 'chromium/src')
    self.name = 'chromium'

  def pre_build_steps(self):
    common.execute('gclient runhooks', self.source_directory)

class LibfuzzerMsanBuilder(ChromiumBuilder):
  """Builds for a Msan testcase, inside the Chromium repo."""

  def pre_build_steps(self):
    common.execute(("GYP_DEFINES='clang=1 component=static_library "
                    "gomadir=%s msan=1 msan_track_origins=2 "
                    "proprietary_codecs=1 target_arch=x64 use_goma=1"
                    " use_prebuilt_instrumented_libraries=1' gclient "
                    "runhooks") % self.goma_dir,
                   self.source_directory)
