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
        '//cmd-editor:src',
        '//3rdparty/python:httplib2',
        '//3rdparty/python:oauth2client',
        '//3rdparty/python:urlfetch',
        '//3rdparty/python:psutil',
        '//3rdparty/python:pyOpenSSL',
        '//3rdparty/python:xvfbwrapper',
        '//3rdparty/python:requests',
        '//3rdparty/python:backports.shutil-get-terminal-size',
        '//3rdparty/python:pyyaml',
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
        '//shared',
    ]
)


python_binary(
    name='pylint',
    entry_point='pylint_cli:main',
    dependencies=[
        '//shared:pylint_cli',
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
        '//shared',
        '//3rdparty/python:pyfakefs',
        '//3rdparty/python:mock'
    ]
)

