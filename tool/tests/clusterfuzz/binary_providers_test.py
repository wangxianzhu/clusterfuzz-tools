"""Test the binary_providers module."""
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
import json
import mock

from clusterfuzz import binary_providers
from clusterfuzz import common
from clusterfuzz import output_transformer
from tests import libs
from test_libs import helpers


class BuildRevisionToShaUrlTest(helpers.ExtendedTestCase):
  """Tests the build_revision_to_sha_url method."""

  def setUp(self):
    helpers.patch(self, [
        'urlfetch.fetch'])

  def test_correct_url_building(self):
    """Tests if the SHA url is built correctly"""

    result = binary_providers.build_revision_to_sha_url(12345, 'v8/v8')
    self.assertEqual(result, ('https://cr-rev.appspot.com/_ah/api/crrev/v1'
                              '/get_numbering?project=chromium&repo=v8%2Fv8'
                              '&number=12345&numbering_type='
                              'COMMIT_POSITION&numbering_identifier=refs'
                              '%2Fheads%2Fmaster'))


class ShaFromRevisionTest(helpers.ExtendedTestCase):
  """Tests the sha_from_revision method."""

  def setUp(self):
    helpers.patch(self, ['urlfetch.fetch'])

  def test_get_sha_from_response_body(self):
    """Tests to ensure that the sha is grabbed from the response correctly"""

    self.mock.fetch.return_value = mock.Mock(body=json.dumps({
        'id': 12345,
        'git_sha': '1a2s3d4f',
        'crash_type': 'Bad Crash'}))

    result = binary_providers.sha_from_revision(123456, 'v8/v8')
    self.assertEqual(result, '1a2s3d4f')


class GetPdfiumShaTest(helpers.ExtendedTestCase):
  """Tests the get_pdfium_sha method."""

  def setUp(self):
    helpers.patch(self, ['urlfetch.fetch'])
    self.mock.fetch.return_value = mock.Mock(
        body=('dmFycyA9IHsNCiAgJ3BkZml1bV9naXQnOiAnaHR0cHM6Ly9wZGZpdW0uZ29vZ'
              '2xlc291cmNlLmNvbScsDQogICdwZGZpdW1fcmV2aXNpb24nOiAnNDA5MzAzOW'
              'QxOWY4MzIxNzNlYzU4Y2ZkOWYyZThhYzM5M2E3NjA5MScsDQp9DQo='))

  def test_decode_pdfium_sha(self):
    """Tests if the method correctly grabs the sha from the b64 download."""

    result = binary_providers.get_pdfium_sha('chrome_sha')
    self.assert_exact_calls(self.mock.fetch, [mock.call(
        ('https://chromium.googlesource.com/chromium/src.git/+/chrome_sha'
         '/DEPS?format=TEXT'))])
    self.assertEqual(result, '4093039d19f832173ec58cfd9f2e8ac393a76091')

class DownloadBuildDataTest(helpers.ExtendedTestCase):
  """Tests the download_build_data test."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute',
                         'clusterfuzz.common.get_source_directory',
                         'os.remove',
                         'os.rename'])

    self.build_url = 'https://storage.cloud.google.com/abc.zip'
    self.provider = binary_providers.BinaryProvider(1234, self.build_url, 'd8')

  def test_build_data_already_downloaded(self):
    """Tests the exit when build data is already returned."""

    self.setup_fake_filesystem()
    build_dir = os.path.join(common.CLUSTERFUZZ_BUILDS_DIR, '1234_build')
    os.makedirs(build_dir)
    self.provider.build_dir = build_dir
    result = self.provider.download_build_data()
    self.assert_n_calls(0, [self.mock.execute])
    self.assertEqual(result, build_dir)

  def test_get_build_data(self):
    """Tests extracting, moving and renaming the build data.."""

    helpers.patch(self, ['os.path.exists',
                         'os.makedirs',
                         'os.chmod',
                         'os.stat',
                         'clusterfuzz.binary_providers.os.remove'])
    self.mock.stat.return_value = mock.Mock(st_mode=0000)
    self.mock.exists.side_effect = [False, False]

    self.provider.download_build_data()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('gsutil', 'cp gs://abc.zip .',
                  common.CLUSTERFUZZ_CACHE_DIR),
        mock.call('unzip', '-q %s -d %s' %
                  (os.path.join(common.CLUSTERFUZZ_CACHE_DIR, 'abc.zip'),
                   common.CLUSTERFUZZ_BUILDS_DIR),
                  cwd=common.CLUSTERFUZZ_DIR)])
    self.assert_exact_calls(self.mock.chmod, [
        mock.call(os.path.join(
            common.CLUSTERFUZZ_BUILDS_DIR, '1234_build', 'd8'), 64)
    ])


class GetBinaryPathTest(helpers.ExtendedTestCase):
  """Tests the get_binary_path method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.DownloadedBinary.get_build_directory'])

  def test_call(self):
    """Tests calling the method."""

    build_dir = os.path.expanduser(os.path.join('~', 'chrome_src',
                                                'out', '12345_build'))
    self.mock.get_build_directory.return_value = build_dir

    provider = binary_providers.DownloadedBinary(12345, 'build_url', 'd8')
    result = provider.get_binary_path()
    self.assertEqual(result, os.path.join(build_dir, 'd8'))


