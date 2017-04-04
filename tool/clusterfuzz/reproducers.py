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
import re
import shutil
import time
import subprocess
import logging
import json
import HTMLParser
import requests
import xvfbwrapper
import psutil

from clusterfuzz import common

DEFAULT_GESTURE_TIME = 5
logger = logging.getLogger('clusterfuzz')


def strip_html(lines):
  """Strip HTML tags and escape HTML chars."""
  new_lines = []
  parser = HTMLParser.HTMLParser()

  for line in lines:
    # We only strip <a> because that's all we need.
    line = re.sub('<[/a][^<]+?>', '', line)
    new_lines.append(parser.unescape(line))

  return new_lines


def remove_unsymbolized_stacktrace(lines):
  """Remove unsymbolized stacktrace because it interferes with stacktrace
    parsing. See: https://chrome-internal.googlesource.com/chrome/tools/clusterfuzz/+/master/src/common/utils.py#220"""  # pylint: disable=line-too-long
  new_lines = []
  for line in lines:
    if 'Release Build Unsymbolized Stacktrace' in line:
      break
    new_lines.append(line)
  return new_lines


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
    self.job_type = testcase.job_type
    self.environment = testcase.environment
    self.args = testcase.reproduction_args
    self.binary_path = binary_provider.get_binary_path()
    self.symbolizer_path = common.get_location('llvm-symbolizer')
    self.sanitizer = sanitizer
    self.gestures = testcase.gestures

    stacktrace_lines = strip_html(
        [l['content'] for l in testcase.stacktrace_lines])
    stacktrace_lines = remove_unsymbolized_stacktrace(stacktrace_lines)
    self.crash_state, self.crash_type = self.get_stacktrace_info(
        '\n'.join(stacktrace_lines))

    self.gesture_start_time = (self.get_gesture_start_time() if self.gestures
                               else None)
    self.source_directory = binary_provider.source_directory

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
    return common.execute(command, os.path.dirname(self.binary_path),
                          environment=self.environment, exit_on_error=False)

  def get_stacktrace_info(self, trace):
    """Post a stacktrace, return (crash_state, crash_type)."""

    response = requests.post(
        url=('https://clusterfuzz.com/v2/parse_stacktrace'),
        data=json.dumps({'job': self.job_type, 'stacktrace': trace}))
    response = json.loads(response.text)
    crash_state = [x for x in response['crash_state'].split('\n') if x]
    crash_type = response['crash_type'].replace('\n', ' ')
    return crash_state, crash_type

  def reproduce(self, iteration_max):
    """Reproduces the crash and prints the stacktrace."""

    logger.info('Reproducing...')

    iterations = 1
    while iterations <= iteration_max:
      _, output = self.reproduce_crash()

      print
      logger.info(output)

      new_crash_state, new_crash_type = self.get_stacktrace_info(output)
      if (new_crash_state == self.crash_state and
          new_crash_type == self.crash_type):
        logger.info('The stacktrace matches the original crash')
        return True
      logger.info('Reproduction attempt %d unsuccessful. Press Ctrl+C to'
                  ' stop trying to reproduce.', iterations)
      logger.debug('New crash state: %s, original: %s',
                   ', '.join(new_crash_state), ', '.join(self.crash_state))
      logger.debug('New crash type: %s, original: %s', new_crash_type,
                   self.crash_type)
      iterations += 1
      time.sleep(3)

class Blackbox(object):
  """Run commands within a virtual display using blackbox window manager."""

  def __init__(self, args):
    self.disable_blackbox = '--disable-gl-drawing-for-tests' not in args

  def __enter__(self):
    if self.disable_blackbox:
      return None
    self.display = xvfbwrapper.Xvfb(width=1280, height=1024)
    self.display.start()
    for i in self.display.xvfb_cmd:
      if i.startswith(':'):
        display_name = i
        break
    logger.info('Starting the blackbox window manager in a virtual display.')
    try:
      self.blackbox = subprocess.Popen(['blackbox'],
                                       env={'DISPLAY': display_name})
    except OSError, e:
      if str(e) == '[Errno 2] No such file or directory':
        raise common.BlackboxNotInstalledError
      raise

    time.sleep(30)
    return display_name

  def __exit__(self, unused_type, unused_value, unused_traceback):
    if self.disable_blackbox:
      return
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
      logger.info('psutil: Process abruptly ended.')
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

    time.sleep(20)
    visible_windows = set()
    for pid in pids:
      _, windows = common.execute(
          ('xdotool search --all --pid %s --onlyvisible --name'
           ' ".*"' % pid), os.path.expanduser('~'),
          environment={'DISPLAY': display_name},
          exit_on_error=False, print_output=False)
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
    logger.info('Running gestures...')
    windows = self.find_windows_for_process(proc.pid, display_name)
    for index, window in enumerate(windows):
      logger.debug('Window %s of %s', index, len(windows))
      self.xdotool_command('windowactivate --sync %s' % window, display_name)

      for gesture in self.gestures:
        logger.debug(gesture)
        self.execute_gesture(gesture, window, display_name)

  def pre_build_steps(self):
    """Steps to run before building."""

    user_profile_dir = '/tmp/clusterfuzz-user-profile-data'
    if os.path.exists(user_profile_dir):
      shutil.rmtree(user_profile_dir)
    user_data_str = ' --user-data-dir=%s' % user_profile_dir
    if user_data_str not in self.args:
      self.args += user_data_str
    super(LinuxChromeJobReproducer, self).pre_build_steps()


  def post_run_symbolize(self, output):
    """Symbolizes non-libfuzzer chrome jobs."""

    asan_symbolizer_location = os.path.join(
        self.source_directory, os.path.join('tools', 'valgrind', 'asan',
                                            'asan_symbolize.py'))
    symbolizer_proxy_location = common.get_location('asan_symbolize_proxy.py')
    os.chmod(symbolizer_proxy_location, 0755)
    x = common.start_execute(asan_symbolizer_location, os.path.expanduser('~'),
                             {'LLVM_SYMBOLIZER_PATH': symbolizer_proxy_location,
                              'CHROMIUM_SRC': self.source_directory})
    output += '\0'
    out, _ = x.communicate(input=output)
    return out


  def reproduce_crash(self):
    """Reproduce the crash, running gestures if necessary."""

    self.pre_build_steps()

    with Blackbox(self.args) as display_name:
      command = '%s %s %s' % (self.binary_path, self.args, self.testcase_path)
      logger.info('Running: %s', command)
      if display_name:
        self.environment['DISPLAY'] = display_name
      self.environment.pop('ASAN_SYMBOLIZER_PATH', None)
      process = common.start_execute(command, os.path.dirname(self.binary_path),
                                     environment=self.environment)
      if self.gestures:
        self.run_gestures(process, display_name)
      err, out = common.wait_execute(process, exit_on_error=False, timeout=15)
      return err, self.post_run_symbolize(out)
