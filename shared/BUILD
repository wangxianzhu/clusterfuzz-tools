python_library(
    name='shared',
    sources=['helpers.py']
)

python_binary(
    name='coveralls',
    entry_point='coveralls.cli:main',
    dependencies = [
        '3rdparty/python:coveralls',
    ]
)

python_library(
    name='pylint_cli',
    sources=['pylint_cli.py'],
    dependencies = [
        '3rdparty/python:pylint',
    ],
    resources=['.pylintrc'],
)
