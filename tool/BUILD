import os


def get_version():
  """Get version from VERSION."""
  with open(os.path.join('tool', 'clusterfuzz', 'resources', 'VERSION')) as f:
    return f.read().strip()


for name in ['clusterfuzz-%s' % get_version(), 'clusterfuzz-ci']:
  python_binary(
      name=name,
      entry_point='clusterfuzz.main:execute',
      dependencies=[':src'],
      zip_safe=False
  )


python_library(
    name='src',
    sources=rglobs('clusterfuzz/*.py'),
    dependencies=[
        '//3rdparty/python:backports.shutil-get-terminal-size',
        '//3rdparty/python:httplib2',
        '//3rdparty/python:namedlist',
        '//3rdparty/python:oauth2client',
        '//3rdparty/python:psutil',
        '//3rdparty/python:pyOpenSSL',
        '//3rdparty/python:pyyaml',
        '//3rdparty/python:requests',
        '//3rdparty/python:urlfetch',
        '//3rdparty/python:xvfbwrapper',
        '//cmd-editor:src',
        '//shared:errors',
    ],
    resources=rglobs('clusterfuzz/resources/*'),
    compatibility=['>=2.7','<3'],
)


python_library(
    name='all-src-for-pylint',
    sources=rglobs('tests/*.py'),
    compatibility=['>=2.7','<3'],
    dependencies=[
        ':src',
        '//shared:test_libs',
    ]
)


python_binary(
    name='pylint',
    entry_point='pylint_cli.main:main',
    dependencies=[
        '//shared:pylint',
        ':all-src-for-pylint'
    ],
    zip_safe=False
)


python_tests(
    name='test',
    sources=rglobs('tests/*.py'),
    coverage='clusterfuzz',
    compatibility=['>=2.7','<3'],
    dependencies=[
        ':src',
        '//shared:test_libs',
        '//3rdparty/python:pyfakefs',
        '//3rdparty/python:mock'
    ]
)

