import json
from hashlib import sha256
from .blockBuilder import BlockBuilder
from .bundleBuilder import BundleBuilder
from .. import util

def create_patch(directory, output='./patchData', patch_data_path=None, 
                block_size=65536, compress=False, compression_level=5,
                dict_path=None, regen_dict=False):
    if compress:
        dict_path = dict_path or f"{output}/dictionary"
    else:
        dict_path = None
    
    block_builder = BlockBuilder(blockSize=block_size)
    block_data, block_set = block_builder.processDir(directory)
    
    if len(block_data) == 0 or len(block_set) == 0:
        raise ValueError("No files processed. Ensure directory exists and check permissions.")
    
    block_builder.writeBlockFiles(
        f"{output}/blocks",
        compress=compress,
        regenDict=regen_dict,
        compressionLevel=compression_level,
        dict_path=dict_path
    )
    
    old_patch_data = util.getPatchData(patch_data_path or output)
    bundle_builder = BundleBuilder(block_set, old_patch_data)
    bundle_data = bundle_builder.buildBundles(f"{output}/bundles")
    
    write_patch_data(block_data, bundle_data, output, compress, compression_level)
    return block_data, bundle_data

def write_patch_data(block_data, bundle_data, output, compress=False, compression_level=5):
    data = {
        "compression": {
            "enabled": compress,
            "level": compression_level if compress else None
        },
        "files": block_data,
        "bundles": bundle_data
    }
    
    with open(f"{output}/patchData.json", "w") as maps:
        maps.write(json.dumps(data))
    
    version_hash = sha256(json.dumps(data).encode('utf-8')).hexdigest()
    with open(f"{output}/version", 'w') as version_file:
        version_file.write(version_hash) 