class V8BuilderGetBuildDirectoryTest(helpers.ExtendedTestCase):
  """Test get_build_directory inside the V8DownloadedBinary class."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.V8Builder.download_build_data',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.V8Builder.checkout_source_by_sha',
        'clusterfuzz.binary_providers.V8Builder.build_target',
        'clusterfuzz.common.ask',
        'clusterfuzz.binary_providers.get_current_sha',
        'clusterfuzz.common.execute',
        'clusterfuzz.common.get_source_directory'])

    self.setup_fake_filesystem()
    self.build_url = 'https://storage.cloud.google.com/abc.zip'
    self.mock.get_current_sha.return_value = '1a2s3d4f5g6h'
    self.mock.execute.return_value = [0, '']
    self.chrome_source = os.path.join('chrome', 'src', 'dir')

  def test_parameter_not_set_valid_source(self):
    """Tests functionality when build has never been downloaded."""

    self.mock_os_environment({'V8_SRC': self.chrome_source})
    testcase = mock.Mock(id=12345, build_url=self.build_url, revision=54321,
                         gn_args=None)
    definition = mock.Mock(source_var='V8_SRC')
    provider = binary_providers.V8Builder(
        testcase, definition, libs.make_options(testcase_id=testcase.id))

    result = provider.get_build_directory()
    self.assertEqual(
        result, os.path.join(self.chrome_source, 'out', 'clusterfuzz_12345'))
    self.assert_exact_calls(self.mock.download_build_data,
                            [mock.call(provider)])
    self.assert_exact_calls(self.mock.build_target, [mock.call(provider)])
    self.assert_exact_calls(self.mock.checkout_source_by_sha,
                            [mock.call(provider)])
    self.assert_n_calls(0, [self.mock.ask])

  def test_parameter_not_set_invalid_source(self):
    """Tests when build is not downloaded & no valid source passed."""

    self.mock_os_environment({'V8_SRC': ''})
    testcase = mock.Mock(id=12345, build_url=self.build_url, revision=54321,
                         gn_args=None)
    definition = mock.Mock(source_var='V8_SRC')
    provider = binary_providers.V8Builder(
        testcase, definition, libs.make_options(testcase_id=testcase.id))

    self.mock.get_source_directory.return_value = self.chrome_source

    result = provider.get_build_directory()
    self.assertEqual(
        result, os.path.join(self.chrome_source, 'out', 'clusterfuzz_12345'))
    self.assert_exact_calls(self.mock.download_build_data,
                            [mock.call(provider)])
    self.assert_exact_calls(self.mock.build_target, [mock.call(provider)])
    self.assert_exact_calls(self.mock.checkout_source_by_sha,
                            [mock.call(provider)])

  def test_parameter_already_set(self):
    """Tests functionality when build_directory parameter is already set."""

    testcase = mock.Mock(id=12345, build_url=self.build_url, revision=54321)
    definition = mock.Mock(source_var='V8_SRC')
    provider = binary_providers.V8Builder(
        testcase, definition, libs.make_options())

    provider.build_directory = 'dir/already/set'

    result = provider.get_build_directory()
    self.assertEqual(result, 'dir/already/set')
    self.assert_n_calls(0, [self.mock.download_build_data])

class DownloadedBuildGetBinaryDirectoryTest(helpers.ExtendedTestCase):
  """Test get_build_directory inside the V8DownloadedBuild class."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.DownloadedBinary.download_build_data',
        'clusterfuzz.common.get_source_directory'])

    self.setup_fake_filesystem()
    self.build_url = 'https://storage.cloud.google.com/abc.zip'

  def test_parameter_not_set(self):
    """Tests functionality when build has never been downloaded."""

    provider = binary_providers.DownloadedBinary(12345, self.build_url, 'd8')
    build_dir = os.path.join(common.CLUSTERFUZZ_BUILDS_DIR, '12345_build')

    result = provider.get_build_directory()
    self.assertEqual(result, build_dir)
    self.assert_exact_calls(self.mock.download_build_data,
                            [mock.call(provider)])

  def test_parameter_already_set(self):
    """Tests functionality when the build_directory parameter is already set."""

    provider = binary_providers.DownloadedBinary(12345, self.build_url, 'd8')
    provider.build_directory = 'dir/already/set'

    result = provider.get_build_directory()
    self.assertEqual(result, 'dir/already/set')
    self.assert_n_calls(0, [self.mock.download_build_data])


