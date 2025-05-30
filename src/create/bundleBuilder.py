import os
from hashlib import sha256
from tqdm import tqdm
from .. import util

class BundleBuilder:

    __data = {}
    __blockSet = None
    __oldPatchData = None

    def __init__(self, blockSet, opd):
        self.__blockSet = blockSet
        self.__oldPatchData = opd

    def canMakeBundle(self, bundle):
        for block in bundle:
            if bundle[block]['hash'] not in self.__blockSet:
                return False
        return True

    def makeBundle(self, bundle, path):
        bundleList = {}
        bundleData = []
        length = 0
        i = 0
        for block in bundle:
            hash = bundle[block]['hash']
            result = self.__blockSet[hash]
            bundleList[i] = {"hash": hash, "length": len(result), "blockOffset": length}   
            length += len(result)
            bundleData.append(result)
            del self.__blockSet[hash]
            i += 1
        self.createBundle(bundleList, b''.join(bundleData), path)

    def getBundleId(self, bundleList):
        return sha256(str(bundleList).encode('utf-8')).hexdigest()

    def writeBundle(self, bundleData, id, bundlePath):
        outputFilename = os.path.join(bundlePath + '/' + id)
        if os.path.exists(outputFilename):
            os.remove(outputFilename)
        with open(outputFilename, 'wb') as outputFile:
            outputFile.write(bundleData)

    def createBundle(self, bundleList, bundleData, path):
        id = self.getBundleId(bundleList)
        self.writeBundle(bundleData, id, path)
        self.__data[id] = bundleList

    def buildBundles(self, path):
        os.makedirs(os.path.abspath(path), exist_ok=True)
        blocksProcessed = 0
        bundleList = {}
        bundleData = []
        length = 0
        oldBundles = 0
        with tqdm(self.__oldPatchData["bundles"], desc="Check for old bundles") as pbar:
            for bundle in pbar:
                b = self.__oldPatchData["bundles"][bundle]
                if self.canMakeBundle(b):
                    oldBundles += 1
                    self.makeBundle(b, path)
        print(f"Created {oldBundles}/{len(pbar)} old bundles")

        if len(self.__blockSet) > 0:
            with tqdm(self.__blockSet, desc="Bundle remaining blocks") as pbar:
                for block in pbar:
                    result = self.__blockSet[block]
                    bundleList[blocksProcessed] = {"hash": block, "length": len(result), "blockOffset": length}   
                    length += len(result)
                    bundleData.append(result)
                    if(blocksProcessed == 59):
                        self.createBundle(bundleList, b''.join(bundleData), path)
                        bundleList = {}
                        bundleData = []
                        blocksProcessed = 0
                        length = 0
                    else:
                        blocksProcessed += 1
        if len(bundleList) > 0:
            self.createBundle(bundleList, b''.join(bundleData), path)
        util.cleanup(path, self.__data)
        normalized = {}
        for bundle_id, block_map in self.__data.items():
            normalized[bundle_id] = {
                str(idx): meta
                for idx, meta in block_map.items()
            }
        return normalized