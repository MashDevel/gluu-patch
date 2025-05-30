import os
import concurrent.futures
from typing import Dict, List, Tuple
from fastcdc import fastcdc
from hashlib import sha256

class BlockGenerator:
    def __init__(self, block_size: int = 65536):
        self.block_size = block_size
        self.min_size = int(block_size * 0.5)
        self.max_size = block_size * 2

    def scan(self, files_to_patch: List[str]) -> Dict[str, bytes]:
        blocks = {}
        args = [(filepath, blocks) for filepath in files_to_patch]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            for _ in executor.map(self._run_fastcdc_on_file, args):
                pass
                
        return blocks

    def _run_fastcdc_on_file(self, args: Tuple[str, Dict[str, bytes]]) -> None:
        filepath, blocks = args
        if not os.path.exists(filepath):
            return
        try:
            for result in fastcdc(filepath, self.min_size, self.block_size, 
                                self.max_size, True, sha256):
                blocks[result.hash] = result.data
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            raise

    def _hash_file(self, file_handle) -> str:
        hasher = sha256()
        for chunk in iter(lambda: file_handle.read(8192), b''):
            hasher.update(chunk)
        return hasher.hexdigest() 