class BuildTargetTest(helpers.ExtendedTestCase):
  """Tests the build_chrome method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.V8Builder.get_goma_cores',
        'clusterfuzz.binary_providers.V8Builder.setup_gn_args',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.common.execute'])
    self.mock.get_goma_cores.return_value = 120

  def test_correct_calls(self):
    """Tests the correct checks and commands are run to build."""

    revision_num = 12345
    testcase_id = 54321
    chrome_source = '/chrome/source'
    testcase = mock.Mock(id=testcase_id, build_url='', revision=revision_num)
    self.mock_os_environment({'V8_SRC': chrome_source})
    definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    builder = binary_providers.V8Builder(
        testcase, definition, libs.make_options())
    builder.build_directory = '/chrome/source/out/clusterfuzz_54321'
    builder.build_target()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('gclient', 'sync', chrome_source),
        mock.call('gclient', 'runhooks', chrome_source),
        mock.call('python', 'tools/clang/scripts/update.py', chrome_source),
        mock.call(
            'ninja',
            ("-w 'dupbuild=err' -C /chrome/source/out/clusterfuzz_54321 "
             '-j 120 -l 15 d8'),
            chrome_source,
            capture_output=False,
            stdout_transformer=mock.ANY)
    ])
    self.assertIsInstance(
        self.mock.execute.call_args[1]['stdout_transformer'],
        output_transformer.Ninja)
    self.assert_exact_calls(self.mock.setup_gn_args, [mock.call(builder)])


class SetupGnArgsTest(helpers.ExtendedTestCase):
  """Tests the setup_gn_args method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.setup_debug_symbol_if_needed',
        'clusterfuzz.common.edit_if_needed',
    ])
    self.testcase_dir = os.path.expanduser(os.path.join('~', 'test_dir'))
    testcase = mock.Mock(id=1234, build_url='', revision=54321, gn_args=None)
    self.mock_os_environment({'V8_SRC': '/chrome/source/dir'})
    self.definition = mock.Mock(source_var='V8_SRC')
    self.builder = binary_providers.V8Builder(
        testcase, self.definition, libs.make_options(goma_dir='/goma/dir'))

    self.mock.setup_debug_symbol_if_needed.side_effect = lambda v, _1, _2: v
    self.mock.edit_if_needed.side_effect = (
        lambda content, prefix, comment, should_edit: content)

  def test_create_build_dir(self):
    """Tests setting up the args when the build dir does not exist."""

    build_dir = os.path.join(common.CLUSTERFUZZ_BUILDS_DIR, '1234_build')
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir\n')
      f.write('use_goma = true')

    self.builder.build_directory = self.testcase_dir
    self.builder.setup_gn_args()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('gn', 'gen --check %s' % self.testcase_dir,
                  '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(f.read(), 'goma_dir = "/goma/dir"\nuse_goma = true')
    self.mock.setup_debug_symbol_if_needed.assert_called_once_with(
        {'goma_dir': '"/goma/dir"', 'use_goma': 'true'},
        self.definition.sanitizer, False)
    self.mock.edit_if_needed.assert_called_once_with(
        'goma_dir = "/goma/dir"\nuse_goma = true', prefix=mock.ANY,
        comment=mock.ANY, should_edit=False)

  def test_args_setup(self):
    """Tests to ensure that the args.gn is setup correctly."""

    os.makedirs(self.testcase_dir)
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'w') as f:
      f.write('Not correct args.gn')
    build_dir = os.path.join(common.CLUSTERFUZZ_BUILDS_DIR, '1234_build')
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir')

    self.builder.build_directory = self.testcase_dir
    self.builder.setup_gn_args()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('gn', 'gen --check %s' % self.testcase_dir,
                  '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(f.read(), 'goma_dir = "/goma/dir"\nuse_goma = true')
    self.mock.setup_debug_symbol_if_needed.assert_called_once_with(
        {'goma_dir': '"/goma/dir"', 'use_goma': 'true'},
        self.definition.sanitizer, False)
    self.mock.edit_if_needed.assert_called_once_with(
        'goma_dir = "/goma/dir"\nuse_goma = true', prefix=mock.ANY,
        comment=mock.ANY, should_edit=False)



class CheckoutSourceByShaTest(helpers.ExtendedTestCase):
  """Tests the checkout_chrome_by_sha method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.common.check_confirm',
        'clusterfuzz.binary_providers.ensure_sha',
        'clusterfuzz.binary_providers.get_current_sha',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.is_repo_dirty',
    ])
    self.chrome_source = '/usr/local/google/home/user/repos/chromium/src'
    self.testcase = mock.Mock(id=12345, build_url='', revision=4567)
    self.mock_os_environment({'V8_SRC': self.chrome_source})
    definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    self.builder = binary_providers.ChromiumBuilder(
        self.testcase, definition, libs.make_options())
    self.builder.git_sha = '1a2s3d4f'

  def test_dirty_dir(self):
    """Tests when the correct git sha is not already checked out."""
    self.mock.get_current_sha.return_value = 'aaa'
    self.mock.is_repo_dirty.return_value = True
    with self.assertRaises(common.DirtyRepoError):
      self.builder.checkout_source_by_sha()

    self.mock.get_current_sha.assert_called_once_with(self.chrome_source)
    self.mock.check_confirm.assert_called_once_with(
        binary_providers.CHECKOUT_MESSAGE.format(
            revision=4567,
            cmd='git checkout %s' % self.builder.git_sha,
            source_dir=self.chrome_source))

  def test_confirm_checkout(self):
    """Tests when user wants confirm the checkout."""
    self.mock.get_current_sha.return_value = 'aaa'
    self.mock.is_repo_dirty.return_value = False
    self.builder.checkout_source_by_sha()

    self.mock.get_current_sha.assert_called_once_with(self.chrome_source)
    self.mock.execute.assert_called_once_with(
        'git', 'checkout 1a2s3d4f', self.chrome_source)
    self.mock.check_confirm.assert_called_once_with(
        binary_providers.CHECKOUT_MESSAGE.format(
            revision=4567,
            cmd='git checkout %s' % self.builder.git_sha,
            source_dir=self.chrome_source))

  def test_already_checked_out(self):
    """Tests when the correct git sha is already checked out."""
    self.mock.get_current_sha.return_value = '1a2s3d4f'
    self.builder.checkout_source_by_sha()

    self.mock.get_current_sha.assert_called_once_with(self.chrome_source)
    self.assert_n_calls(0, [self.mock.check_confirm, self.mock.execute])


class EnsureShaTest(helpers.ExtendedTestCase):
  """Tests ensure_sha."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_exists',
    ])

  def test_already_exists(self):
    """Test when sha already exists."""
    self.mock.sha_exists.return_value = True
    binary_providers.ensure_sha('sha', 'source')

    self.mock.sha_exists.assert_called_once_with('sha', 'source')
    self.assertEqual(0, self.mock.execute.call_count)

  def test_not_exists(self):
    """Test when sha doesn't exists."""
    self.mock.sha_exists.return_value = False
    binary_providers.ensure_sha('sha', 'source')

    self.mock.sha_exists.assert_called_once_with('sha', 'source')
    self.mock.execute.assert_called_once_with(
        'git', 'fetch origin sha', 'source')


