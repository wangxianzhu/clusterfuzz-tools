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
import multiprocessing
import urllib
import json
import sys
import base64
import string
import logging
import urlfetch

from cmd_editor import editor
from clusterfuzz import common


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


def sha_exists(sha, source_dir):
  """Check if sha exists."""
  returncode, _ = common.execute(
      'git', 'cat-file -e %s' % sha, cwd=source_dir, exit_on_error=False)
  return returncode == 0


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
    if not os.path.exists(common.CLUSTERFUZZ_BUILDS_DIR):
      os.makedirs(common.CLUSTERFUZZ_BUILDS_DIR)

    gsutil_path = self.build_url.replace(
        'https://storage.cloud.google.com/', 'gs://')
    common.execute(
        'gsutil', 'cp %s .' % gsutil_path, common.CLUSTERFUZZ_CACHE_DIR)

    filename = os.path.split(gsutil_path)[1]
    saved_file = os.path.join(common.CLUSTERFUZZ_CACHE_DIR, filename)

    common.execute(
        'unzip', '-q %s -d %s' % (saved_file, common.CLUSTERFUZZ_BUILDS_DIR),
        cwd=common.CLUSTERFUZZ_DIR)

    logger.info('Cleaning up...')
    os.remove(saved_file)
    os.rename(os.path.join(common.CLUSTERFUZZ_BUILDS_DIR,
                           os.path.splitext(filename)[0]), build_dir)
    stats = os.stat(binary_location)
    os.chmod(binary_location, stats.st_mode | stat.S_IEXEC)

  def get_binary_path(self):
    return '%s/%s' % (self.get_build_directory(), self.binary_name)

  def build_dir_name(self):
    """Returns a build number's respective directory."""
    return os.path.join(common.CLUSTERFUZZ_BUILDS_DIR,
                        str(self.testcase_id) + '_build')


class DownloadedBinary(BinaryProvider):
  """Uses a downloaded binary."""

  def get_build_directory(self):
    """Returns the location of the correct build to use for reproduction."""

    if self.build_directory:
      return self.build_directory

    self.download_build_data()
    # We need the source dir so we can use asan_symbolize.py from the
    # chromium source directory.
    self.source_directory = common.get_source_directory('chromium')
    self.build_directory = self.build_dir_name()
    return self.build_directory


