ClusterFuzz tools
=================================

Status: Early prototype phase

[![CircleCI](https://circleci.com/gh/google/clusterfuzz-tools/tree/master.svg?style=shield)](https://circleci.com/gh/google/clusterfuzz-tools/tree/master)
[![Coverage Status](https://coveralls.io/repos/github/google/clusterfuzz-tools/badge.svg?branch=master)](https://coveralls.io/github/google/clusterfuzz-tools?branch=master)
[![Version](https://img.shields.io/pypi/v/clusterfuzz.svg)](https://pypi.python.org/pypi/clusterfuzz)
[![Python](https://img.shields.io/pypi/pyversions/clusterfuzz.svg)](https://pypi.python.org/pypi/clusterfuzz)

The tools supports various tasks (e.g. reproduce a crash locally)
needed by ClusterFuzz's users.


Installation
-----------------

`pip install clusterfuzz`


Usage
------

See `clusterfuzz --help`.

Currently, it supports reproducing a crash locally. In the future, it will
support uploading a fuzzer, tailing fuzzer log, and uploading a testcase.


Develop
------------

1. Set up virtualenv with `python bootstrap.py`.
2. Setting up virtualenv by running `virtualenv ENV` and `source ENV/bin/activate`.
3. Run the binary by running `clusterfuzz --help`.


Test
-------------------------

1. Run tests with: `python test.py`.
2. Run the tests with coverage `coverage run test.py`.
3. Generate the report with `coverage html -d /tmp/coverage` and see `/tmp/coverage/index.html`.


Publish
----------

1. Create and merge a pull request to increase the version number.
2. Clear previously built artifacts with `rm -rf dist`.
3. Build artifact by running `python setup.py sdist bdist_wheel`.
4. Upload to [pypi.python.org](https://pypi.python.org/pypi/clusterfuzz) by running `twine upload dist/*`.
5. Tag the current version with `git tag -a <version> -m "Version <version>"`.
6. Push the tag `git push --tags`.