class V8BuilderOutDirNameTest(helpers.ExtendedTestCase):
  """Tests the out_dir_name builder method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.binary_providers.sha_from_revision'])
    self.mock_os_environment({'V8_SRC': '/source/dir'})
    testcase = mock.Mock(id=1234, build_url='', revision=54321)
    definition = mock.Mock(source_var='V8_SRC')
    self.builder = binary_providers.V8Builder(
        testcase, definition, libs.make_options(testcase_id=testcase.id))

  def test_dir(self):
    """Tests when no changes have been made to the dir."""
    result = self.builder.out_dir_name()
    self.assertEqual(result, '/source/dir/out/clusterfuzz_1234')


class PdfiumSetupGnArgsTest(helpers.ExtendedTestCase):
  """Tests the setup_gn_args method inside PdfiumBuilder."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, ['clusterfuzz.common.execute',
                         'clusterfuzz.binary_providers.sha_from_revision',
                         'clusterfuzz.binary_providers.get_pdfium_sha'])
    self.sha = '1a2s3d4f5g'
    self.mock.sha_from_revision.return_value = 'chrome_sha'
    self.mock.get_pdfium_sha = self.sha
    self.testcase = mock.Mock(id=1234, build_url='', revision=54321,
                              gn_args='use_goma = true')
    self.mock_os_environment({'V8_SRC': '/chrome/source/dir'})
    self.definition = mock.Mock(source_var='V8_SRC')
    self.testcase_dir = os.path.expanduser(os.path.join('~', 'test_dir'))
    self.mock.execute.return_value = (0, '12345')

  def test_gn_args(self):
    """Tests the args.gn parsing of extra values."""
    self.builder = binary_providers.PdfiumBuilder(
        self.testcase, self.definition,
        libs.make_options(goma_dir='/goma/dir'))

    os.makedirs(self.testcase_dir)
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'w') as f:
      f.write('Not correct args.gn')
    build_dir = os.path.join(common.CLUSTERFUZZ_BUILDS_DIR, '1234_build')
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir')

    self.builder.build_directory = self.testcase_dir
    self.builder.setup_gn_args()

    self.assert_exact_calls(self.mock.execute, [mock.call(
        'gn', 'gen  %s' % self.testcase_dir, '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(
          f.read(),
          ('goma_dir = "/goma/dir"\n'
           'pdf_is_standalone = true\n'
           'use_goma = true'))

  def test_gn_args_no_goma(self):
    """Tests the args.gn parsing of extra values when not using goma."""
    self.builder = binary_providers.PdfiumBuilder(
        self.testcase, self.definition, libs.make_options(goma_dir=None))

    os.makedirs(self.testcase_dir)
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'w') as f:
      f.write('Not correct args.gn')
    build_dir = os.path.join(common.CLUSTERFUZZ_BUILDS_DIR, '1234_build')
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir\n')
      f.write('use_goma = true')

    self.builder.build_directory = self.testcase_dir
    self.builder.setup_gn_args()

    self.assert_exact_calls(self.mock.execute, [mock.call(
        'gn', 'gen  %s' % self.testcase_dir, '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(
          f.read(), 'pdf_is_standalone = true\nuse_goma = false')


class PdfiumBuildTargetTest(helpers.ExtendedTestCase):
  """Tests the build_target method in PdfiumBuilder."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.PdfiumBuilder.setup_gn_args',
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.PdfiumBuilder.get_goma_cores',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.get_pdfium_sha'])
    self.mock.get_goma_cores.return_value = 120
    self.mock.sha_from_revision.return_value = 'chrome_sha'
    testcase = mock.Mock(id=1234, build_url='', revision=54321)
    self.mock_os_environment({'V8_SRC': '/chrome/source/dir'})
    definition = mock.Mock(source_var='V8_SRC')
    self.builder = binary_providers.PdfiumBuilder(
        testcase, definition, libs.make_options())

  def test_build_target(self):
    """Ensures that all build calls are made correctly."""
    self.builder.build_directory = '/build/dir'
    self.builder.source_directory = '/source/dir'

    self.builder.build_target()
    self.assert_exact_calls(self.mock.setup_gn_args, [mock.call(self.builder)])
    self.assert_exact_calls(self.mock.execute, [
        mock.call('gclient', 'sync', '/source/dir'),
        mock.call(
            'ninja',
            "-w 'dupbuild=err' -C /build/dir -j 120 -l 15 pdfium_test",
            '/source/dir',
            capture_output=False,
            stdout_transformer=mock.ANY)
    ])
    self.assertIsInstance(
        self.mock.execute.call_args[1]['stdout_transformer'],
        output_transformer.Ninja)


class ChromiumBuilderTest(helpers.ExtendedTestCase):
  """Tests the methods in ChromiumBuilder."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.ChromiumBuilder.get_build_directory',
        'clusterfuzz.binary_providers.ChromiumBuilder.get_goma_cores',
        'clusterfuzz.binary_providers.ChromiumBuilder.setup_gn_args',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.common.execute',
    ])
    self.mock.sha_from_revision.return_value = '1a2s3d4f5g'
    self.mock.get_build_directory.return_value = '/chromium/build/dir'
    self.testcase = mock.Mock(id=12345, build_url='', revision=4567)
    self.mock_os_environment({'V8_SRC': '/chrome/src'})
    self.definition = mock.Mock(
        source_var='V8_SRC', binary_name='binary', target='target')
    self.builder = binary_providers.ChromiumBuilder(
        self.testcase, self.definition, libs.make_options())
    self.builder.build_directory = '/chrome/src/out/clusterfuzz_builds'
    self.mock.get_goma_cores.return_value = 120

  def test_no_binary_name(self):
    """Test the functionality when no binary name is provided."""
    stacktrace = [
        {'content': 'not correct'}, {'content': '[Environment] A = b'},
        {'content': ('Running command: path/to/binary --flag-1 --flag2 opt'
                     ' /testcase/path')}]
    testcase = mock.Mock(id=12345, build_url='', revision=4567,
                         stacktrace_lines=stacktrace)
    definition = mock.Mock(source_var='V8_SRC', binary_name=None)
    builder = binary_providers.ChromiumBuilder(
        testcase, definition, libs.make_options())

    self.assertEqual(builder.binary_name, 'binary')

  def test_build_target(self):
    """Tests the build_target method."""
    self.builder.build_target()

    self.assert_exact_calls(self.mock.setup_gn_args, [mock.call(self.builder)])
    self.assert_exact_calls(self.mock.get_goma_cores, [mock.call(self.builder)])
    self.assert_exact_calls(self.mock.execute, [
        mock.call('gclient', 'sync', '/chrome/src'),
        mock.call('gclient', 'runhooks', '/chrome/src'),
        mock.call('python', 'tools/clang/scripts/update.py', '/chrome/src'),
        mock.call(
            'ninja',
            ("-w 'dupbuild=err' -C /chrome/src/out/clusterfuzz_builds "
             '-j 120 -l 15 target'),
            '/chrome/src',
            capture_output=False,
            stdout_transformer=mock.ANY)
    ])
    self.assertIsInstance(
        self.mock.execute.call_args[1]['stdout_transformer'],
        output_transformer.Ninja)

  def test_get_binary_path(self):
    """Tests the get_binary_path method."""
    result = self.builder.get_binary_path()
    self.assertEqual(result, '/chromium/build/dir/binary')


class CfiChromiumBuilderTest(helpers.ExtendedTestCase):
  """Tests the pre-build step of CfiChromiumBuilder."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.ChromiumBuilder.pre_build_steps'])

    testcase = mock.Mock(id=12345, build_url='', revision=4567)
    self.mock_os_environment({'V8_SRC': '/chrome/src'})
    definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    self.builder = binary_providers.CfiChromiumBuilder(
        testcase, definition, libs.make_options())

  def test_pre_build_steps(self):
    """Test the pre_build_steps method."""
    self.builder.pre_build_steps()
    self.assert_exact_calls(self.mock.execute, [
        mock.call('build/download_gold_plugin.py', '', '/chrome/src')])
    self.assert_exact_calls(self.mock.pre_build_steps,
                            [mock.call(self.builder)])


class MsanChromiumBuilderTest(helpers.ExtendedTestCase):
  """Tests the pre-build step of MsanChromiumBuilder."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.ChromiumBuilder.setup_gn_args'])

    testcase = mock.Mock(id=12345, build_url='', revision=4567,
                         gn_args='msan_track_origins=2\n')
    self.mock_os_environment({'V8_SRC': '/chrome/src'})
    definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    self.builder = binary_providers.MsanChromiumBuilder(
        testcase, definition, libs.make_options())

  def test_setup_gn_args(self):
    """Test the pre_build_steps method."""
    self.builder.setup_gn_args()
    self.assert_exact_calls(self.mock.execute, [
        mock.call('gclient', 'runhooks', '/chrome/src',
                  env={'GYP_DEFINES':
                       'msan=1 msan_track_origins=2 '
                       'use_prebuilt_instrumented_libraries=1'})])


class MsanV8BuilderTest(helpers.ExtendedTestCase):
  """Tests the pre-build step of MsanV8Builder."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.V8Builder.setup_gn_args'])

    testcase = mock.Mock(id=12345, build_url='', revision=4567,
                         gn_args='msan_track_origins=2\n')
    self.mock_os_environment({'V8_SRC': '/chrome/src'})
    definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    self.builder = binary_providers.MsanV8Builder(
        testcase, definition, libs.make_options())

  def test_setup_gn_args(self):
    """Test the pre_build_steps method."""
    self.builder.setup_gn_args()
    self.assert_exact_calls(self.mock.execute, [
        mock.call('gclient', 'runhooks', '/chrome/src',
                  env={'GYP_DEFINES':
                       'msan=1 msan_track_origins=2 '
                       'use_prebuilt_instrumented_libraries=1'})])


class ChromiumBuilder32BitTest(helpers.ExtendedTestCase):
  """Tests the pre-build step of ChromiumBuilder32Bit."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.install_build_deps_32bit',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.ChromiumBuilder.pre_build_steps'])

    testcase = mock.Mock(id=12345, build_url='', revision=4567)
    self.mock_os_environment({'CHROMIUM_SRC': '/chrome/src'})
    definition = mock.Mock(
        source_var='CHROMIUM_SRC', binary_name='binary')
    self.builder = binary_providers.ChromiumBuilder32Bit(
        testcase, definition, libs.make_options())

  def test_pre_build_steps(self):
    """Test the pre_build_steps method."""
    self.builder.pre_build_steps()
    self.mock.install_build_deps_32bit.assert_called_once_with('/chrome/src')
    self.mock.pre_build_steps.assert_called_once_with(self.builder)


class V8Builder32BitTest(helpers.ExtendedTestCase):
  """Tests the pre-build step of V8Builder32Bit."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.install_build_deps_32bit',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.V8Builder.pre_build_steps'])

    testcase = mock.Mock(id=12345, build_url='', revision=4567)
    self.mock_os_environment({'V8_SRC': '/chrome/src'})
    definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    self.builder = binary_providers.V8Builder32Bit(
        testcase, definition, libs.make_options())

  def test_pre_build_steps(self):
    """Test the pre_build_steps method."""
    self.builder.pre_build_steps()
    self.mock.install_build_deps_32bit.assert_called_once_with('/chrome/src')
    self.mock.pre_build_steps.assert_called_once_with(self.builder)


class GetCurrentShaTest(helpers.ExtendedTestCase):
  """Tests functionality when the rev-parse command fails."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision'
    ])
    self.mock.execute.return_value = (0, 'test\n')

  def test_get(self):
    """Tests to ensure the method prints before it exits."""
    self.assertEqual('test', binary_providers.get_current_sha('source'))
    self.mock.execute.assert_called_once_with(
        'git', 'rev-parse HEAD', 'source', print_command=False,
        print_output=False)