class GenericBuilder(BinaryProvider):
  """Provides a base for binary builders."""

  def __init__(self, testcase_id, build_url, revision, current, goma_dir,
               source, binary_name, target, goma_threads, edit_mode):
    """self.git_sha must be set in a subclass, or some of these
    instance methods may not work."""
    super(GenericBuilder, self).__init__(testcase_id, build_url, binary_name)
    self.target = target if target else binary_name
    self.current = current
    self.goma_dir = goma_dir
    self.source_directory = source
    self.revision = revision
    self.gn_args = None
    self.gn_args_options = None
    self.gn_flags = '--check'
    self.goma_threads = goma_threads
    self.edit_mode = edit_mode

  def get_current_sha(self):
    try:
      _, current_sha = common.execute(
          'git', 'rev-parse HEAD', self.source_directory, print_command=False,
          print_output=False)
    except SystemExit:
      logger.info(
          'Error: The selected directory is not a valid git repository.')
      raise
    return current_sha.strip()

  def source_dir_is_dirty(self):
    """Returns true if the source dir has uncommitted changes."""

    _, diff_result = common.execute(
        'git', 'diff', self.source_directory, print_command=False,
        print_output=False)
    return bool(diff_result)

  def out_dir_name(self):
    """Returns the correct out dir in which to build the revision.

    Directory name is of the format clusterfuzz_<testcase_id>_<git_sha>,
    with a possible '_dirty' on the end. Based on the current git sha, and
    whether changes have been made to the repo."""

    dir_name = os.path.join(self.source_directory, 'out',
                            'clusterfuzz_%s_%s' % (str(self.testcase_id),
                                                   self.get_current_sha()))
    if self.source_dir_is_dirty():
      dir_name += '_dirty'
    return dir_name


  def checkout_source_by_sha(self):
    """Checks out the correct revision."""

    if self.get_current_sha() == self.git_sha:
      return

    if not sha_exists(self.git_sha, self.source_directory):
      common.execute(
          'git', 'fetch origin %s' % self.git_sha, self.source_directory)

    binary = 'git'
    args = 'checkout %s' % self.git_sha
    common.check_confirm(
        'Proceed with the following command:\n'
        '%s %s in %s?' % (binary, args, self.source_directory))
    if self.source_dir_is_dirty():
      logger.info('Your source directory has uncommitted changes: please '
                  'commit or stash these changes and re-run this tool.')
      sys.exit(1)
    common.execute(binary, args, self.source_directory)

  def deserialize_gn_args(self, args):
    """Convert gn args into a dict."""

    args_hash = {}
    for line in args.splitlines():
      key, val = line.split('=')
      args_hash[key.strip()] = val.strip()
    return args_hash

  def serialize_gn_args(self, args_hash):
    args = []
    for key, val in sorted(args_hash.iteritems()):
      args.append('%s = %s' % (key, val))
    return '\n'.join(args)

  def setup_gn_goma_params(self, gn_args):
    """Ensures that goma_dir and gn_goma are used correctly."""

    if not self.goma_dir:
      self.goma_dir = False
      gn_args.pop('goma_dir', None)
      gn_args['use_goma'] = 'false'
    else:
      gn_args['use_goma'] = 'true'
      gn_args['goma_dir'] = '"%s"' % self.goma_dir
    return gn_args

  def setup_gn_args(self):
    """Ensures that args.gn is set up properly."""
    # Remove existing gn file from build directory.
    args_gn_path = os.path.join(self.build_directory, 'args.gn')
    if os.path.isfile(args_gn_path):
      os.remove(args_gn_path)

    # Create build directory if it does not already exist.
    if not os.path.exists(self.build_directory):
      os.makedirs(self.build_directory)

    # If no args.gn file is found, get it from downloaded build.
    if self.gn_args:
      gn_args = self.gn_args
    else:
      args_gn_downloaded_build_path = os.path.join(
          self.build_dir_name(), 'args.gn')
      with open(args_gn_downloaded_build_path, 'r') as f:
        gn_args = f.read()

    # Add additional options to existing gn args.
    args_hash = self.deserialize_gn_args(gn_args)
    args_hash = self.setup_gn_goma_params(args_hash)
    if self.gn_args_options:
      for k, v in self.gn_args_options.iteritems():
        args_hash[k] = v

    # Let users edit the current args.
    content = self.serialize_gn_args(args_hash)
    if self.edit_mode:
      content = editor.edit(
          content, prefix='edit-args-gn-',
          comment='Edit args.gn before building.')

    # Write args to file and store.
    with open(args_gn_path, 'w') as f:
      f.write(content)
    self.gn_args = content

    common.execute('gn', 'gen %s %s' % (self.gn_flags, self.build_directory),
                   self.source_directory)

  def pre_build_steps(self):
    """Steps to be run before the target is built."""

    pass

  def get_goma_cores(self):
    """Choose the correct amount of GOMA cores for a build."""

    if self.goma_threads:
      return self.goma_threads
    else:
      cpu_count = multiprocessing.cpu_count()
      return 50 * cpu_count if self.goma_dir else (3 * cpu_count) / 4

  def build_target(self):
    """Build the correct revision in the source directory."""
    # Note: gclient sync must be run before setting up the gn args.
    common.execute('gclient', 'sync', self.source_directory)

    self.pre_build_steps()
    self.setup_gn_args()
    goma_cores = self.get_goma_cores()
    common.execute(
        'ninja',
        "-w 'dupbuild=err' -C %s -j %i -l 15 %s" % (
            self.build_directory, goma_cores, self.target),
        self.source_directory, capture_output=False)

  def get_build_directory(self):
    """Returns the location of the correct build to use for reproduction."""

    if self.build_directory:
      return self.build_directory

    if not self.gn_args:
      self.download_build_data()

    self.build_directory = self.build_dir_name()

    if not self.source_directory:
      self.source_directory = common.get_source_directory(self.name)

    if not self.current:
      self.checkout_source_by_sha()

    self.build_directory = self.out_dir_name()
    self.build_target()

    return self.build_directory


class PdfiumBuilder(GenericBuilder):
  """Build a fresh Pdfium binary."""

  def __init__(self, testcase, binary_definition, current, goma_dir,
               goma_threads, edit_mode):
    super(PdfiumBuilder, self).__init__(
        testcase.id, testcase.build_url, testcase.revision, current,
        goma_dir, os.environ.get(binary_definition.source_var), 'pdfium_test',
        None, goma_threads, edit_mode)
    self.chromium_sha = sha_from_revision(self.revision, 'chromium/src')
    self.name = 'Pdfium'
    self.git_sha = get_pdfium_sha(self.chromium_sha)
    self.gn_args = testcase.gn_args
    self.gn_args_options = {'pdf_is_standalone': 'true'}
    self.gn_flags = ''


