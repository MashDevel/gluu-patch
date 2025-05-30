import json
from hashlib import sha256
from src.create import create_patch, write_patch_data
from src.create import blockBuilder as b
from src.create import bundleBuilder as bb
from src.patcher import Patcher
from argparse import ArgumentParser
from src import util
import asyncio

parser = ArgumentParser()

def define_args():

    subparsers = parser.add_subparsers(title="Gluu Patcher Commands", dest="subcommand")
    patch_parser = subparsers.add_parser("create", help="Create a patch")

    patch_parser.add_argument("directory", help="The directory to process for patching")
    patch_parser.add_argument("-bs", "--block-size", dest="blockSize", help="Set average size of block (default=65536)")
    patch_parser.add_argument("-c", "--compress", action="store_true", dest="compress", help="Compress blocks")
    patch_parser.add_argument("-cl", "--compression-level", help="Set compression level")
    patch_parser.add_argument("-dp", "--dict-path", help="Custom compression dictionary path (used for both loading and writing)")
    patch_parser.add_argument("-rd", "--regen-dict", action="store_true", dest="regen_dict", help="Generate a new dictionary")
    patch_parser.add_argument("-o", "--output", dest="output", help="Output directory for patch data")
    patch_parser.add_argument("-pd", "--patch-data", dest="patch_data", help="Path or URL to the previous patchData")

    patch_parser = subparsers.add_parser("apply", help="Apply a patch")
    patch_parser.add_argument("directory", help="The directory to apply the patch to")
    patch_parser.add_argument("-pd", "--patch-data", dest="patch_data", help="Path or URL to the new patchData")

    patch_parser = subparsers.add_parser("validate", help="Check a directory to see if an installation is corrupted")
    patch_parser.add_argument("directory", help="The directory to check")

def main():
    define_args()
    args = parser.parse_args()
    if args.subcommand == "create":
        makePatch(args)
    elif args.subcommand == "apply":
        applyPatch(args)
    elif args.subcommand == "validate":
        validateInstall(args)

def validateInstall(args):
    patcher = Patcher('', args.directory)
    if patcher.change_log.validate_current_installation():
        print('1', end="")
    else:
        print('0', end="")

def applyPatch(args):
    patch_data_path = args.patch_data if args.patch_data else ''
    patcher = Patcher(patch_data_path, args.directory)
    asyncio.run(patcher.patch())

def makePatch(args):
    try:
        block_data, bundle_data = create_patch(
            directory=args.directory,
            output=args.output or './patchData',
            patch_data_path=args.patch_data,
            block_size=int(args.blockSize) if args.blockSize else 65536,
            compress=args.compress if args.compress else False,
            compression_level=int(args.compression_level) if args.compression_level else 5,
            dict_path=args.dict_path,
            regen_dict=args.regen_dict if args.regen_dict else False
        )
        write_patch_data(block_data, bundle_data, args.output or './patchData')
    except ValueError as e:
        print(str(e))
        exit(1)

main()