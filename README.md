# Electron ASAR-archive unpack/repack tool 

This is library for parsing Electron's ASAR archive files.  

Electron (formerly known as Atom Shell) uses it's own archive format to compress files into a single file. The format is somewhat similar to TAR files.

There also exists a [Node.JS package](https://github.com/electron/asar) for working with ASAR files.

## Installation

PyASAR and can be installed through [pip](https://pypi.org/):

    pip install --user .

### Example Python usage

```python
    from asar import AsarArchive
    
    with AsarArchive.open('myfile.asar') as archive:
        archive.extract('.')
    
    AsarArchive.repack('my_dir', 'myfile.asar')
```

### Example command line usage

    asar -u app.asar
    asar -u
    asar -r -i -n -o app.asar app_unpacked

## Disclaimer / License

This is no way associated with Github, Electron or Atom.  
It is free (free as in beer) and open-source for fun and non-profit.  

Licensed under the
[*Do What The Fuck You Want To Public License*](http://www.wtfpl.net/).
