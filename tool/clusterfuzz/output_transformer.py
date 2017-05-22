"""Transform the output before printing on screen."""


class Base(object):
  """Transform output and send to the output function."""

  def process(self, string, output_fn):
    """Process string and send to output_fn."""
    raise NotImplementedError

  def flush(self, output_fn):
    """Send the residue to output_fn."""
    raise NotImplementedError


class Hidden(Base):
  """Hide output and print dot every N characters."""

  def __init__(self, n=100):
    self.n = n
    self.count = 0

  def process(self, string, output_fn):
    """Process string and send to output_fn."""
    all_count = self.count + len(string)

    if all_count < self.n:
      self.count = all_count
      return

    for _ in xrange(int(all_count / self.n)):
      output_fn('.')

    self.count = all_count % self.n

  def flush(self, output_fn):
    """Send the residue to output_fn."""
    output_fn('.')


class Identity(Base):
  """Print output as it comes."""

  def process(self, string, output_fn):
    """Process string and send to output_fn."""
    output_fn(string)

  def flush(self, output_fn):
    """Send the residue to output_fn."""
    output_fn('')


class Ninja(Base):
  """Process ninja output and correctly replace previous lines."""

  def __init__(self):
    self.current_line = ''
    self.previous_line_size = 0

  def process(self, string, output_fn):
    """Replace the previous line and print output."""
    if '\n' in string:
      tokens = string.split('\n')
      self.current_line += tokens[0]
      current_line_size = len(self.current_line)

      if current_line_size < self.previous_line_size:
        self.current_line += ' ' * (self.previous_line_size - current_line_size)

      output_fn('\b' * self.previous_line_size)
      output_fn(self.current_line)

      self.previous_line_size = len(self.current_line)

      self.current_line = tokens[-1]
    else:
      self.current_line += string

  def flush(self, output_fn):
    """Print the residue output."""
    self.process('\n', output_fn)
    output_fn('\n')
