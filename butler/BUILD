python_binary(
    name='butler',
    entry_point='butler.main:execute',
    dependencies=[':src'],
    zip_safe=False
)


python_library(
    name='src',
    sources=rglobs('butler/*.py'),
    compatibility=['>=2.7','<3'],
)


python_binary(
    name='pylint',
    entry_point='pylint_cli:main',
    dependencies=[
        '//shared:pylint_cli',
        ':src'
    ],
    zip_safe=False
)