class GetGomaCoresTest(helpers.ExtendedTestCase):
  """Tests to ensure the correct number of cores is set."""

  def setUp(self):
    helpers.patch(self, ['multiprocessing.cpu_count',
                         'clusterfuzz.binary_providers.sha_from_revision'])

    self.testcase = mock.Mock(id=12345, build_url='', revision=4567)
    self.definition = mock.Mock(
        source_var='V8_SRC', binary_name='binary')
    self.mock.cpu_count.return_value = 64

  def test_specifying_goma_threads(self):
    """Ensures that if cores are manually specified, they are used."""
    self.builder = binary_providers.ChromiumBuilder(
        self.testcase, self.definition,
        libs.make_options(goma_threads=500, goma_dir='dir'))
    self.assertEqual(self.builder.get_goma_cores(), 500)

  def test_not_specifying(self):
    """Test not specifying goma threads."""
    self.builder = binary_providers.ChromiumBuilder(
        self.testcase, self.definition,
        libs.make_options(goma_threads=None, goma_dir='dir'))
    self.assertEqual(self.builder.get_goma_cores(), 3200)


class ShaExistsTest(helpers.ExtendedTestCase):
  """Tests for sha_exists."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute'])

  def test_exist(self):
    """Test exists."""
    self.mock.execute.return_value = (0, '')
    self.assertTrue(binary_providers.sha_exists('SHA', '/dir'))

    self.mock.execute.assert_called_once_with(
        'git', 'cat-file -e SHA', cwd='/dir', exit_on_error=False)

  def test_not_exist(self):
    """Test not exists."""
    self.mock.execute.return_value = (1, '')
    self.assertFalse(binary_providers.sha_exists('SHA', '/dir'))

    self.mock.execute.assert_called_once_with(
        'git', 'cat-file -e SHA', cwd='/dir', exit_on_error=False)


class IsRepoDirtyTest(helpers.ExtendedTestCase):
  """Tests for is_repo_dirty."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute'])

  def test_clean(self):
    """Test exists."""
    self.mock.execute.return_value = (0, '')
    self.assertFalse(binary_providers.is_repo_dirty('/dir'))

    self.mock.execute.assert_called_once_with(
        'git', 'diff', '/dir', print_command=False, print_output=False)

  def test_dirty(self):
    """Test not exists."""
    self.mock.execute.return_value = (0, 'some change')
    self.assertTrue(binary_providers.is_repo_dirty('/dir'))

    self.mock.execute.assert_called_once_with(
        'git', 'diff', '/dir', print_command=False, print_output=False)


