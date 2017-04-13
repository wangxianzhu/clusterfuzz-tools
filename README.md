ClusterFuzz tools
=================================

Status: Early prototype phase

[![CircleCI](https://circleci.com/gh/google/clusterfuzz-tools/tree/master.svg?style=shield)](https://circleci.com/gh/google/clusterfuzz-tools/tree/master)
[![Coverage Status](https://coveralls.io/repos/github/google/clusterfuzz-tools/badge.svg?branch=master)](https://coveralls.io/github/google/clusterfuzz-tools?branch=master)
[![Version](https://img.shields.io/pypi/v/clusterfuzz.svg)](https://pypi.python.org/pypi/clusterfuzz)
[![Python](https://img.shields.io/pypi/pyversions/clusterfuzz.svg)](https://pypi.python.org/pypi/clusterfuzz)

The tools supports various tasks (e.g. reproduce a crash locally)
needed by ClusterFuzz's users.

Currently, it supports reproducing a crash locally. In the future, it will
support uploading a fuzzer, tailing fuzzer log, and uploading a testcase.


Installation
-----------------

`pip install -U clusterfuzz`


### For Goobuntu

The default pip is of v1.5.4, which has known issues when installing dependencies. You *must* upgrade to the version 9.0+.

Please be aware that the pip on Goobuntu is installed with apt-get. The binary is at `/usr/bin/pip`. When upgrading pip with `sudo pip install -U pip`, it installs to `/usr/local/bin/pip`, and `sudo pip` still points to `/usr/bin/pip` (which is of the version 1.5.4).

Therefore, you must perform the below steps instead:

1. `sudo pip install -U pip`.
2. `sudo /usr/local/bin/pip install -U clusterfuzz`.

As a side note, it might be better if we uninstall `/usr/bin/pip` altogether with `sudo apt-get remove python-pip`.


Usage
------

See `clusterfuzz reproduce --help`. Run `clusterfuzz reproduce [testcase-id]`

Here's the workflow (we think) might be appropriate when fixing a bug:

1. Run `clusterfuzz reproduce [testcase-id]`
2. Make a new branch and make a code change
3. Run against the code change with `clusterfuzz reproduce [testcase-id] --current`
4. If the crash doesn’t occur anymore, it means your code change fixes the crash


Develop
------------

1. `./pants -V` to bootstrap [Pants](http://www.pantsbuild.org/)
2. Run the tool's tests: `./pants test --coverage=1 tool:test`
3. Run the ci's tests: `./pants test --coverage=1 ci/continuous_integration:test`
4. Run the tool binary: `./pants run tool:clusterfuzz -- reproduce -h`


Deploy CI
------------

1. Build the CI Pex binary: `./pants binary ci/continuous_integration:ci`
2. TODO(everestmz): Please fill in the ansible command.


Publish
----------

1. Create and merge a pull request to increase the version number
2. Build the Pex binary: `./pants binary tool:clusterfuzz`
3. Upload to the place where users can download
4. Tag the current version with `git tag -a <version> -m "Version <version>"`
5. Push the tag `git push --tags`

