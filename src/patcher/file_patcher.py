import os
import tempfile
from typing import Dict, List
import aiofiles

class FilePatcher:
    def __init__(self, install_directory: str):
        self.install_directory = install_directory

    async def apply(self, new_build: Dict, local_blocks: Dict[str, bytes], 
                    files_to_patch: List[str]) -> None:
        for filename in files_to_patch:
            await self.apply_patch_to_file(filename, new_build, local_blocks)

    async def apply_patch_to_file(self, filename: str, new_build: Dict, 
                                  local_blocks: Dict[str, bytes]) -> None:
        dest_dir = os.path.join(self.install_directory, os.path.dirname(filename))
        os.makedirs(dest_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=dest_dir)
        os.close(fd)

        try:
            async with aiofiles.open(temp_path, 'wb') as f:
                for block in new_build["files"][filename]["blocks"]:
                    await f.write(local_blocks[block])
            final_path = os.path.join(self.install_directory, filename)
            if os.path.exists(final_path):
                os.remove(final_path)
            os.replace(temp_path, final_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
