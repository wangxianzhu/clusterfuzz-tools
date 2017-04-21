"""Module for the 'supported-job-types' command.

Prints the supported job types."""
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

import logging
import yaml

from clusterfuzz import common

logger = logging.getLogger('clusterfuzz')

def execute():
  """Echos all supported job types."""

  logger.debug('Printing supported job types')

  with open(common.get_resource(
      0640, 'resources', 'supported_job_types.yml')) as stream:
    supported_jobs = yaml.load(stream)
  to_print = {}
  for category in supported_jobs:
    to_print[category] = []
    for job in supported_jobs[category]:
      to_print[category].append(job)

  logger.info(yaml.dump(to_print))
