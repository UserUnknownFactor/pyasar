import struct, json, shutil, os, re, hashlib, logging, fnmatch

DEFAULT_CHUNK = 4194304
DEFAULT_HASH = "sha256"

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger(__name__)

def is_junk(file, patterns):
    for pattern in patterns:
        if fnmatch.fnmatch(file, pattern):
            return True
    return False

class AsarArchive:
    """ Class for unpacking and repacking Electron ASAR archives """
    def __init__(self, filename, asarfile, files, baseoffset):
        self.filename = filename
        self.asarfile = asarfile
        self.files = files
        self.baseoffset = baseoffset

    def externalize(self, file_patterns: [str|list], verbose=True):
        if isinstance(file_patterns, str):
            file_patterns = [pattern.replace('\\', '/').strip() for pattern in file_patterns.split(',')]

        f = self.asarfile
        f.seek(4)
        json_size = struct.unpack('I', f.read(4))[0] - 8
        f.seek(16)
        content = f.read(json_size).decode("utf-8")
        old_content_len = len(content)

        try:
            header_data = json.loads(content)
            all_files = []
        except json.JSONDecodeError:
            LOGGER.error("Could not parse the ASAR header as valid JSON")
            return

        all_files = []
        def collect_files(obj, path=""):
            if isinstance(obj, dict):
                if 'files' in obj:
                    collect_files(obj['files'], path)
                else:
                    for key, value in obj.items():
                        new_path = f"{path}/{key}" if path else key
                        if isinstance(value, dict):
                            if 'size' in value or 'offset' in value:
                                all_files.append((new_path, value))
                            else:
                                collect_files(value, new_path)

        collect_files(header_data)

        files_to_modify = []
        for file_path, file_obj in all_files:
            normalized_path = file_path.lstrip('/')
            for pattern in file_patterns:
                normalized_pattern = pattern.lstrip('/')
                if fnmatch.fnmatch(normalized_path, normalized_pattern):
                    files_to_modify.append((file_path, file_obj))
                    break
                    
        if not files_to_modify:
            if verbose:
                LOGGER.info(f'No matching files found')
            return

        modified_count = 0
        for file_path, file_obj in files_to_modify:
            file_name = file_path.split('/')[-1]
            original_json = json.dumps({file_name: file_obj})
            modified_obj = {}
            modified_obj['unpacked'] = True
            modified_json = json.dumps({file_name: modified_obj})

            escaped_json = re.escape(original_json).replace('\\"', '(?:\\"|")')
            match = re.search(escaped_json, content)
            if match:
                original_entry = match.group(0)
                length_diff = len(original_entry) - len(modified_json)
                if length_diff < 0:
                    LOGGER.error(f"New entry for {file_path} is {length_diff} bytes longer than the original")
                if length_diff > 0:
                    modified_json = modified_json[:-1] + ' ' * length_diff + '}'

                content = content.replace(original_entry, modified_json, 1)
                modified_count += 1
            else:
                # if we couldn't find it, try a more flexible approach
                pattern = r'"' + re.escape(file_name) + r'"\s*:(\{[^\{\}]*(?:\{[^\{\}]*\}[^\{\}]*)*\})'
                matches = list(re.finditer(pattern, content))
                for match in matches:
                    original_entry = match.group(0)
                    file_obj_str = match.group(1)

                    if ('size' in file_obj and '"size":' in file_obj_str) or \
                       ('offset' in file_obj and '"offset":' in file_obj_str):
                        new_entry = f'"{file_name}":{{"unpacked":true}}'
                        length_diff = len(original_entry) - len(new_entry)
                        if length_diff < 0:
                            LOGGER.error(f"New entry for {file_path} is {length_diff} bytes longer than the original")

                        if length_diff > 0:
                            new_entry = new_entry[:-1] + ' ' * length_diff + '}'

                        content = content.replace(original_entry, new_entry, 1)
                        modified_count += 1
                        break

        if len(content) != old_content_len:
            LOGGER.error("The JSON data should keep the same length")
            return
        if modified_count > 0:
            f.seek(16)
            f.write(content.encode("utf-8"))
            if verbose:
                LOGGER.info(f'Externalized {modified_count} file entries in the ASAR header; \nthey can now be put in "{self.filename}.unpacked" folder now')

    def extract(self, destination, verbose=False):
        """Extracts the given `.asar` file."""
        if not destination:
            destination = ".\\" + os.path.basename(os.path.splitext(self.filename)[0])
        self.__extract_directory('.', self.files["files"], destination, verbose)
        LOGGER.info(f"Extracting to {destination} completed successfully.")

    def __extract_directory(self, path, files, destination, verbose):
        destination_path = os.path.join(destination, path)
        os.makedirs(destination_path, exist_ok=True)

        for name, contents in files.items():
            item_path = os.path.join(path, name)
            if "files" in contents:
                self.__extract_directory(
                    item_path, contents["files"], destination, verbose)
            else:
                self.__extract_file(item_path, contents, destination, verbose)

    def __extract_file(self, path, fileinfo, destination, verbose):
        if verbose:
            LOGGER.info(f"Extracting {path}...")

        if "unpacked" in fileinfo and fileinfo["unpacked"]:
            if verbose:
                LOGGER.info(f"File {path} is marked as unpacked...")
            self.__copy_extracted(path, destination, verbose)
            return

        if "offset" not in fileinfo:
            self.__copy_extracted(path, destination, verbose)
            return

        self.asarfile.seek(self.__absolute_offset(int(fileinfo["offset"])))
        destination_path = os.path.join(destination, path)
        with open(destination_path, "wb") as fp:
            size = abs(int(fileinfo["size"]))
            if "integrity" in fileinfo and "blockSize" in fileinfo["integrity"]:
                block_size = min(abs(int(fileinfo["integrity"]["blockSize"])), 1024 * 1024 * 512)
            else:
                block_size = DEFAULT_CHUNK  # Read in 4 MB chunks
            while size > 0:
                read_size = min(block_size, size)
                contents = self.asarfile.read(read_size)
                size -= read_size
                fp.write(contents)
    
        LOGGER.debug(f"Extracted {path} to {destination_path}")
    
    def __copy_extracted(self, path, destination, verbose):
        unpacked_dir = self.filename + ".unpacked"
        if not os.path.isdir(unpacked_dir):
            if verbose:
                LOGGER.warning(f"Failed to copy unpacked file {path}, no extracted dir {unpacked_dir}")
            return

        source_path = os.path.join(unpacked_dir, path)
        if not os.path.exists(source_path):
            if verbose:
                LOGGER.warning(f"Failed to copy unpacked file {path}, path does not exist")
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
    def open(cls, filename, mode="rb"):
        with open(filename, mode) as asarfile:
            asarfile.seek(4)
            json_size = struct.unpack('I', asarfile.read(4))[0] - 8
            asarfile.seek(16)
            header = asarfile.read(json_size).rstrip(b'\0').decode("utf-8")
            files = json.loads(header)
            return cls(filename, open(filename, mode), files, asarfile.tell())

    @staticmethod
    def calculate_integrity(filename, algorithm, block_size, file_size):
        hash_class = getattr(hashlib, algorithm)
        hash_processor = hash_class()
        block_hashes = []
        with open(filename, "rb") as fp:
            block_number = 0
            while True:
                data = fp.read(block_size)
                if not data:
                    break
                block_hashes.append(hash_class(data).hexdigest())
                hash_processor.update(data)
                block_number += 1
        return {
            "algorithm": algorithm.upper(),
            "hash": hash_processor.hexdigest(),
            "blockSize": block_size,
            "blocks": block_hashes
        }

    @staticmethod
    def repack(source_dir, destination_asar=None, verbose=False, ignore_junk=[], add_integrity=True,
                     block_size=DEFAULT_CHUNK, algorithm=DEFAULT_HASH, executable_files=[]):
        """ Repacks the given directory into the specified `.asar` """
        if not destination_asar:
            destination_asar = os.path.join('.', f"{source_dir}.asar")

        if verbose:
            LOGGER.info(f"Repacking {source_dir} into {destination_asar}")

        file_list = {}
        offset = 0
        unpacked_dir = f"{destination_asar}.unpacked"
        unpacked_files = []

        if os.path.exists(unpacked_dir):
            for root, _, files in os.walk(unpacked_dir):
                for file in files:
                    relative_path = os.path.relpath(os.path.join(root, file), unpacked_dir)
                    unpacked_files.append(relative_path)

        def build_file_list(directory, asar_dict, ignore_junk=False, algorithm="sha256", block_size=DEFAULT_CHUNK):
            nonlocal offset
            if ignore_junk and is_junk(directory, ignore_junk):
                return

            files = []
            subdirectories = []
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    subdirectories.append((item, item_path))
                else:
                    files.append((item, item_path))

            for item, item_path in files:
                size = os.path.getsize(item_path)
                relative_path = os.path.relpath(item_path, source_dir)
                # dict's fields ordered this way to minimize difference with native implementation
                asar_dict[item] = { "size": size }

                if add_integrity:
                    asar_dict[item]["integrity"] = AsarArchive.calculate_integrity(
                        item_path,
                        algorithm=algorithm,
                        block_size=block_size,
                        file_size=size
                    )

                if relative_path in unpacked_files:  # Mark as unpacked
                    asar_dict[item]["unpacked"] = True
                else:
                    asar_dict[item]["offset"] = str(offset)
                    offset += size

                if relative_path in executable_files:
                    asar_dict[item]["executable"] = True

            for item, item_path in subdirectories:
                if ignore_junk and is_junk(item, ignore_junk):
                    continue
                asar_dict[item] = {"files": {}}
                build_file_list(item_path, asar_dict[item]["files"], ignore_junk, algorithm, block_size)

        build_file_list(source_dir, file_list)

        header = json.dumps({"files": file_list}, separators=(',', ':'), ensure_ascii=False).encode("utf-8")
        json_size = len(header)
        aligned_json_size = json_size + (4 - (json_size % 4)) % 4  # align to 4 bytes

        with open(destination_asar, "wb") as asar_out:
            asar_out.write(struct.pack("<I", 4))
            asar_out.write(struct.pack("<I", aligned_json_size + 8))
            asar_out.write(struct.pack("<I", aligned_json_size + 4))
            asar_out.write(struct.pack("<I", json_size)) # or json_size-1?
            asar_out.write(header)
            asar_out.write(b'\0' * (aligned_json_size - json_size))

            def write_files(directory, asar_dict):
                for item, meta in asar_dict.items():
                    item_path = os.path.join(directory, item)
                    if verbose:
                        LOGGER.info(f"Adding {item_path}...")
                    if "files" in meta:
                        write_files(item_path, meta["files"])
                    elif "unpacked" not in meta:  # Only write packed files to the archive
                        with open(item_path, "rb") as f:
                            remaining_size = meta["size"]
                            while remaining_size > 0:
                                buffer = f.read(min(block_size, remaining_size))
                                asar_out.write(buffer)
                                remaining_size -= len(buffer)

            write_files(source_dir, file_list)

        LOGGER.info("Repacking completed successfully.")