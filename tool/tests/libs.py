"""Helper methods to make tests shorter."""
# TODO(tanin): rename this module to helpers once we rename shared/helpers.

from __future__ import absolute_import

from clusterfuzz import common


def make_options(
    testcase_id='1',
    current=False,
    build='chromium',
    disable_goma=False,
    goma_threads=10,
    iterations=11,
    disable_xvfb=False,
    target_args=None,
    edit_mode=False,
    disable_gclient=False,
    goma_dir=None):
  return common.Options(
      testcase_id=testcase_id,
      current=current,
      build=build,
      disable_goma=disable_goma,
      goma_threads=goma_threads,
      iterations=iterations,
      disable_xvfb=disable_xvfb,
      target_args=target_args,
      edit_mode=edit_mode,
      disable_gclient=disable_gclient,
      goma_dir=goma_dir)
