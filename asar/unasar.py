#!/usr/bin/env python
import sys, os
from asar import AsarArchive

def main():
    if len(sys.argv) != 2:
        print(f'ASAR archive unpacker v1.0')
        print(f'Usage: {os.path.basename(__file__)} file.asar')
        return

    filename = sys.argv[1]
    if os.path.isfile(filename):
        print (f'Extracting {filename}... ', end='', flush=True)
        try:
            with AsarArchive.open(filename) as archive:
                archive.extract(os.getcwd(), verbose=False)
                print('OK')
        except Exception as e:
            print(f'FAILED ({e})')
            return
    else:
        print(f'{filename} is not found.')

if __name__ == "__main__":
    main()
