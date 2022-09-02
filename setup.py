from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name             = 'pySerialTransfer',
    packages         = ['pySerialTransfer'],
    version          = '2.1.7',
    description      = 'Python package used to transmit and receive low overhead byte packets - especially useful for PC<-->Arduino USB communication (compatible with https://github.com/PowerBroker2/SerialTransfer)',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    author           = 'Power_Broker',
    author_email     = 'gitstuff2@gmail.com',
    url              = 'https://github.com/PowerBroker2/pySerialTransfer',
    download_url     = 'https://github.com/PowerBroker2/pySerialTransfer/archive/2.1.7.tar.gz',
    keywords         = ['Arduino', 'serial', 'usb', 'protocol', 'communication'],
    classifiers      = [],
    install_requires = ['pyserial']
)
