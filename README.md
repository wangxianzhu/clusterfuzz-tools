ClusterFuzz tools
=================================

[![CircleCI](https://circleci.com/gh/google/clusterfuzz-tools/tree/master.svg?style=shield)](https://circleci.com/gh/google/clusterfuzz-tools/tree/master)
[![Coverage Status](https://coveralls.io/repos/github/google/clusterfuzz-tools/badge.svg?branch=master)](https://coveralls.io/github/google/clusterfuzz-tools?branch=master)

The tools supports various tasks (e.g. reproduce a crash locally)
needed by ClusterFuzz's users.

Currently, it supports reproducing a crash locally. In the future, it will
support uploading a fuzzer, tailing fuzzer log, and uploading a testcase.


Requirements
---------------

* [gsutil](https://cloud.google.com/storage/docs/gsutil_install)
* `blackbox` and `xdotool`; these can be installed with `apt-get`.


Installation
-----------------

ClusterFuzz tools is a single binary file built with [Pex](https://github.com/pantsbuild/pex).
Therefore, you can simply copy the binary and run it.


For Goobuntu:

1. Run `prodaccess`.
2. Run `/google/data/ro/teams/clusterfuzz-tools/releases/clusterfuzz reproduce -h`.

For others:

1. Download [the latest stable version](https://storage.cloud.google.com/clusterfuzz-tools).
2. Run `clusterfuzz-<version>.pex reproduce -h`.


Usage
------

See `<binary> reproduce --help`. Run `<binary> reproduce [testcase-id]`.

Here's the workflow (we think) might be appropriate when fixing a bug:

1. Run `<binary> reproduce [testcase-id]`.
2. Make a new branch and make a code change.
3. Run against the code change with `<binary> reproduce [testcase-id] --current`.
4. If the crash doesn’t occur anymore, it means your code change fixes the crash.


Here are some other useful options:

```
usage: clusterfuzz reproduce [-h] [-c] [-b {download,chromium,standalone}]
                                [--disable-goma] [-j GOMA_THREADS]
                                [-i ITERATIONS] [-dx]
                                [--target-args TARGET_ARGS] [--edit-mode]
                                [--disable-gclient] [--enable-debug]
                                testcase_id

positional arguments:
  testcase_id           The testcase ID.

optional arguments:
  -h, --help            show this help message and exit
  -c, --current         Use the current tree; On the other hand, without
                        --current, the Chrome repository will be switched to
                        the commit specified in the testcase.
  -b {download,chromium,standalone}, --build {download,chromium,standalone}
                        Select which type of build to run the testcase
                        against.
  --disable-goma        Disable GOMA when building binaries locally.
  -j GOMA_THREADS, --goma-threads GOMA_THREADS
                        Manually specify the number of concurrent jobs for a
                        ninja build.
  -i ITERATIONS, --iterations ITERATIONS
                        Specify the number of times to attempt reproduction.
  -dx, --disable-xvfb   Disable running testcases in a virtual frame buffer.
  --target-args TARGET_ARGS
                        Additional arguments for the target (e.g. chrome).
  --edit-mode           Edit args.gn before building and target arguments
                        before running.
  --disable-gclient     Disable running gclient commands (e.g. sync,
                        runhooks).
  --enable-debug        Build Chrome with full debug symbols by injecting
                        `sanitizer_keep_symbols = true` and `is_debug = true`
                        to args.gn. Ready to debug with GDB.

```
