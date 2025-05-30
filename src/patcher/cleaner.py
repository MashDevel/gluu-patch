import os
from typing import Dict
import concurrent.futures
from .change_log import ChangeLog

class Cleaner:
    def __init__(self, install_directory: str):
        self.install_directory = install_directory

    def run(self, new_build: Dict, change_log: ChangeLog) -> None:
        files_to_process = []
        dirs_to_check = []
        
        for root, subdirs, files in os.walk(os.path.abspath(self.install_directory), topdown=False):
            for file in files:
                files_to_process.append((root, file, new_build, change_log))
            dirs_to_check.append(root)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            executor.map(self._cleanup_file, files_to_process)

        for directory in dirs_to_check:
            self._delete_empty_folders(directory)

    def _cleanup_file(self, args):
        root, filename, new_build, change_log = args
        filepath = os.path.join(root, filename)
        rel_path = os.path.relpath(filepath, self.install_directory)
        rel_path = rel_path.replace(os.sep, '/')

        if rel_path not in new_build.get("files", {}):
            if rel_path == ".DS_Store":
                return
            change_log.remove_file(rel_path)
            try:
                os.remove(filepath)
            except FileNotFoundError:
                pass
        else:
            change_log.update_metadata(rel_path)

    def _delete_empty_folders(self, directory: str) -> None:
        try:
            if not os.listdir(directory):
                os.rmdir(directory)
        except (OSError, FileNotFoundError):
            pass
