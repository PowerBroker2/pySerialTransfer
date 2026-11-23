from setuptools import setup

setup(
    name             = 'pySerialTransfer',
    packages         = ['pySerialTransfer'],
    version          = '3.0.0',
    python_requires  = '>=3.8',
    description      = 'Python package used to transmit and receive low overhead byte packets - especially useful for PC<-->Arduino USB communication (compatible with https://github.com/PowerBroker2/SerialTransfer)',
    long_description_content_type = "text/markdown",
    author           = 'Power_Broker',
    author_email     = 'gitstuff2@gmail.com',
    url              = 'https://github.com/PowerBroker2/pySerialTransfer',
    keywords         = ['Arduino', 'serial', 'usb', 'protocol', 'communication'],
    classifiers      = [],
    install_requires = ['pyserial>=3.5', 'typer>=0.15.0'],
    entry_points     = {'console_scripts': ['pySerialTransfer=pySerialTransfer.cli:main']},
    extras_require   = {
        'release': ['build>=1', 'twine>=5'],
        'dev': [
            'pytest>=8.1.1',
            'pytest-cov>=5.0.0',
            'pytest-mock>=3.14.0',
        ],
    },
)
