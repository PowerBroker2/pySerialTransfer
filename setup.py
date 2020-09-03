from setuptools import setup

setup(
    name         = 'pySerialTransfer',
    packages     = ['pySerialTransfer'],
    version      = '2.0.3',
    description  = 'Python package used to transmit and receive low overhead byte packets - especially useful for PC<-->Arduino USB communication (compatible with https://github.com/PowerBroker2/SerialTransfer)',
    author       = 'Power_Broker',
    author_email = 'gitstuff2@gmail.com',
    url          = 'https://github.com/PowerBroker2/pySerialTransfer',
    download_url = 'https://github.com/PowerBroker2/pySerialTransfer/archive/2.0.3.tar.gz',
    keywords     = ['Arduino', 'serial', 'usb', 'protocol', 'communication'],
    classifiers  = [],
    install_requires=['pyserial']
)
