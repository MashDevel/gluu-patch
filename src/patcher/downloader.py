import os
import asyncio
import aiohttp
import zstandard
from typing import Dict, List, Set, Optional, Tuple, NamedTuple
from .. import util

class RangeRequest(NamedTuple):
    start: int
    end: int
    block_hash: str

class Downloader:
    def __init__(self, patch_data_path: str, use_compression: bool = True):
        self.patch_data_path = patch_data_path
        self.use_compression = use_compression
        self._decompressor: Optional[zstandard.ZstdDecompressor] = None
        if use_compression:
            self._decompressor = self._load_decompressor()
        self.total_to_download = 0
        self.total_downloaded = 0

        self.bundle_index: dict[str, dict[str, tuple[int, int]]] = {}
        build_meta = util.getPatchData(patch_data_path)
        for bund_id, blkmap in build_meta.get("bundles", {}).items():
            self.bundle_index[bund_id] = {
                meta["hash"]: (meta["blockOffset"], meta["length"])
                for meta in blkmap.values()
            }


    def _load_decompressor(self) -> zstandard.ZstdDecompressor:
        data = util.getDictionary(self.patch_data_path)
        dict_data = zstandard.ZstdCompressionDict(data)
        return zstandard.ZstdDecompressor(dict_data=dict_data)

    async def fetch(self, bundles: Dict[str, List[str]], blocks_to_download: Set[str],
                   local_blocks: Dict[str, bytes]) -> None:
        self.total_to_download = len(bundles) + len(blocks_to_download)
        self.total_downloaded = 0

        if util.isURL(self.patch_data_path):
            await self._fetch_remote(bundles, blocks_to_download, local_blocks)
        else:
            self._fetch_local(bundles, blocks_to_download, local_blocks)

    async def _fetch_remote(self, bundles: Dict[str, List[str]], blocks_to_download: Set[str],
                          local_blocks: Dict[str, bytes]) -> None:
        connector = aiohttp.TCPConnector(limit=15)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Process bundles with range requests
            bundle_tasks = []
            for bundle_id, needed_blocks in bundles.items():
                # Group blocks by bundle and create range requests
                ranges = self._create_range_requests(bundle_id, needed_blocks)
                if ranges:
                    task = asyncio.create_task(
                        self._fetch_bundle_ranges(session, bundle_id, ranges, local_blocks)
                    )
                    bundle_tasks.append(task)

            # Wait for all bundle range requests to complete
            for task in asyncio.as_completed(bundle_tasks):
                await task
                self._update_progress()

            # Process individual blocks that aren't in bundles
            block_tasks = []
            for block in blocks_to_download:
                task = asyncio.create_task(
                    util.fetch(session, f"{self.patch_data_path}/blocks/{block}", block)
                )
                block_tasks.append(task)

            for task in asyncio.as_completed(block_tasks):
                resp, block_id = await task
                local_blocks[block_id] = self._decompress_if_needed(resp)
                self._update_progress()

    def _fetch_local(self, bundles: Dict[str, List[str]], blocks_to_download: Set[str],
                    local_blocks: Dict[str, bytes]) -> None:
        """Fetch from local filesystem."""
        for bundle in bundles:
            resp = util.loadBinFile(f"{self.patch_data_path}/bundles/{bundle}")
            self._process_bundle_sync(bundle, resp, bundles[bundle], local_blocks)
            self._update_progress()

        for block in blocks_to_download:
            resp = util.loadBinFile(f"{self.patch_data_path}/blocks/{block}")
            local_blocks[block] = self._decompress_if_needed(resp)
            self._update_progress()

    async def _process_bundle(self, bundle_id: str, bundle_data: bytes,
                            needed_blocks: List[str], local_blocks: Dict[str, bytes]) -> None:
        for block_hash in needed_blocks:
            if block_hash in local_blocks:
                continue
            block_info = self._get_block_info(bundle_id, block_hash)
            if block_info:
                offset, length = block_info
                block_data = bundle_data[offset:offset + length]
                local_blocks[block_hash] = self._decompress_if_needed(block_data)

    def _process_bundle_sync(self, bundle_id: str, bundle_data: bytes,
                           needed_blocks: List[str], local_blocks: Dict[str, bytes]) -> None:
        for block_hash in needed_blocks:
            if block_hash in local_blocks:
                continue
            block_info = self._get_block_info(bundle_id, block_hash)
            if block_info:
                offset, length = block_info
                block_data = bundle_data[offset:offset + length]
                local_blocks[block_hash] = self._decompress_if_needed(block_data)

    def _get_block_info(self, bundle_id: str, block_hash: str):
        return self.bundle_index.get(bundle_id, {}).get(block_hash)

    def _decompress_if_needed(self, data: bytes) -> bytes:
        if self.use_compression and self._decompressor:
            return self._decompressor.decompress(data)
        return data

    def _update_progress(self) -> None:
        self.total_downloaded += 1
        progress = round((self.total_downloaded / self.total_to_download) * 100)
        print(f"\rDownload progress: {progress}%", end="")

    def _create_range_requests(self, bundle_id: str, needed_blocks: List[str]) -> List[RangeRequest]:
        """Create a list of range requests for blocks in a bundle."""
        ranges = []
        bundle_blocks = self.bundle_index.get(bundle_id, {})
        
        for block_hash in needed_blocks:
            if block_hash in bundle_blocks:
                offset, length = bundle_blocks[block_hash]
                ranges.append(RangeRequest(offset, offset + length - 1, block_hash))
        
        return sorted(ranges, key=lambda r: r.start)

    async def _fetch_bundle_ranges(self, session: aiohttp.ClientSession, bundle_id: str,
                                 ranges: List[RangeRequest], local_blocks: Dict[str, bytes]) -> None:
        """Fetch multiple ranges from a bundle in a single request."""
        if not ranges:
            return

        # Create range header value
        range_header = ','.join(f'bytes={r.start}-{r.end}' for r in ranges)
        headers = {'Range': range_header}

        async with session.get(f"{self.patch_data_path}/bundles/{bundle_id}", headers=headers) as response:
            if response.status == 206:  # Partial Content
                content_type = response.headers.get('Content-Type', '')
                if 'multipart/byteranges' in content_type:
                    # Handle multipart response
                    boundary = content_type.split('boundary=')[1].strip('"')
                    body = await response.read()
                    await self._process_multipart_response(body, boundary, ranges, local_blocks)
                else:
                    # Handle single range response
                    data = await response.read()
                    self._process_single_range(data, ranges[0], local_blocks)
            else:
                # Fallback to full bundle download if range requests not supported
                resp, _ = await util.fetch(session, f"{self.patch_data_path}/bundles/{bundle_id}", bundle_id)
                await self._process_bundle(bundle_id, resp, [r.block_hash for r in ranges], local_blocks)

    async def _process_multipart_response(self, body: bytes, boundary: str,
                                        ranges: List[RangeRequest], local_blocks: Dict[str, bytes]) -> None:
        """Process a multipart response containing multiple ranges."""
        parts = body.split(f'--{boundary}'.encode())
        for part in parts[1:-1]:  # Skip first (empty) and last (boundary end) parts
            # Extract headers and content
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue
                
            headers = part[:header_end].decode()
            content = part[header_end + 4:].rstrip(b'\r\n')  # Strip trailing newlines
            
            # Parse content range from headers
            content_range = next((h for h in headers.split('\r\n') if h.startswith('Content-Range:')), '')
            if not content_range:
                continue
                
            # Extract range info
            range_info = content_range.split('bytes ')[1].split('/')[0]
            start, end = map(int, range_info.split('-'))
            
            # Find matching range request
            matching_range = next((r for r in ranges if r.start == start and r.end == end), None)
            if matching_range:
                local_blocks[matching_range.block_hash] = self._decompress_if_needed(content)

    def _process_single_range(self, data: bytes, range_req: RangeRequest,
                            local_blocks: Dict[str, bytes]) -> None:
        """Process a single range response."""
        local_blocks[range_req.block_hash] = self._decompress_if_needed(data) 