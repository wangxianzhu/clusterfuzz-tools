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
import time
import subprocess
import xvfbwrapper
import psutil

from clusterfuzz import common

DEFAULT_GESTURE_TIME = 5

class BaseReproducer(object):
  """The basic reproducer class that all other ones are built on."""

  def get_gesture_start_time(self):
    """Determine how long to sleep before running gestures."""

    if self.gestures[-1].startswith('Trigger'):
      gesture_start_time = int(self.gestures[-1].split(':')[1])
      self.gestures.pop()
    else:
      gesture_start_time = DEFAULT_GESTURE_TIME
    return gesture_start_time

  def __init__(self, binary_provider, testcase, sanitizer):
    self.testcase_path = testcase.get_testcase_path()
    self.environment = testcase.environment
    self.args = testcase.reproduction_args
    self.binary_path = binary_provider.get_binary_path()
    self.symbolizer_path = binary_provider.symbolizer_path
    self.sanitizer = sanitizer
    self.gestures = testcase.gestures
    self.gesture_start_time = (self.get_gesture_start_time() if self.gestures
                               else None)

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


class Blackbox(object):
  """Run commands within a virtual display using blackbox window manager."""

  def __enter__(self):
    self.display = xvfbwrapper.Xvfb(width=1280, height=1024)
    self.display.start()
    for i in self.display.xvfb_cmd:
      if i.startswith(':'):
        display_name = i
        break
    print 'Starting the blackbox window manager in a virtual display.'
    self.blackbox = subprocess.Popen(['blackbox'],
                                     env={'DISPLAY': display_name})
    time.sleep(30)
    return display_name

  def __exit__(self, unused_type, unused_value, unused_traceback):
    self.blackbox.kill()
    self.display.stop()


class LinuxChromeJobReproducer(BaseReproducer):
  """Adds and extre pre-build step to BaseReproducer."""

  def get_process_ids(self, process_id, recursive=True):
    """Return list of pids for a process and its descendants."""

    # Try to find the running process.
    if not psutil.pid_exists(process_id):
      return []

    pids = [process_id]
    try:
      psutil_handle = psutil.Process(process_id)
      children = psutil_handle.children(recursive=recursive)
      for child in children:
        pids.append(child.pid)
    except:
      print 'psutil: Process abruptly ended.'
      raise

    return pids

  def xdotool_command(self, command, display_name):
    """Run a command, returning its output."""
    proc = common.start_execute(
        'xdotool %s' % command, os.path.expanduser('~'),
        environment={'DISPLAY': display_name})

    common.wait_execute(proc, exit_on_error=False, capture_output=False,
                        print_output=False)

  def find_windows_for_process(self, process_id, display_name):
    """Return visible windows belonging to a process."""
    pids = self.get_process_ids(process_id)
    if not pids:
      return []

    visible_windows = set()
    for _ in pids:
      _, windows = common.execute(
          ('xdotool search --all --pid %s --onlyvisible --nam'
           'e ".*"' % display_name), os.path.expanduser('~'),
          environment={'DISPLAY': display_name},
          exit_on_error=False)
      for line in windows.splitlines():
        if not line.isdigit():
          continue
        visible_windows.add(line)
    return visible_windows

  def execute_gesture(self, gesture, window, display_name):
    """Executes a specific gesture."""

    gesture_type, gesture_cmd = gesture.split(',')
    if gesture_type == 'windowsize':
      self.xdotool_command('%s %s %s' % (gesture_type, window, gesture_cmd),
                           display_name)
    else:
      self.xdotool_command('%s -- %s' % (gesture_type, gesture_cmd),
                           display_name)

  def run_gestures(self, proc, display_name):
    """Executes all required gestures."""

    time.sleep(self.gesture_start_time)

    windows = self.find_windows_for_process(proc.pid, display_name)
    for index, window in enumerate(windows):
      print 'Window %s of %s' % (index, len(windows))
      self.xdotool_command('windowactivate --sync %s' % window, display_name)

      for gesture in self.gestures:
        print gesture
        self.execute_gesture(gesture, window, display_name)

  def pre_build_steps(self):
    """Steps to run before building."""

    user_profile_dir = '/tmp/clusterfuzz-user-profile-data'
    if os.path.exists(user_profile_dir):
      shutil.rmtree(user_profile_dir)
    self.args += ' --user-data-dir=%s' % user_profile_dir
    super(LinuxChromeJobReproducer, self).pre_build_steps()

  def reproduce_crash(self):
    """Reproduce the crash, running gestures if necessary."""

    self.pre_build_steps()

    with Blackbox() as display_name:
      command = '%s %s %s' % (self.binary_path, self.args, self.testcase_path)
      print 'Running: %s' % command
      self.environment['DISPLAY'] = display_name
      process = common.start_execute(command, os.path.dirname(self.binary_path),
                                     environment=self.environment)
      if self.gestures:
        self.run_gestures(process, display_name)
      common.wait_execute(process, exit_on_error=False)
