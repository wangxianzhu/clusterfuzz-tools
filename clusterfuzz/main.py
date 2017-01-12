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
import inspect

def _args_to_dict(args, method):
  """Convert args to dict that is compatible with the method's argument."""
  arg_names = inspect.getargspec(method).args
  args_dict = {
      k: v
      for k, v in vars(args).items() if k in arg_names and v is not None
  }
  return args_dict



def main():
  """The main entry point."""
  parser = argparse.ArgumentParser(description='ClusterFuzz tools')
  subparsers = parser.add_subparsers(dest='command')

  reproduce = subparsers.add_parser('reproduce', help='Reproduce a crash.')
  reproduce.add_argument('testcase_id', help='The testcase ID.')
  reproduce.add_argument(
      '-c', '--current', action='store_true', default=False,
      help=('Use the current tree. Without --current, the Chrome repository is'
            ' switched to the commit specified in the testcase.'))

  args = parser.parse_args()
  command = importlib.import_module('clusterfuzz.commands.%s' % args.command)
  command.execute(**_args_to_dict(args, command.execute))


if __name__ == "__main__":
  main()
