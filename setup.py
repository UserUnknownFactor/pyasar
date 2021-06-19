from setuptools import setup

setup(
    name='pyasar',
    packages=['asar'],
    version='1.0.9',
    author='Swen Kooij (Photonios)',
    author_email='photonios@outlook.com',
    description='Library for unpacking Electron\'s ASAR archives.',
    long_description=open('README.md').read(),
    url='',
    keywords=['asar', 'electron', 'pyasar', 'unpacker', 'extractor'],
    entry_points={'console_scripts': ['unasar=asar.unasar:main']},
)
