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
import helpers

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
    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '1234_build')
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
                  binary_providers.CLUSTERFUZZ_DIR),
        mock.call('unzip', '-q %s -d %s' %
                  (os.path.join(binary_providers.CLUSTERFUZZ_DIR, 'abc.zip'),
                   binary_providers.CLUSTERFUZZ_BUILDS_DIR),
                  cwd=binary_providers.CLUSTERFUZZ_DIR)])
    self.assert_exact_calls(self.mock.chmod, [
        mock.call(os.path.expanduser('~/.clusterfuzz/builds/1234_build/d8'),
                  64)])


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

  def setUp(self): #pylint: disable=missing-docstring
    helpers.patch(self, [
        'clusterfuzz.binary_providers.V8Builder.download_build_data',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.V8Builder.checkout_source_by_sha',
        'clusterfuzz.binary_providers.V8Builder.build_target',
        'clusterfuzz.common.ask',
        'clusterfuzz.binary_providers.V8Builder.get_current_sha',
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
    binary_definition = mock.Mock(source_var='V8_SRC')
    provider = binary_providers.V8Builder(
        testcase, binary_definition, False, '/goma/dir', None)

    result = provider.get_build_directory()
    self.assertEqual(result, os.path.join(self.chrome_source, 'out',
                                          'clusterfuzz_12345_1a2s3d4f5g6h'))
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
    binary_definition = mock.Mock(source_var='V8_SRC')
    provider = binary_providers.V8Builder(
        testcase, binary_definition, False, '/goma/dir', None)

    self.mock.get_source_directory.return_value = self.chrome_source

    result = provider.get_build_directory()
    self.assertEqual(result, os.path.join(self.chrome_source, 'out',
                                          'clusterfuzz_12345_1a2s3d4f5g6h'))
    self.assert_exact_calls(self.mock.download_build_data,
                            [mock.call(provider)])
    self.assert_exact_calls(self.mock.build_target, [mock.call(provider)])
    self.assert_exact_calls(self.mock.checkout_source_by_sha,
                            [mock.call(provider)])

  def test_parameter_already_set(self):
    """Tests functionality when build_directory parameter is already set."""

    testcase = mock.Mock(id=12345, build_url=self.build_url, revision=54321)
    binary_definition = mock.Mock(source_var='V8_SRC')
    provider = binary_providers.V8Builder(
        testcase, binary_definition, False, '/goma/dir', None)

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
    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '12345_build')

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
        'clusterfuzz.binary_providers.V8Builder.setup_gn_args',
        'clusterfuzz.binary_providers.V8Builder.get_goma_cores',
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision'])
    self.mock.get_goma_cores.return_value = 120

  def test_correct_calls(self):
    """Tests the correct checks and commands are run to build."""

    revision_num = 12345
    testcase_id = 54321
    chrome_source = '/chrome/source'
    goma_dir = '/goma/dir/location'
    testcase = mock.Mock(id=testcase_id, build_url='', revision=revision_num)
    self.mock_os_environment({'V8_SRC': chrome_source})
    binary_definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    builder = binary_providers.V8Builder(
        testcase, binary_definition, False, goma_dir, None)
    builder.build_directory = '/chrome/source/out/clusterfuzz_54321'
    builder.build_target()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('gclient', 'sync', chrome_source),
        mock.call('gclient', 'runhooks', chrome_source),
        mock.call('gypfiles/gyp_v8', '', chrome_source),
        mock.call(
            'ninja',
            ("-w 'dupbuild=err' -C /chrome/source/out/clusterfuzz_54321 "
             '-j 120 -l 15 d8'),
            chrome_source,
            capture_output=False)
    ])
    self.assert_exact_calls(self.mock.setup_gn_args, [mock.call(builder)])