class V8Builder(GenericBuilder):
  """Builds a fresh v8 binary."""

  def __init__(self, testcase, binary_definition, current, goma_dir,
               goma_threads, edit_mode):
    super(V8Builder, self).__init__(
        testcase.id, testcase.build_url, testcase.revision, current, goma_dir,
        os.environ.get(binary_definition.source_var), 'd8', None, goma_threads,
        edit_mode)
    self.git_sha = sha_from_revision(self.revision, 'v8/v8')
    self.gn_args = testcase.gn_args
    self.name = 'V8'

  def pre_build_steps(self):
    common.execute('gclient', 'runhooks', self.source_directory)
    if not self.current:
      common.execute('python', 'tools/clang/scripts/update.py',
                     self.source_directory)

class ChromiumBuilder(GenericBuilder):
  """Builds a specific target from inside a Chromium source repository."""

  def __init__(self, testcase, binary_definition, current, goma_dir,
               goma_threads, edit_mode):
    target_name = None
    binary_name = binary_definition.binary_name
    if binary_definition.target:
      target_name = binary_definition.target
    if not binary_name:
      binary_name = common.get_binary_name(testcase.stacktrace_lines)
    super(ChromiumBuilder, self).__init__(
        testcase.id, testcase.build_url, testcase.revision, current,
        goma_dir, os.environ.get(binary_definition.source_var), binary_name,
        target_name, goma_threads, edit_mode)
    self.git_sha = sha_from_revision(self.revision, 'chromium/src')
    self.gn_args = testcase.gn_args
    self.name = 'chromium'

  def pre_build_steps(self):
    common.execute('gclient', 'runhooks', self.source_directory)
    if not self.current:
      common.execute('python', 'tools/clang/scripts/update.py',
                     self.source_directory)


class CfiChromiumBuilder(ChromiumBuilder):
  """Build a CFI chromium build."""

  def pre_build_steps(self):
    """Run the pre-build steps and then run download_gold_plugin.py."""
    super(CfiChromiumBuilder, self).pre_build_steps()
    common.execute('build/download_gold_plugin.py', '', self.source_directory)


class MsanChromiumBuilder(ChromiumBuilder):
  """Build a MSAN chromium build."""

  def setup_gn_args(self):
    """Run the setup_gn_args and re-run hooks with special GYP_DEFINES."""
    super(MsanChromiumBuilder, self).setup_gn_args()

    args_hash = self.deserialize_gn_args(self.gn_args)
    msan_track_origins_value = (int(args_hash['msan_track_origins'])
                                if 'msan_track_origins' in args_hash
                                else 2)
    common.execute('gclient', 'runhooks', self.source_directory,
                   env={'GYP_DEFINES':
                        ('msan=1 msan_track_origins=%d '
                         'use_prebuilt_instrumented_libraries=1') %
                        msan_track_origins_value})


class MsanV8Builder(V8Builder):
  """Build a MSAN V8 build."""

  def setup_gn_args(self):
    """Run the setup_gn_args and re-run hooks with special GYP_DEFINES."""
    super(MsanV8Builder, self).setup_gn_args()

    args_hash = self.deserialize_gn_args(self.gn_args)
    msan_track_origins_value = (int(args_hash['msan_track_origins'])
                                if 'msan_track_origins' in args_hash
                                else 2)
    common.execute('gclient', 'runhooks', self.source_directory,
                   env={'GYP_DEFINES':
                        ('msan=1 msan_track_origins=%d '
                         'use_prebuilt_instrumented_libraries=1') %
                        msan_track_origins_value})


class ChromiumBuilder32Bit(ChromiumBuilder):
  """Build a 32-bit chromium build."""

  def pre_build_steps(self):
    """Run the pre-build steps and then install 32-bit libraries."""
    super(ChromiumBuilder32Bit, self).pre_build_steps()
    common.execute_with_shell('build/install-build-deps.sh',
                              '--lib32 --syms --no-prompt',
                              self.source_directory)

class V8Builder32Bit(V8Builder):
  """Build a 32-bit V8 build."""

  def pre_build_steps(self):
    """Run the pre-build steps and then install 32-bit libraries."""
    super(V8Builder32Bit, self).pre_build_steps()
    common.execute_with_shell('build/install-build-deps.sh',
                              '--lib32 --syms --no-prompt',
                              self.source_directory)
