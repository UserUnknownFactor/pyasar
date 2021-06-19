from setuptools import setup

setup(
    name='pyasar',
    packages=['asar'],
    version='1.0.10',
    author='UserUnknownFactor',
    author_email='noreply@example.com',
    description="Library for unpacking and repacking Electron ASAR archives.",
    long_description=open('README.md', encoding='utf-8').read(),
    url='',
    keywords=['asar', 'electron', 'pyasar', 'unpacker', 'repacker', 'packer', 'extractor'],
    entry_points={'console_scripts': ['asar=asar.asar:main']},
)
