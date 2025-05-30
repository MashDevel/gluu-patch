# Gluu Patcher

Gluu Patcher is a block-based file patching and distribution tool designed to efficiently create, compress, bundle, and apply updates for directories or applications. It supports incremental patch creation, compression with Zstandard dictionaries, and uploading to a CDN for distribution. The CLI interface allows for creating patches, uploading them, applying updates, and validating installations.

This project is inspired by Riot Games' patching system described in their article ["Supercharging Data Delivery: The New League Patcher"](https://technology.riotgames.com/news/supercharging-data-delivery-new-league-patcher).

## Table of Contents

* [Features](#features)
* [Requirements](#requirements)
* [Installation](#installation)
* [Configuration](#configuration)
* [Usage](#usage)

  * [Create a Patch](#create-a-patch)
  * [Upload a Patch](#upload-a-patch)
  * [Apply a Patch](#apply-a-patch)
  * [Validate Installation](#validate-installation)
* [Project Structure](#project-structure)
* [Development](#development)
* [License](#license)

## Features

* **Block-based differencing**: Splits files into content-defined chunks using FastCDC and SHA-256 hashing for checksum calculation.
* **Zstandard compression**: Optionally compress blocks with Zstandard using trained dictionaries for improved compression ratios.
* **Bundle management**: Automatically groups blocks into bundles for efficient network transfer and CDN storage.
* **Incremental updates**: Leverages previous patch data to only upload/download changed or missing blocks.
* **CDN integration**: Upload patches, blocks, and bundles to DigitalOcean Spaces (S3-compatible) and purge caches automatically.
* **Asynchronous downloader**: Fetches missing blocks and bundles using `aiohttp` for non-blocking I/O.
* **Validation & cleanup**: Validates the current installation and removes orphan files or directories.

## Requirements

* Python 3.8+
* `zstandard`
* `fastcdc`
* `boto3`
* `aiohttp`
* `pydo`
* `python-dotenv`
* `tqdm`

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-org/gluu.git
   cd gluu/src
   ```
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

The `gluu.py` script provides a CLI with the following commands:

### Create a Patch

Generates patch data (blocks, bundles, dictionary, version) for a given directory.

```bash
python gluu.py create <directory> [options]
```

**Options:**

* `-bs, --block-size`: Average block size (default: `65536`).
* `-c, --compress`: Enable block compression.
* `-cl, --compression-level`: Zstd compression level (default: `5`).
* `-dp, --dict-path`: Path to load/save compression dictionary.
* `-rd, --regen-dict`: Force re-generation of the dictionary.
* `-o, --output`: Output directory for patch data (default: `./patchData`).
* `-pd, --patch-data`: Path or URL to previous patch data for incremental diffs.

**Example:**

```bash
python gluu.py create ./my_app -c -cl 9 -o ./patchData -pd https://cdn.example.com/patchData
```

### Upload a Patch

Uploads new patch data (blocks and bundles) to the configured CDN.

```bash
python gluu.py upload <patch_data_dir> [--all]
```

* `--all`: Upload all files, including unchanged blocks and bundles.

### Apply a Patch

Applies patch data to an installation directory. Downloads missing blocks/bundles and reconstructs updated files.

```bash
python gluu.py apply <install_dir> [-pd <patch_data_path>] [--no-compression]
```

* `--no-compression`: Bypass block decompression if patch data is uncompressed.

### Validate Installation

Checks if the current installation matches the recorded changelog metadata.

```bash
python gluu.py validate <install_dir>
```

Returns `1` if valid, `0` otherwise.
