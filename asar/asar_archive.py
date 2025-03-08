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
    def __init__(self, filename, mode, files, baseoffset):
        self.filename = filename
        self.asarfile = open(filename, mode)
        self.files = files
        self.baseoffset = baseoffset

    def replace(self, file:str, fileinfo:str, verbose:bool=True):
        text_extensions = [".js", ".html", ".ks", ".txt", ".csv", ".json", ".tjs"]
        is_text = any(file.endswith(ext) for ext in text_extensions)
        f_size = os.stat(file).st_size
        old_size = int(fileinfo["size"])
        if (not is_text and f_size != old_size) or (is_text and f_size > old_size):
            if verbose:
                LOGGER.error(f"The size of file {file} ({f_size}) does't match the file in ASAR ({fileinfo['size']}); difference: {f_size - int(fileinfo['size'])}")
            return False
        if not os.path.isfile(file):
            if verbose:
                LOGGER.error(f"The file {file} is not found")
            return False
        with open(file, 'rb') as f:
            data = f.read()
            pad_size = (old_size - len(data))
            if is_text and pad_size > 0:
                data += b'\x0d' * pad_size# just pad the text
                LOGGER.info(f"Padded the data with {pad_size} 0xD bytes")
            if len(data) != old_size:
                if verbose:
                    LOGGER.error(f"The read size of file {file} does't match the file in ASAR ({len(data)} != {fileinfo['size']})")
                return False
            self.asarfile.seek(self.__absolute_offset(int(fileinfo["offset"])))
            self.asarfile.write(data)
            return True
        return False

    def replace_by_dir(self, file_patterns:list, replacement_dir:str, verbose:bool=True):
        all_files = []
        AsarArchive.collect_files(self.files, all_files)

        files_to_modify = AsarArchive.find_files(file_patterns, all_files)
        if not files_to_modify:
            if verbose:
                LOGGER.warning(f'No matching files found from {file_patterns}')
            return
        for normalized_path, fileinfo in files_to_modify:
            real_path = os.path.join(replacement_dir, normalized_path)
            if self.replace(real_path, fileinfo, verbose):
                LOGGER.info(f"Repaced {normalized_path} with {real_path}")

    @staticmethod
    def collect_files(obj, all_files, path=""):
        if not isinstance(obj, dict): return
        if 'files' in obj:
            AsarArchive.collect_files(obj['files'], all_files, path)
        else:
            for key, value in obj.items():
                new_path = f"{path}/{key}" if path else key
                if isinstance(value, dict):
                    if 'size' in value or 'offset' in value:
                        all_files.append((new_path, value))
                    else:
                        AsarArchive.collect_files(value, all_files, new_path)

    @staticmethod
    def find_files(file_patterns, all_files):
        files_to_modify = []
        for file_path, file_obj in all_files:
            normalized_path = file_path.rstrip('/')
            for pattern in file_patterns:
                normalized_pattern = pattern.rstrip('/')
                if re.compile(normalized_pattern).match(normalized_path):
                    #LOGGER.debug(f"{normalized_path}, {normalized_pattern}")
                    files_to_modify.append((normalized_path, file_obj))
                    break
        return files_to_modify

    def externalize(self, file_patterns: list, dump_file: str=None, verbose:bool=True):
        all_files = []
        AsarArchive.collect_files(self.files, all_files)

        files_to_modify = AsarArchive.find_files(file_patterns, all_files)
        if not files_to_modify:
            if verbose:
                LOGGER.info(f'No matching files found from {file_patterns}')
            return

        modified_count = 0
        content = self.content
        for normalized_path, file_obj in files_to_modify:
            file_name = normalized_path.split('/')[-1]
            pattern = r'"' + re.escape(file_name) + r'\"\s*:(\{[^\}]+?"offset":"?'+ str(file_obj['offset']) +'"?[^\}]*?\})'
            #LOGGER.debug(pattern)
            matches = list(re.finditer(pattern, content))
            for match in matches:
                original_entry = match.group(0)
                file_obj_str = match.group(1)

                if ('size' in file_obj and '"size":' in file_obj_str) or ('offset' in file_obj and '"offset":' in file_obj_str):
                    new_entry = f'"{file_name}":{{"unpacked":true}}'
                    length_diff = len(original_entry) - len(new_entry)
                    if length_diff < 0:
                        LOGGER.error(f"New entry for {normalized_path} is {length_diff} bytes longer than the original")
                    elif length_diff > 0:
                        new_entry = new_entry[:-1] + ' ' * length_diff + '}'
                    content = content.replace(original_entry, new_entry, 1)
                    LOGGER.debug(f"Replacing pattern for {normalized_path}: {original_entry} -> {new_entry}")
                    modified_count += 1
                    break

        content = content.encode("utf-8") + self.zeros
        if len(content) != self.json_size:
            LOGGER.error("The JSON data should keep the same length")
            return
        if dump_file:
            dump_file = os.path.abspath(dump_file)
            with open(dump_file, "wb") as o:
                o.write(content)
                LOGGER.info(f"JSON header is written to {dump_file}")
        elif modified_count > 0:
            self.asarfile.seek(16)
            self.asarfile.write(content)
            if verbose:
                LOGGER.info(f'Externalized {modified_count} file entries ({files_to_modify}) in the ASAR header; \nthey can now be put in "{self.filename}.unpacked" folder')
        else:
            LOGGER.warning(f'No matching entries found')

    def extract(self, destination:str, verbose:bool=False):
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
    
    def __copy_extracted(self, path:str, destination:str, verbose:bool):
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

    def __absolute_offset(self, offset:int|str):
        return int(offset) + self.baseoffset

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.asarfile:
            self.asarfile.close()
            self.asarfile = None

    @classmethod
    def open(cls, filename:str, mode:str="rb"):
        with open(filename, mode) as asarfile:
            asarfile.seek(4)
            cls.json_size = struct.unpack('I', asarfile.read(4))[0] - 8
            file_size = asarfile.seek(0, 2)
            if file_size < cls.json_size or cls.json_size == 0:
                raise Exception("Unknown file format")
            asarfile.seek(16)
            cls.content = asarfile.read(cls.json_size)
            n_right_zeroes = 0 if cls.content[len(cls.content)-1] != 0 else next((i for i, c in enumerate(cls.content[::-1]) if c != 0)) # :)
            cls.zeros = cls.content[-n_right_zeroes:] if n_right_zeroes else b''
            cls.content = (cls.content[:-n_right_zeroes] if n_right_zeroes > 0 else cls.content).decode("utf-8")
            files = json.loads(cls.content)
            return cls(filename, mode, files, asarfile.tell())

    @staticmethod
    def calculate_integrity(filename:str, algorithm:str, block_size:int, file_size:int):
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
    def repack(source_dir:str, destination_asar:str=None, verbose:bool=False,
        ignore_junk:list=[], add_integrity:bool=True, block_size:int=DEFAULT_CHUNK,
        algorithm:str=DEFAULT_HASH, executable_files:list=[]):
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