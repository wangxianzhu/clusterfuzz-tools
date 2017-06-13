"""Tests for asan_symbolize_proxy."""

import os
import sys
import mock

from clusterfuzz import asan_symbolize_proxy
from test_libs import helpers


class TestSymbolizerProxying(helpers.ExtendedTestCase):
  """Tests to ensure symbolizer proxying is done correctly."""

  def setUp(self):
    helpers.patch(self, ['subprocess.call'])

  def test_run(self):
    """Test running the main method."""
    with self.assertRaises(SystemExit):
      asan_symbolize_proxy.main('cmd', '--inlining=true', 'arg1',
                                '--functions=short')
    expected_symbolizer_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'clusterfuzz', 'resources',
        'llvm-symbolizer'))
    self.assert_exact_calls(self.mock.call, [
        mock.call(
            [expected_symbolizer_path, '--inlining=false', 'arg1',
             '--functions=linkage'],
            stdin=sys.stdin, stdout=sys.stdout)])