class SetupGnArgsTest(helpers.ExtendedTestCase):
  """Tests the setup_gn_args method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision'])
    self.testcase_dir = os.path.expanduser(os.path.join('~', 'test_dir'))
    testcase = mock.Mock(id=1234, build_url='', revision=54321, gn_args=None)
    self.mock_os_environment({'V8_SRC': '/chrome/source/dir'})
    binary_definition = mock.Mock(source_var='V8_SRC')
    self.builder = binary_providers.V8Builder(
        testcase, binary_definition, False, '/goma/dir', None)

  def test_create_build_dir(self):
    """Tests setting up the args when the build dir does not exist."""

    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '1234_build')
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
      self.assertEqual(f.read(), 'use_goma = true\ngoma_dir = "/goma/dir"\n')

  def test_args_setup(self):
    """Tests to ensure that the args.gn is setup correctly."""

    os.makedirs(self.testcase_dir)
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'w') as f:
      f.write('Not correct args.gn')
    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '1234_build')
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir')

    self.builder.build_directory = self.testcase_dir
    self.builder.setup_gn_args()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('gn', 'gen --check %s' % self.testcase_dir,
                  '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(f.read(), 'use_goma = true\ngoma_dir = "/goma/dir"\n')



class CheckoutSourceByShaTest(helpers.ExtendedTestCase):
  """Tests the checkout_chrome_by_sha method."""

  def setUp(self): #pylint: disable=missing-docstring
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.common.check_confirm',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.GenericBuilder.source_dir_is_dirty'])
    self.chrome_source = '/usr/local/google/home/user/repos/chromium/src'
    self.command = 'git checkout 1a2s3d4f in %s' % self.chrome_source
    testcase = mock.Mock(id=12345, build_url='', revision=4567)
    self.mock_os_environment({'V8_SRC': self.chrome_source})
    binary_definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    self.builder = binary_providers.ChromiumBuilder(
        testcase, binary_definition, False, '/goma/dir', None)
    self.builder.git_sha = '1a2s3d4f'

  def test_dirty_dir(self):
    """Tests when the correct git sha is not already checked out."""

    self.mock.source_dir_is_dirty.return_value = True
    self.mock.execute.return_value = [0, 'not_the_same']
    with self.assertRaises(SystemExit):
      self.builder.checkout_source_by_sha()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('git', 'rev-parse HEAD', self.chrome_source,
                  print_command=False, print_output=False),
        mock.call('git', 'fetch', self.chrome_source)
    ])
    self.assert_exact_calls(self.mock.check_confirm, [
        mock.call('Proceed with the following command:\n%s?' % self.command)
    ])

  def test_not_already_checked_out(self):
    """Tests when the correct git sha is not already checked out."""

    self.mock.source_dir_is_dirty.return_value = False
    self.mock.execute.return_value = [0, 'not_the_same']
    self.builder.checkout_source_by_sha()

    self.assert_exact_calls(
        self.mock.execute,
        [
            mock.call('git', 'rev-parse HEAD', self.chrome_source,
                      print_command=False, print_output=False),
            mock.call('git', 'fetch', self.chrome_source),
            mock.call('git', 'checkout 1a2s3d4f', self.chrome_source)
        ]
    )
    self.assert_exact_calls(self.mock.check_confirm, [
        mock.call('Proceed with the following command:\n%s?' % self.command)
    ])

  def test_already_checked_out(self):
    """Tests when the correct git sha is already checked out."""

    self.mock.execute.return_value = [0, '1a2s3d4f']
    self.builder.checkout_source_by_sha()

    self.assert_exact_calls(
        self.mock.execute,
        [mock.call('git', 'rev-parse HEAD', self.chrome_source,
                   print_command=False, print_output=False)]
    )
    self.assert_n_calls(0, [self.mock.check_confirm])


class V8BuilderOutDirNameTest(helpers.ExtendedTestCase):
  """Tests the out_dir_name builder method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute',
                         'clusterfuzz.binary_providers.sha_from_revision'])
    self.mock_os_environment({'V8_SRC': '/source/dir'})
    self.sha = '1a2s3d4f5g6h'
    self.mock.sha_from_revision.return_value = self.sha
    testcase = mock.Mock(id=1234, build_url='', revision=54321)
    binary_definition = mock.Mock(source_var='V8_SRC')
    self.builder = binary_providers.V8Builder(
        testcase, binary_definition, False, '/goma/dir', None)

  def test_clean_dir(self):
    """Tests when no changes have been made to the dir."""

    self.mock.execute.side_effect = [[0, self.sha], [0, '']]
    result = self.builder.out_dir_name()
    self.assertEqual(result, '/source/dir/out/clusterfuzz_1234_1a2s3d4f5g6h')

  def test_dirty_dir(self):
    """Tests when changes have been made to the dir."""

    self.mock.execute.side_effect = [[0, self.sha], [0, 'changes']]
    result = self.builder.out_dir_name()
    self.assertEqual(result,
                     '/source/dir/out/clusterfuzz_1234_1a2s3d4f5g6h_dirty')


