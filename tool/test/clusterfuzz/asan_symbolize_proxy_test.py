"""Tests for asan_symbolize_proxy."""

import sys
import mock

from clusterfuzz import asan_symbolize_proxy
import helpers

class TestSymbolizerProxying(helpers.ExtendedTestCase):
  """Tests to ensure symbolizer proxying is done correctly."""

  def setUp(self):
    asan_symbolize_proxy.__name__ = 'module_name'
    helpers.patch(self, ['pkg_resources.resource_filename',
                         'subprocess.call'])
    self.mock.resource_filename.return_value = 'symbolizer_location'

  def test_run(self):
    """Test running the main method."""

    with self.assertRaises(SystemExit):
      asan_symbolize_proxy.main('cmd', '--inlining=true', 'arg1',
                                '--functions=short')
    self.assert_exact_calls(self.mock.call, [
        mock.call(['symbolizer_location', '--inlining=false', 'arg1',
                   '--functions=linkage'],
                  stdin=sys.stdin, stdout=sys.stdout)])
