ClusterFuzz tools
=================================

[![Build Status](https://travis-ci.org/google/clusterfuzz-tools.svg?branch=master)](https://travis-ci.org/google/clusterfuzz-tools)
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

1. Install [virtualenv](https://virtualenv.pypa.io).
2. Setting up virtualenv by running `virtualenv ENV` and `source ENV/bin/activate`.
3. Install dependencies by running `pip install -r requirements.txt`.
3. Build "[the development mode](https://packaging.python.org/distributing/#working-in-development-mode)" binary by running `pip install -e .`.
4. Run the binary by running `clusterfuzz --help`.
5. Run the tests `python test.py --help`.
6. Run the tests with coverage `coverage run test.py`.
7. Generate the report with `coverage html -d /tmp/coverage` and see `/tmp/coverage/index.html`.

Please note that we need to run `pip install -e .` before running `clusterfuzz` if the code has been changed.


Contribute
-----------

Please create a pull request.


Publish
----------

1. Create and merge a pull request to increase the version number.
2. Clear previously built artifacts with `rm -rf dist`.
3. Build artifact by running `python setup.py sdist bdist_wheel`.
4. Upload to [pypi.python.org](https://pypi.python.org/pypi/clusterfuzz) by running `twine upload dist/*`.
5. Tag the current version with `git tag -a <version> -m "Version <version>"`.
6. Push the tag `git push --tags`.

