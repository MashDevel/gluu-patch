import os
import json
import zstandard
from typing import Dict, List, Set, Tuple, Optional, Union
from .. import util
from .change_log import ChangeLog

class PatchData:
    def __init__(self, patch_data_path: str):
        self.patch_data_path = patch_data_path
        self.patch_data = self.load_new_build()
        self.use_compression = self.patch_data.get("compression", {}).get("enabled", False)
        self.compression_level = self.patch_data.get("compression", {}).get("level", 5)
        self._decompressor: Optional[zstandard.ZstdDecompressor] = None
        if self.use_compression:
            self._decompressor = self._load_decompressor()

    def _load_decompressor(self) -> zstandard.ZstdDecompressor:
        data = util.getDictionary(self.patch_data_path)
        dict_data = zstandard.ZstdCompressionDict(data)
        return zstandard.ZstdDecompressor(dict_data=dict_data)

    def load_new_build(self) -> Dict:
        return util.getPatchData(self.patch_data_path)

    def get_files_to_patch(self, new_build: Dict, local_files: Dict[str, str], 
                          change_log: ChangeLog) -> List[str]:
        """
        Determine which files need patching by comparing new build data with local files.
        local_files should be a dict mapping filenames to their current hashes.
        """
        files_to_patch = []
        for filename in new_build["files"]:
            if (filename not in local_files or 
                new_build["files"][filename]["hash"] != local_files[filename] or
                not change_log.is_valid(filename)):
                files_to_patch.append(filename)
        return files_to_patch

    def get_missing_blocks(self, files_to_patch: List[str], new_build: Dict, 
                          local_blocks: Dict[str, bytes]) -> Set[str]:
        missing_blocks = set()
        for filename in files_to_patch:
            for block in new_build["files"][filename]["blocks"]:
                if block not in local_blocks:
                    missing_blocks.add(block)
        return missing_blocks

    def find_bundles_and_blocks_to_fetch(
        self, 
        new_build: Dict, 
        missing_blocks: Set[str],
        local_blocks: Dict[str, bytes],
        *,
        return_mapping: bool = False
    ) -> Tuple[Union[Dict[str, List[str]], Set[str]], Set[str]]:
        bundle_info = self._analyze_bundles(new_build, missing_blocks)
        bundles_to_download, remaining_blocks = self._bundles_to_download(bundle_info, missing_blocks)
        
        if return_mapping:
            return bundles_to_download, remaining_blocks
            
        return set(bundles_to_download.keys()), remaining_blocks

    def _analyze_bundles(self, new_build: Dict, missing_blocks: Set[str]) -> Dict:
        bundle_info = {}
        for bundle in new_build["bundles"]:
            bundle_size = 0
            blocks_needed = []
            for block in new_build["bundles"][bundle]:
                block_hash = new_build["bundles"][bundle][block]["hash"]
                if block_hash in missing_blocks:
                    blocks_needed.append(block_hash)
                bundle_size += 1
            if bundle_size > 0:
                bundle_info[bundle] = {
                    "percentNeeded": len(blocks_needed) / bundle_size,
                    "blocksNeeded": blocks_needed
                }
        return bundle_info

    def _bundles_to_download(self, bundle_info: Dict, missing_blocks: Set[str]) -> Tuple[Dict[str, List[str]], Set[str]]:
        bundles_to_download = {}
        remaining_blocks = missing_blocks.copy()
        for bundle, info in bundle_info.items():
            if info["percentNeeded"] >= 0.5:
                bundles_to_download[bundle] = info["blocksNeeded"]
                for block in info["blocksNeeded"]:
                    remaining_blocks.discard(block)
        return bundles_to_download, remaining_blocks 