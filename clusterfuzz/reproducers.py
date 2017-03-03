"""Classes to reproduce different types of testcases."""
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
import shutil

from clusterfuzz import common

class BaseReproducer(object):
  """The basic reproducer class that all other ones are built on."""

  def __init__(self, binary_provider, testcase, sanitizer):
    self.testcase_path = testcase.get_testcase_path()
    self.environment = testcase.environment
    self.args = testcase.reproduction_args
    self.binary_path = binary_provider.get_binary_path()
    self.symbolizer_path = binary_provider.symbolizer_path
    self.sanitizer = sanitizer

  def deserialize_sanitizer_options(self, options):
    """Read options from a variable like ASAN_OPTIONS into a dict."""

    pairs = options.split(':')
    return_dict = {}
    for pair in pairs:
      k, v = pair.split('=')
      return_dict[k] = v
    return return_dict


  def serialize_sanitizer_options(self, options):
    """Takes dict of sanitizer options, returns command-line friendly string."""

    pairs = []
    for key, value in options.iteritems():
      pairs.append('%s=%s' % (key, value))
    return ':'.join(pairs)

  def set_up_symbolizers_suppressions(self):
    """Sets up the symbolizer variables for an environment."""

    env = self.environment
    env['%s_SYMBOLIZER_PATH' % self.sanitizer] = self.symbolizer_path
    env['DISPLAY'] = ':0.0'
    for variable in env:
      if '_OPTIONS' not in variable:
        continue
      options = self.deserialize_sanitizer_options(env[variable])

      if 'external_symbolizer_path' in options:
        options['external_symbolizer_path'] = self.symbolizer_path
      if 'suppressions' in options:
        suppressions_map = {'UBSAN_OPTIONS': 'ubsan', 'LSAN_OPTIONS': 'lsan'}
        filename = common.get_location(('suppressions/%s_suppressions.txt' %
                                        suppressions_map[variable]))
        options['suppressions'] = filename
      env[variable] = self.serialize_sanitizer_options(options)
    self.environment = env

  def pre_build_steps(self):
    """Steps to run before building."""
    self.set_up_symbolizers_suppressions()

  def reproduce_crash(self):
    """Reproduce the crash."""

    self.pre_build_steps()

    command = '%s %s %s' % (self.binary_path, self.args, self.testcase_path)
    common.execute(command, os.path.dirname(self.binary_path),
                   environment=self.environment, exit_on_error=False)


class LinuxUbsanChromeReproducer(BaseReproducer):
  """Adds and extre pre-build step to BaseReproducer."""

  def pre_build_steps(self):
    """Steps to run before building."""

    user_profile_dir = '/tmp/clusterfuzz-user-profile-data'
    if os.path.exists(user_profile_dir):
      shutil.rmtree(user_profile_dir)
    self.args += ' --user-data-dir=%s' % user_profile_dir
    super(LinuxUbsanChromeReproducer, self).pre_build_steps()
