"""Test output_transformer."""

import helpers

from clusterfuzz import output_transformer


class HiddenTest(helpers.ExtendedTestCase):
  """Test Hidden."""

  def test_print_dot(self):
    """Test printing dot every n characters."""
    self.output = ''
    def output_fn(s):
      self.output += s

    transformer = output_transformer.Hidden()
    transformer.process('a' * 1001, output_fn)
    transformer.flush(output_fn)

    self.assertEqual('.' * 11 + '\n', self.output)


class IdentityTest(helpers.ExtendedTestCase):
  """Test Identity."""

  def test_print(self):
    """Test printing dot every n characters."""
    self.output = ''
    def output_fn(s):
      self.output += s

    transformer = output_transformer.Identity()
    transformer.process('a' * 1001, output_fn)
    transformer.flush(output_fn)

    self.assertEqual('a' * 1001, self.output)


class NinjaTest(helpers.ExtendedTestCase):
  """Test Ninja."""

  def test_print(self):
    """Test ninja output."""
    self.output = ''
    def output_fn(s):
      self.output += s

    transformer = output_transformer.Ninja()
    transformer.process('aaaaa\n', output_fn)
    transformer.process('bbb', output_fn)
    transformer.process('\nccc', output_fn)
    transformer.process('c\ndddddd', output_fn)
    transformer.flush(output_fn)

    self.assertEqual(
        'aaaaa\b\b\b\b\bbbb  \b\b\b\b\bcccc \b\b\b\b\bdddddd\n', self.output)
