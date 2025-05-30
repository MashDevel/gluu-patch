import os
import json
import asyncio
import urllib.request
import urllib.error
import random
import zstandard as zstd
from hashlib import sha256
from fastcdc import fastcdc
from typing import Optional

def extract_blocks(file_path: str, block_size: int):
    min_size = int(block_size * 0.5)
    max_size = block_size * 2
    for result in fastcdc(file_path, min_size, block_size, max_size, True, sha256):
        yield result.hash, result.data, result

def load_or_train_dict(dict_path: str, uncompressed_data: list, block_size: int, samples: Optional[int] = 2000) -> zstd.ZstdCompressionDict:
    if os.path.exists(dict_path):
        with open(dict_path, 'rb') as f:
            return zstd.ZstdCompressionDict(f.read())
    if samples is not None and len(uncompressed_data) > samples:
        training_sample = random.sample(uncompressed_data, samples)
    else:
        training_sample = uncompressed_data
    dict_bytes = zstd.train_dictionary(block_size, training_sample).as_bytes()
    os.makedirs(os.path.dirname(dict_path), exist_ok=True)
    with open(dict_path, 'wb') as f:
        f.write(dict_bytes)
    return zstd.ZstdCompressionDict(dict_bytes)

def get_compressor(dict_data: zstd.ZstdCompressionDict, level: int, threads: int = -1) -> zstd.ZstdCompressor:
    return zstd.ZstdCompressor(level=int(level), dict_data=dict_data, threads=threads)

def get_decompressor(dict_data: zstd.ZstdCompressionDict) -> zstd.ZstdDecompressor:
    return zstd.ZstdDecompressor(dict_data=dict_data)

def slice_bundle(bundle_data: bytes, metadata: dict, blocks_needed: list, decompressor=None) -> dict:
    out = {}
    for entry in metadata.values():
        h = entry['hash']
        if h not in blocks_needed:
            continue
        start = entry['blockOffset']
        length = entry['length']
        chunk = bundle_data[start:start+length]
        if decompressor:
            chunk = decompressor.decompress(chunk)
        out[h] = chunk
    return out

async def fetch(s, url, id, json=False):
        async with s.get(url) as r:
            if r.status != 200:
                r.raise_for_status()
            if json:
                data = await r.json()
            else:
                data = await r.read()
            await asyncio.sleep(0)
            return data, id

def cleanup(path, data):
    if os.path.exists(path):
        for root, dirs, files in os.walk(path):
            for file in files:
                if(file not in data):
                    os.remove(os.path.join(root, file).replace(os.sep, '/'))

def isURL(url):
    return 'http://' in url or 'https://' in url

def getDictionary(loc):
    if isURL(loc):
        try:
            with urllib.request.urlopen(f"{loc}/dictionary") as response:
                return response.read()
        except urllib.error.URLError:
            print(f"Failed to load dictionary at path {loc}/dictionary")
            exit()
    else:
        try:
            return loadBinFile(f"{loc}/dictionary")
        except:
            print(f"Failed to load dictionary at path {loc}/dictionary")
            exit()

def loadBinFile(loc):
    f = open(loc, mode='rb')
    pd = f.read()
    f.close()
    return pd

def getPatchData(loc):
    if loc == '':
        return {'bundles': {}, 'files': {}}
    elif isURL(loc):
        try:
            with urllib.request.urlopen(f"{loc}/patchData.json") as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError:
            return {'bundles': {}, 'files': {}}
    else:
        try:
            f = open(f"{loc}/patchData.json")
            pd = json.load(f)
            f.close()
            return pd
        except:
            return {'bundles': {}, 'files': {}}

def getRelPath(filePath, directory):
    relPath = os.path.relpath(filePath, directory)
    return relPath.replace(os.sep, '/')