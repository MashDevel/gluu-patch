from typing import Dict, List, Set, Tuple
from .change_log import ChangeLog
from .patch_data import PatchData
from .block_generator import BlockGenerator
from .downloader import Downloader
from .file_patcher import FilePatcher
from .cleaner import Cleaner
import os

class Patcher:
    def __init__(self, patch_data_path: str, install_directory: str):
        self.install_directory = f"{install_directory}/install"
        self.app_data_path = f"{install_directory}/data"
        self.patch_data_path = patch_data_path
        self.change_log = ChangeLog(self.app_data_path)
        self.patch_data = PatchData(self.patch_data_path)
        self.compression = self.patch_data.use_compression
        self.block_generator = BlockGenerator()
        self.downloader = Downloader(self.patch_data_path, self.compression)
        self.file_patcher = FilePatcher(self.install_directory)
        self.cleaner = Cleaner(self.install_directory)

    def _get_local_file_hashes(self) -> Dict[str, str]:
        """Get hashes of all files in the install directory."""
        local_files = {}
        for root, _, files in os.walk(self.install_directory):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.install_directory)
                try:
                    with open(file_path, 'rb') as f:
                        file_hash = self.block_generator._hash_file(f)
                        local_files[rel_path] = file_hash
                except (IOError, OSError):
                    continue
        return local_files

    async def patch(self) -> None:
        new_build = self.patch_data.load_new_build()
        local_files = self._get_local_file_hashes()
        files_to_patch = self.patch_data.get_files_to_patch(new_build, local_files, self.change_log)
        local_blocks = self.block_generator.scan(files_to_patch)
        missing_blocks = self.patch_data.get_missing_blocks(files_to_patch, new_build, local_blocks)
        bundles, blocks_to_download = self.patch_data.find_bundles_and_blocks_to_fetch(
            new_build, missing_blocks, local_blocks, return_mapping=True
        )
        await self.downloader.fetch(bundles, blocks_to_download, local_blocks)
        await self.file_patcher.apply(new_build, local_blocks, files_to_patch)
        self.cleaner.run(new_build, self.change_log)
        self.change_log.save()