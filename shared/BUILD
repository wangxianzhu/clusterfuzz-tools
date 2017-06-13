python_binary(
    name='coveralls',
    entry_point='coveralls.cli:main',
    dependencies = [
        '3rdparty/python:coveralls',
    ]
)

python_library(
    name='pylint',
    sources=rglobs('pylint_cli/*.py'),
    dependencies = [
        '3rdparty/python:pylint',
    ],
    resources=['pylint_cli/.pylintrc'],
)

python_library(
    name='test_libs',
    sources=rglobs('test_libs/*.py')
)
