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
    group.add_argument('-s', '--substitute', type=str, help='Replace provided file with the file from output directory')
    parser.add_argument('-e', '--external', type=str, help='Externalize specific files in the ASAR (comma separated mask or file list)')
    parser.add_argument('-o', '--output', type=str, help='Output file or directory')
    parser.add_argument('-n', '--nojunk', help='Ignore common junk files', action='store_true')
    parser.add_argument('-i', '--integrity', help='Add file integrity info on repack', action='store_true') 
    parser.add_argument('-d', '--dump', help='Dump raw JSON header or only header with --external option', action='store_true') 
    args = parser.parse_args()
    
    def check_exists_or_subst(filename):
        if filename == '' :
            filename = DEFAULT_FILENAME
        if not os.path.exists(filename):
            parser.print_usage()
            print(f"Error: File '{filename}' not found.")
            exit(1)
        return filename

    import os
    if args.repack:
        dir_path = args.pathname
        if dir_path == '':
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
    elif args.substitute:
        file_path = check_exists_or_subst(args.pathname)
        with AsarArchive.open(file_path, "r+b") as asar:
            if isinstance(args.substitute, str):
                substitute = args.substitute.split(',')
            substitute = [pattern.replace('\\\\', '/').strip() for pattern in substitute if pattern]
            output = args.output or "output"
            asar.replace_by_dir(substitute, output, verbose=True)
    elif args.external:
        file_path = check_exists_or_subst(args.pathname)
        with AsarArchive.open(file_path, "r+b") as asar:
            dump = args.output or (file_path + "_header.json") if args.dump else None
            if isinstance(args.external, str):
                args.external = args.external.split(',')
            args.external = [pattern.replace('\\\\', '/').strip() for pattern in args.external if pattern]
            asar.externalize(args.external, dump, verbose=True)
    elif args.dump:
        import struct
        file_path = check_exists_or_subst(args.pathname)
        with open(file_path, "rb") as f:
            f.seek(4)
            json_size = struct.unpack('I', f.read(4))[0] - 8
            f.seek(16)
            content = f.read(json_size)
            out_path = args.output or (file_path + "_header.json")
            with open(out_path, "wb") as o:
                o.write(content)
                print(f"JSON header written to {out_path}")
    elif args.unpack:
        file_path = check_exists_or_subst(args.pathname)
        with AsarArchive.open(file_path) as asar:
            asar.extract(args.output, verbose=True)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()