class PdfiumSetupGnArgsTest(helpers.ExtendedTestCase):
  """Tests the setup_gn_args method inside PdfiumBuilder."""

  def setUp(self): #pylint: disable=missing-docstring
    self.setup_fake_filesystem()
    helpers.patch(self, ['clusterfuzz.common.execute',
                         'clusterfuzz.binary_providers.sha_from_revision',
                         'clusterfuzz.binary_providers.get_pdfium_sha'])
    self.sha = '1a2s3d4f5g'
    self.mock.sha_from_revision.return_value = 'chrome_sha'
    self.mock.get_pdfium_sha = self.sha
    testcase = mock.Mock(id=1234, build_url='', revision=54321,
                         gn_args='use_goma = true')
    self.mock_os_environment({'V8_SRC': '/chrome/source/dir'})
    binary_definition = mock.Mock(source_var='V8_SRC')
    self.builder = binary_providers.PdfiumBuilder(
        testcase, binary_definition, False, '/goma/dir', None)
    self.testcase_dir = os.path.expanduser(os.path.join('~', 'test_dir'))
    self.mock.execute.return_value = (0, '12345')

  def test_gn_args(self):
    """Tests the args.gn parsing of extra values."""

    os.makedirs(self.testcase_dir)
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'w') as f:
      f.write('Not correct args.gn')
    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '1234_build')
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir')

    self.builder.build_directory = self.testcase_dir
    self.builder.setup_gn_args()

    self.assert_exact_calls(self.mock.execute, [mock.call(
        'gn', 'gen  %s' % self.testcase_dir, '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(f.read(), ('goma_dir = "/goma/dir"\n'
                                  'use_goma = true\n'
                                  'pdf_is_standalone = true\n'))

  def test_gn_args_no_goma(self):
    """Tests the args.gn parsing of extra values when not using goma."""

    os.makedirs(self.testcase_dir)
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'w') as f:
      f.write('Not correct args.gn')
    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '1234_build')
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir\n')
      f.write('use_goma = true')

    self.builder.build_directory = self.testcase_dir
    self.builder.goma_dir = None
    self.builder.setup_gn_args()

    self.assert_exact_calls(self.mock.execute, [mock.call(
        'gn', 'gen  %s' % self.testcase_dir, '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(f.read(), ('use_goma = false\n'
                                  'pdf_is_standalone = true\n'))


class PdfiumBuildTargetTest(helpers.ExtendedTestCase):
  """Tests the build_target method in PdfiumBuilder."""

  def setUp(self): #pylint: disable=missing-docstring
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
    binary_definition = mock.Mock(source_var='V8_SRC')
    self.builder = binary_providers.PdfiumBuilder(
        testcase, binary_definition, False, '/goma/dir', None)

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
            '/source/dir', capture_output=False)])

