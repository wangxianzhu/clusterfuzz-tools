"""Tests the clone_chromium module of the CI service."""
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
import mock

from daemon import clone_chromium
import helpers


class CloneChromiumTest(helpers.ExtendedTestCase):
  """Tests the clone_chromium method."""

  def setUp(self):
    helpers.patch(self, ['subprocess.check_call'])
    self.setup_fake_filesystem()

  def test_insalls_correctly(self):
    """Ensures chromium is cloned and deps installed correctly."""

    self.assertFalse(os.path.exists(clone_chromium.DEPOT_TOOLS))
    self.assertFalse(os.path.exists(clone_chromium.CHROMIUM_DIR))

    clone_chromium.clone_chromium()
    self.assert_exact_calls(self.mock.check_call, [
        mock.call(
            ('git clone --depth 1 '
             'https://chromium.googlesource.com/chromium/tools/'
             'depot_tools.git'), cwd=clone_chromium.HOME, shell=True),
        mock.call(('%s --nohooks --force chromium' %
                   os.path.join(clone_chromium.DEPOT_TOOLS, 'fetch')),
                  cwd=clone_chromium.CHROMIUM_DIR, shell=True),
        mock.call('build/install-build-deps.sh --no-prompt',
                  cwd=clone_chromium.CHROMIUM_SRC, shell=True)
    ])
