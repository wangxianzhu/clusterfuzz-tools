python_library(
    name='src',
    sources=rglobs('cmd_editor/*.py'),
    compatibility=['>=2.7','<3'],
)


python_library(
    name='all-src-for-pylint',
    sources=rglobs('tests/*.py'),
    compatibility=['>=2.7','<3'],
    dependencies=[
        ':src',
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
    coverage='cmd_editor',
    compatibility=['>=2.7','<3'],
    dependencies=[
        ':src',
        '//shared',
        '//3rdparty/python:pyfakefs',
        '//3rdparty/python:mock'
    ]
)