class ChromiumBuilderTest(helpers.ExtendedTestCase):
  """Tests the methods in ChromiumBuilder."""

  def setUp(self): #pylint: disable=missing-docstring
    helpers.patch(self, [
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.ChromiumBuilder.setup_gn_args',
        'clusterfuzz.binary_providers.ChromiumBuilder.get_build_directory'])
    self.mock.sha_from_revision.return_value = '1a2s3d4f5g'
    self.mock.get_build_directory.return_value = '/chromium/build/dir'
    self.testcase = mock.Mock(id=12345, build_url='', revision=4567)
    self.mock_os_environment({'V8_SRC': '/chrome/src'})
    self.binary_definition = mock.Mock(
        source_var='V8_SRC', binary_name='binary', target='target')
    self.builder = binary_providers.ChromiumBuilder(
        self.testcase, self.binary_definition, False, '/goma/dir', None)
    self.builder.build_directory = '/chrome/src/out/clusterfuzz_builds'

  def test_get_goma_cores(self):
    """Ensure goma_cores is calculated correctly."""

    helpers.patch(self, ['multiprocessing.cpu_count'])
    self.mock.cpu_count.return_value = 12

    builder = binary_providers.ChromiumBuilder(
        self.testcase, self.binary_definition, False, '/goma/dir', None)

    builder.goma_dir = False
    result = builder.get_goma_cores()
    self.assertEqual(result, 9)

    builder.goma_dir = True
    result = builder.get_goma_cores()
    self.assertEqual(result, 600)

  def test_no_binary_name(self):
    """Test the functionality when no binary name is provided."""
    helpers.patch(self, [
        'clusterfuzz.binary_providers.ChromiumBuilder.get_goma_cores'])
    self.mock.get_goma_cores.return_value = 120
    stacktrace = [
        {'content': 'not correct'}, {'content': '[Environment] A = b'},
        {'content': ('Running command: path/to/binary --flag-1 --flag2 opt'
                     ' /testcase/path')}]
    testcase = mock.Mock(id=12345, build_url='', revision=4567,
                         stacktrace_lines=stacktrace)
    binary_definition = mock.Mock(source_var='V8_SRC', binary_name=None)
    builder = binary_providers.ChromiumBuilder(
        testcase, binary_definition, False, '/goma/dir', None)

    self.assertEqual(builder.binary_name, 'binary')

  def test_build_target(self):
    """Tests the build_target method."""
    helpers.patch(self, [
        'clusterfuzz.binary_providers.ChromiumBuilder.get_goma_cores'])
    self.mock.get_goma_cores.return_value = 120
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
            capture_output=False)])

  def test_get_binary_path(self):
    """Tests the get_binary_path method."""

    helpers.patch(self, [
        'clusterfuzz.binary_providers.ChromiumBuilder.get_goma_cores'])
    self.mock.get_goma_cores.return_value = 120
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
    binary_definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    self.builder = binary_providers.CfiChromiumBuilder(
        testcase, binary_definition, False, '/goma/dir', None)

  def test_pre_build_steps(self):
    """Test the pre_build_steps method."""
    self.builder.pre_build_steps()
    self.assert_exact_calls(self.mock.execute, [
        mock.call('build/download_gold_plugin.py', '', '/chrome/src')])
    self.assert_exact_calls(self.mock.pre_build_steps, [mock.call(self.builder)])


class GetCurrentShaTest(helpers.ExtendedTestCase):
  """Tests functionality when the rev-parse command fails."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute',
                         'logging.RootLogger.info',
                         'clusterfuzz.binary_providers.sha_from_revision'])

    self.mock.execute.side_effect = SystemExit

  def test_log_when_exception(self):
    """Tests to ensure the method prints before it exits."""

    testcase = mock.Mock(id=12345, build_url='', revision=4567)
    binary_definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    builder = binary_providers.ChromiumBuilder(
        testcase, binary_definition, False, '/goma/dir', None)
    with self.assertRaises(SystemExit):
      builder.get_current_sha()


class GetGomaCoresTest(helpers.ExtendedTestCase):
  """Tests to ensure the correct number of cores is set."""

  def setUp(self):

    helpers.patch(self, ['multiprocessing.cpu_count',
                         'clusterfuzz.binary_providers.sha_from_revision'])

    testcase = mock.Mock(id=12345, build_url='', revision=4567)
    binary_definition = mock.Mock(source_var='V8_SRC', binary_name='binary')
    self.builder = binary_providers.ChromiumBuilder(
        testcase, binary_definition, False, '/goma/dir', None)
    self.mock.cpu_count.return_value = 64

  def test_select_correct_cores(self):
    """Ensures that if cores are manually specified, they are used."""

    self.builder.goma_threads = 500
    result = self.builder.get_goma_cores()
    self.assertEqual(result, 500)

    self.builder.goma_threads = None
    result = self.builder.get_goma_cores()
    self.assertEqual(result, 3200)
