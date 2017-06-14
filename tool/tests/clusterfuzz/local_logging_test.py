"""Test local_logging."""

import logging
import os
import mock

from clusterfuzz import local_logging
from test_libs import helpers


class StartLoggersTest(helpers.ExtendedTestCase):
  """Test start_loggers."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'logging.config.dictConfig',
        'logging.getLogger',
        'logging.handlers.RotatingFileHandler.doRollover'
    ])

  def test_start(self):
    """Test starting a logger."""
    rotating_handler = logging.handlers.RotatingFileHandler(filename='test.log')
    self.mock.getLogger.return_value = (
        mock.Mock(handlers=[logging.NullHandler(), rotating_handler]))

    local_logging.start_loggers()

    self.mock.getLogger.assert_called_once_with('clusterfuzz')
    self.assertTrue(os.path.exists(local_logging.LOG_DIR))
    self.mock.doRollover.assert_called_once_with(rotating_handler)