class SetupDebugSymbolIfNeededTest(helpers.ExtendedTestCase):
  """Tests setup_debug_symbol_if_needed."""

  def test_not_setup(self):
    """Test when we shouldn't setup debug symbol."""
    self.assertEqual(
        {'is_debug': 'false'},
        binary_providers.setup_debug_symbol_if_needed(
            {'is_debug': 'false'}, 'ASAN', False))

  def test_asan(self):
    """Test editing."""
    self.assertEqual(
        {'symbol_level': '2', 'is_debug': 'true',
         'sanitizer_keep_symbols': 'true'},
        binary_providers.setup_debug_symbol_if_needed(
            {'is_debug': 'false'}, 'ASAN', True))

  def test_msan(self):
    """Test editing."""
    self.assertEqual(
        {'symbol_level': '2', 'is_debug': 'false',
         'sanitizer_keep_symbols': 'true'},
        binary_providers.setup_debug_symbol_if_needed(
            {'is_debug': 'false'}, 'MSAN', True))


class InstallBuildDeps32bitTest(helpers.ExtendedTestCase):
  """Tests install_build_deps_32bit."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute'])

  def test_build(self):
    """Test run."""
    binary_providers.install_build_deps_32bit('/source')
    self.mock.execute.assert_called_once_with(
        'build/install-build-deps.sh', '--lib32 --syms --no-prompt',
        '/source', stdout_transformer=mock.ANY, preexec_fn=None,
        redirect_stderr_to_stdout=True)
    self.assertIsInstance(
        self.mock.execute.call_args[1]['stdout_transformer'],
        output_transformer.Identity)
