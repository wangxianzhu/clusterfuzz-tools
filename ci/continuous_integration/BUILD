
python_binary(
    name='daemon',
    entry_point='daemon.main:main',
    dependencies=[':src'],
    zip_safe=False
)


python_library(
    name='src',
    sources=rglobs('daemon/*.py'),
    dependencies=[
        '//3rdparty/python:pyyaml',
        '//3rdparty/python:httplib2',
        '//3rdparty/python:oauth2client'
    ],
    resources=['daemon/sanity_checks.yml'],
    compatibility=['>=2.7', '<3']
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
    coverage='daemon',
    compatibility=['>=2.7','<3'],
    dependencies=[
        ':src',
        '//shared',
        '//3rdparty/python:pyfakefs',
        '//3rdparty/python:mock',
        '//3rdparty/python:py-lru-cache',
        '//3rdparty/python:requests'
    ]
)
