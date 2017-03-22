"""For all local logging configuration."""
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
import logging
from logging import config

CLUSTERFUZZ_DIR = os.path.expanduser(os.path.join('~', '.clusterfuzz'))
LOG_DIR = os.path.join(CLUSTERFUZZ_DIR, 'logs')
DEBUG = os.environ.get('CF_DEBUG')
logging_config = dict(
    version=1,
    formatters={
        'timestamp': {'format': '%(asctime)s [%(levelname)s]: %(message)s'},
        'message': {'format': '%(message)s'}},
    handlers={
        'console': {'class': 'logging.StreamHandler',
                    'formatter': 'message',
                    'level': logging.DEBUG if DEBUG else logging.INFO},
        'file': {'class': 'logging.handlers.RotatingFileHandler',
                 'filename': os.path.join(LOG_DIR, 'output.log'),
                 'formatter': 'timestamp',
                 'maxBytes': 1048576,
                 'backupCount': 9,
                 'level': logging.DEBUG}},
    loggers={
        'clusterfuzz': {'handlers': ['console', 'file'],
                        'level': logging.DEBUG}})
logger = None
current_chunk = []

def start_loggers():
  global logger
  if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
  config.dictConfig(logging_config)
  logger = logging.getLogger('clusterfuzz')

def send_output(output_chunk):
  """Send a chunk of command line output to a file."""

  global current_chunk
  for x in output_chunk:
    if x == '\n':
      logger.debug(''.join(current_chunk))
      current_chunk = []
    else:
      current_chunk.append(x)
