from .asar_archive import AsarArchive

DEFAULT_BASENAME = 'app'
DEFAULT_FILENAME = f'{DEFAULT_BASENAME}.asar'
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

    parser.add_argument('pathname', nargs='?', type=str, default='', help='ASAR file or input directory to process (default: app.asar/app)')
    group.add_argument('-r', '--repack', help='Repack game archive. Output defaults to "[directory].asar"', action='store_true')
    group.add_argument('-u', '--unpack', help='Unpack game archives. Output defaults to "[asar_name without extension]"', action='store_true')
    parser.add_argument('-o', '--output', type=str, help='Output file or directory')
    parser.add_argument('-n', '--nojunk', help='Ignore common junk files', action='store_true')
    parser.add_argument('-i', '--integrity', help='Add file integrity info on repack', action='store_true') 
    args = parser.parse_args()

    import os
    if args.repack:
        dir_path = args.pathname
        if dir_path == '' and os.path.exists(DEFAULT_BASENAME):
            dir_path = DEFAULT_BASENAME
        if not os.path.exists(dir_path):
            parser.print_usage()
            print(f"Error: Directory '{dir_path}' not found.")
            exit(1)
        AsarArchive.repack(
            dir_path, 
            args.output, 
            verbose=True, 
            ignore_junk=(JUNK if args.nojunk else []),
            add_integrity = args.integrity
        )
    elif args.unpack:
        file_path = args.pathname
        if file_path == '' and os.path.exists(DEFAULT_FILENAME):
            file_path = DEFAULT_FILENAME
        if not os.path.exists(file_path):
            parser.print_usage()
            print(f"Error: File '{file_path}' not found.")
            exit(1)
        with AsarArchive.open(file_path) as asar:
            asar.extract(args.output, verbose=True)
    else:
        print("Please provide either --repack or --unpack option")

if __name__ == "__main__":
    main()