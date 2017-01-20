"""The main entry point."""
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
import importlib


def execute(argv=None):
  """The main entry point."""
  parser = argparse.ArgumentParser(description='ClusterFuzz tools')
  subparsers = parser.add_subparsers(dest='command')

  reproduce = subparsers.add_parser('reproduce', help='Reproduce a crash.')
  reproduce.add_argument('testcase_id', help='The testcase ID.')
  reproduce.add_argument(
      '-c', '--current', action='store_true', default=False,
      help=('Use the current tree. Without --current, the Chrome repository is'
            ' switched to the commit specified in the testcase.'))

  args = parser.parse_args(argv)
  command = importlib.import_module('clusterfuzz.commands.%s' % args.command)

  arg_dict = {k: v for k, v in vars(args).items()}
  del arg_dict['command']

  command.execute(**arg_dict)
