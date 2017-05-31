"""Test output_transformer."""

import StringIO
import helpers

from clusterfuzz import output_transformer


class HiddenTest(helpers.ExtendedTestCase):
  """Test Hidden."""

  def test_print_dot(self):
    """Test printing dot every n characters."""
    self.output = StringIO.StringIO()

    transformer = output_transformer.Hidden()
    transformer.set_output(self.output)
    transformer.process('a' * 1001)
    transformer.flush()

    self.assertEqual('.' * 11 + '\n', self.output.getvalue())
    self.output.close()


class IdentityTest(helpers.ExtendedTestCase):
  """Test Identity."""

  def test_print(self):
    """Test printing dot every n characters."""
    self.output = StringIO.StringIO()

    transformer = output_transformer.Identity()
    transformer.set_output(self.output)
    transformer.process('a' * 1001)
    transformer.flush()

    self.assertEqual('a' * 1001, self.output.getvalue())
    self.output.close()


class NinjaTest(helpers.ExtendedTestCase):
  """Test Ninja."""

  def test_print(self):
    """Test ninja output."""
    self.output = StringIO.StringIO()

    transformer = output_transformer.Ninja()
    transformer.set_output(self.output)
    transformer.process('aaaaa\n')
    transformer.process('bbb')
    transformer.process('\nccc')
    transformer.process('c\ndddddd')
    transformer.flush()

    self.assertEqual(
        'aaaaa\b\b\b\b\bbbb  \b\b\b\b\bcccc \b\b\b\b\bdddddd\n',
        self.output.getvalue())
    self.output.close()
