
python_library(
    name='src',
    sources=rglobs('error/*.py'),
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
    coverage='error',
    compatibility=['>=2.7','<3'],
    dependencies=[
        ':src',
        '//shared:test_libs',
        '//3rdparty/python:pyfakefs',
        '//3rdparty/python:mock'
    ]
)
