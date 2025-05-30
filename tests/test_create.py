import os
import json
from hashlib import sha256
import pytest

from src.create.create import create_patch, write_patch_data

def test_create_patch_empty_dir(tmp_path):
    empty = tmp_path / "empty_dir"
    empty.mkdir()
    with pytest.raises(ValueError):
        create_patch(str(empty))

def test_create_and_write_patch(tmp_path):
    sample_dir = tmp_path / "sample"
    sample_dir.mkdir()
    file1 = sample_dir / "foo.txt"
    file1.write_text("hello world")
    file2 = sample_dir / "bar.txt"
    file2.write_text("another file content")

    output = tmp_path / "patchData"

    block_data, bundle_data = create_patch(
        directory=str(sample_dir),
        output=str(output),
        patch_data_path=None,
        block_size=1024,
        compress=False,
        compression_level=0,
        dict_path=None,
        regen_dict=False
    )

    assert isinstance(block_data, dict)
    assert "foo.txt" in block_data and "bar.txt" in block_data
    for info in block_data.values():
        assert isinstance(info, dict)
        assert "hash" in info and "blocks" in info
        assert isinstance(info["blocks"], list) and len(info["blocks"]) > 0

    assert isinstance(bundle_data, dict)
    total_blocks = sum(len(info["blocks"]) for info in block_data.values())
    blocks_in_bundles = sum(len(meta) for meta in bundle_data.values())
    assert blocks_in_bundles == total_blocks

    write_patch_data(block_data, bundle_data, str(output))
    pd_file = output / "patchData.json"
    assert pd_file.exists()
    loaded = json.loads(pd_file.read_text())
    assert loaded["files"] == block_data
    assert loaded["bundles"] == bundle_data

    version_file = output / "version"
    assert version_file.exists()
    expected = sha256(json.dumps(loaded).encode('utf-8')).hexdigest()
    assert version_file.read_text() == expected
