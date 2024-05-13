import struct
import json
import shutil
import os
import logging
import fnmatch


logging.basicConfig(level=logging.INFO, format='%(message)s')
LOGGER = logging.getLogger(__name__)

def is_junk(file, patterns):
    for pattern in patterns:
        if fnmatch.fnmatch(file, pattern):
            return True
    return False

class AsarArchive:
    """Class for unpacking and repacking Electron ASAR archives"""
    def __init__(self, filename, asarfile, files, baseoffset):
        self.filename = filename
        self.asarfile = asarfile
        self.files = files
        self.baseoffset = baseoffset

    def extract(self, destination, verbose=False):
        """Extracts the given `.asar` file."""
        if not destination:
            destination = '.\\' + os.path.basename(os.path.splitext(self.filename)[0])
        self.__extract_directory('.', self.files['files'], destination, verbose)

    def __extract_directory(self, path, files, destination, verbose):
        destination_path = os.path.join(destination, path)
        os.makedirs(destination_path, exist_ok=True)

        for name, contents in files.items():
            item_path = os.path.join(path, name)
            if 'files' in contents:
                self.__extract_directory(item_path, contents['files'], destination, verbose)
            else:
                self.__extract_file(item_path, contents, destination, verbose)

    def __extract_file(self, path, fileinfo, destination, verbose):
        if verbose:
            LOGGER.info(f'Extracting {path}...')
        
        if 'offset' not in fileinfo:
            self.__copy_extracted(path, destination)
            return

        self.asarfile.seek(self.__absolute_offset(int(fileinfo['offset'])))
        destination_path = os.path.join(destination, path)
        with open(destination_path, 'wb') as fp:
            size = int(fileinfo['size'])
            chunk_size = 1024 * 1024  # Read in 1 MB chunks
            while size > 0:
                read_size = min(chunk_size, size)
                contents = self.asarfile.read(read_size)
                fp.write(contents)
                size -= read_size

        LOGGER.debug('Extracted %s to %s', path, destination_path)

    def __copy_extracted(self, path, destination):
        unpacked_dir = self.filename + '.unpacked'
        if not os.path.isdir(unpacked_dir):
            if verbose:
                LOGGER.warning('Failed to copy extracted file %s, no extracted dir', path)
            return

        source_path = os.path.join(unpacked_dir, path)
        if not os.path.exists(source_path):
            if verbose:
                LOGGER.warning('Failed to copy extracted file %s, does not exist', path)
            return

        destination_path = os.path.join(destination, path)
        shutil.copyfile(source_path, destination_path)

    def __absolute_offset(self, offset):
        return int(offset) + self.baseoffset

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.asarfile:
            self.asarfile.close()
            self.asarfile = None

    @classmethod
    def open(cls, filename):
        with open(filename, 'rb') as asarfile:
            asarfile.seek(4)
            json_size = struct.unpack('I', asarfile.read(4))[0] - 8
            asarfile.seek(16)
            header = asarfile.read(json_size).rstrip(b'\0').decode('utf-8')
            files = json.loads(header)
            return cls(filename, open(filename, 'rb'), files, asarfile.tell())

    @staticmethod
    def repack(source_dir, destination_asar=None, chunk_size=1024*1024, verbose=False, ignore_junk=[]):
        """Repacks the given directory into the specified `.asar` file."""
        if not destination_asar:
            destination_asar = os.path.join('.', f"{source_dir}.asar")

        if verbose:
            LOGGER.info(f"Repacking {source_dir} into {destination_asar}")
        file_list = {}
        offset = 0

        def build_file_list(directory, asar_dict):
            nonlocal offset
            if ignore_junk and is_junk(directory, ignore_junk):
                return
            for item in os.listdir(directory):
                if ignore_junk and is_junk(item, ignore_junk):
                    continue
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    asar_dict[item] = {'files': {}}
                    build_file_list(item_path, asar_dict[item]['files'])
                else:
                    size = os.path.getsize(item_path)
                    asar_dict[item] = {
                        'size': size,
                        'offset': str(offset)
                    }
                    offset += size

        build_file_list(source_dir, file_list)

        header = json.dumps({'files': file_list}, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        json_size = len(header)
        aligned_json_size = json_size + (4 - (json_size % 4)) % 4 # align to 4 bytes

        with open(destination_asar, 'wb') as asar_out:
            asar_out.write(struct.pack('<I', 4))
            asar_out.write(struct.pack('<I', aligned_json_size + 8))
            asar_out.write(struct.pack('<I', aligned_json_size + 4))
            asar_out.write(struct.pack('<I', json_size - 1)) # or json_size?
            asar_out.write(header)
            asar_out.write(b'\0' * (aligned_json_size - json_size))

            def write_files(directory, asar_dict):
                for item, meta in asar_dict.items():
                    item_path = os.path.join(directory, item)
                    if verbose:
                        LOGGER.info(f'Adding {item_path}...')
                    if 'files' in meta:
                        write_files(item_path, meta['files'])
                    else:
                        with open(item_path, 'rb') as f:
                            remaining_size = meta['size']
                            while remaining_size > 0:
                                buffer = f.read(min(chunk_size, remaining_size))
                                asar_out.write(buffer)
                                remaining_size -= len(buffer)

            write_files(source_dir, file_list)

