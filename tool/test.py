"""Runs tests for clusterfuzz."""
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

import argparse
import os
import sys
import unittest


def execute(pattern, unsuppressed_output):
  """Run tests."""
  suites = unittest.loader.TestLoader().discover(
      os.path.join('test', 'clusterfuzz'),
      pattern=pattern,
      top_level_dir='.')

  result = unittest.TextTestRunner(
      verbosity=1, buffer=(not unsuppressed_output)).run(suites)

  if result.errors or result.failures:
    sys.exit(1)


def main():
  """Main entry point."""
  parser = argparse.ArgumentParser(description='Run tests.')
  parser.add_argument(
      '-p', '--pattern', default='*_test.py',
      help='Pattern to match test filenames.')
  parser.add_argument(
      '-u', '--unsuppressed-output', action='store_true', default=False,
      help='Unsuppress and print STDOUT and STDERR.')

  args = parser.parse_args()
  execute(args.pattern, args.unsuppressed_output)


if __name__ == '__main__':
  main()
