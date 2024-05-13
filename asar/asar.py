from .asar_archive import AsarArchive

JUNK = [
    "desktop.ini", #Custom folder settings for Windows
    ".DS_Store", #Custom folder settings for macOS
    "Thumbs.db", #Thumbnail cache for Windows Explorer
    "._*", #Resource fork and Finder information files on macOS
    "~$*", #Temporary files created by Microsoft Office applications
    "*.tmp", #General temporary files
    "*.temp", #General temporary files
    "*.bak", #Backup files created by various applications
    "*.old", #Old version of files
    ".vs", #VSCode caches
    "__pycache__", #Python caches
    ".git", #Version control history for Git repositories
]

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Tool to unpack and repack Electron ASAR files')
    group = parser.add_mutually_exclusive_group()

    parser.add_argument('pathname', type=str, help='The ASAR file to process or input directory')
    group.add_argument('-r', '--repack', help='Repack game archive. Output defaults to "[directory].asar"', action='store_true')
    group.add_argument('-u', '--unpack', help='Unpack game archives. Output defaults to "[asar name without extension]"', action='store_true')
    parser.add_argument('-d', '--directory', type=str, help='The directory of unpacked files')
    parser.add_argument('-n', '--nojunk', help='Ignore common junk files', action='store_true')
    
    args = parser.parse_args()

    import os
    if args.repack:
        if not os.path.exists(args.pathname):
            parser.print_usage()
            print(f"Error: Directory '{args.pathname}' not found.")
            exit(1)
        AsarArchive.repack(
            args.pathname, 
            args.directory, 
            verbose=True, 
            ignore_junk=(JUNK if args.nojunk else [])
        )
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