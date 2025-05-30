import zstandard as zstd
import os
from hashlib import sha256
from tqdm import tqdm
from collections import OrderedDict
from .. import util

class BlockBuilder:
    __blockSize = 65536
    __uncompressed_block_data = []
    __data = {}
    __blockSet = OrderedDict()

    def __init__(self, blockSize=65536):
        self.__blockSize = blockSize

    def __processFile(self, filePath, relPath):
        fileData = {"hash" : "", "blocks": []}
        fileHash = []
        for block_hash, block_data, _ in util.extract_blocks(filePath, self.__blockSize):
            self.__uncompressed_block_data.append(block_data)
            self.__blockSet[block_hash] = block_data
            fileHash.append(block_hash)
            fileData["blocks"].append(block_hash)
        fileData["hash"] = sha256(''.join(fileHash).encode('utf-8')).hexdigest()
        self.__data[relPath] = fileData

    def processDir(self, directory):
        for root, subdirs, files in os.walk(os.path.abspath(directory)):
            for filename in files:
                filePath = os.path.join(root, filename)
                relPath = util.getRelPath(filePath, directory)
                self.__processFile(filePath, relPath)
        return dict(sorted(self.__data.items())), self.__blockSet

    def writeBlockFiles(self, outputPath, compress, regenDict, compressionLevel, dict_path):
        os.makedirs(os.path.abspath(outputPath), exist_ok=True)
        if dict_path:
            os.makedirs(os.path.dirname(dict_path), exist_ok=True)
        
        compressor = None
        if compress:
            dict_data = util.load_or_train_dict(
                dict_path, 
                self.__uncompressed_block_data, 
                self.__blockSize,
                samples=2000 if not regenDict else None
            )
            compressor = util.get_compressor(dict_data, compressionLevel)

        with tqdm(self.__blockSet, desc="Create blocks") as pbar:
            for block in pbar:
                blockBinary = self.__blockSet[block]
                if compress and compressor:
                    blockBinary = compressor.compress(blockBinary)
                self.__blockSet[block] = blockBinary
                outputFilename = os.path.join(outputPath, block)
                if os.path.exists(outputFilename):
                    os.remove(outputFilename)
                with open(outputFilename, 'wb') as outputFile:
                    outputFile.write(blockBinary)
        util.cleanup(outputPath, self.__blockSet)
        self.__validate(outputPath)

    def __validate(self, outputPath):
        missing = []
        blockCount = 0
        for file in self.__data:
            for block in self.__data[file]["blocks"]:
                blockCount += 1
                if not os.path.exists(outputPath + '/' + block):
                    missing.append(block)
        if(len(missing) > 0):
            print(f'Missing {len(missing)} generated blocks of {blockCount} in patchData!')