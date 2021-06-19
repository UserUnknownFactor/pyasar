# Electron ASAR archive unpacker

This is library for unpacking Electron's ASAR archive files.  

Electron (formely known as Atom Shell) uses it's own archive format to compress files into a single file. The format is somewhat similar to TAR files.

There also exists a [Node.JS package](https://www.npmjs.com/package/asar) for working with ASAR files.

## Installation

PyAsar and can be installed through [Pip](https://pypi.org/):

    pip install --user .

### Example Python usage

    from asar import AsarArchive

    with AsarArchive.open('myasarfile.asar') as archive:
        archive.extract('.')


### Example command line usage

    unasar app.asar


## Disclaimer / License

This is no way associated with Github, Electron or Atom.  
It is free and open-source (free as in beer) for fun and non-profit.  

Licensed under the
[*Do What the Fuck You want Public License*](http://www.wtfpl.net/).
