from .asar_archive import AsarArchive

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Tool to unpack and repack Electron ASAR files')
    group = parser.add_mutually_exclusive_group()

    parser.add_argument('pathname', type=str, help='The ASAR file to process or input directory')
    group.add_argument('-r', '--repack', help='Repack game archive. Output defaults to "[directory].asar"', action='store_true')
    group.add_argument('-u', '--unpack', help='Unpack game archives. Output defaults to "[asar name without extension]"', action='store_true')
    parser.add_argument('-d', '--directory', type=str, help='The directory of unpacked files')

    args = parser.parse_args()

    import os
    if args.repack:
        if not os.path.exists(args.pathname):
            parser.print_usage()
            print(f"Error: Directory '{args.pathname}' not found.")
            exit(1)
        AsarArchive.repack(args.pathname, args.directory)
        print("Completed!")
    elif args.unpack:
        if not os.path.exists(args.pathname):
            parser.print_usage()
            print(f"Error: File '{args.pathname}' not found.")
            exit(1)
        with AsarArchive.open(args.pathname) as asar:
            asar.extract(args.directory, verbose=True)
        print("Completed!")
    else:
        print("Please provide either --repack or --unpack option")

if __name__ == "__main__":
    main()