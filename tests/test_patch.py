import os
import json
import pytest
from hashlib import sha256
import tempfile

from src.patcher.change_log import ChangeLog
from src.patcher.patch_data import PatchData

class DummyChangeLog:
    def __init__(self, valid=True):
        self._valid = valid

    def is_valid(self, filename):
        return self._valid


def test_change_log_validate_empty(tmp_path):
    # No changelog file: should load empty and validate True
    data_dir = tmp_path / "data"
    cl = ChangeLog(str(data_dir))
    assert cl.validate_current_installation() is True


def test_change_log_validate_with_invalid_file(tmp_path):
    # Create a dummy changelog.json with a file entry that doesn't exist
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    changelog_path = data_dir / "changelog.json"
    # Add a file entry that won't be found in install
    changelog_path.write_text(json.dumps({"missing.txt": {"size": "0", "lastMod": "0"}}))
    cl = ChangeLog(str(data_dir))
    assert cl.validate_current_installation() is False


def test_get_files_to_patch_new_install(monkeypatch):
    # With empty local_files, should include all new files
    new_build = {"files": {"a.txt": {"hash": "h1"}, "b.txt": {"hash": "h2"}}}
    local_files = {}  # Empty dict for new install
    cl = DummyChangeLog(valid=True)
    
    # Create a temporary patch data directory with proper metadata
    with tempfile.TemporaryDirectory() as tmpdir:
        patch_data = {
            "files": new_build["files"],
            "compression": {"enabled": False}
        }
        with open(os.path.join(tmpdir, "patchData.json"), 'w') as f:
            json.dump(patch_data, f)
        pd = PatchData(tmpdir)
        files = pd.get_files_to_patch(new_build, local_files, cl)
        assert set(files) == {"a.txt", "b.txt"}


def test_get_files_to_patch_up_to_date(monkeypatch):
    # With matching local files, no files to patch
    new_build = {"files": {"a.txt": {"hash": "h1"}}}
    local_files = {"a.txt": "h1"}  # Same hash as new build
    cl = DummyChangeLog(valid=True)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        patch_data = {
            "files": new_build["files"],
            "compression": {"enabled": False}
        }
        with open(os.path.join(tmpdir, "patchData.json"), 'w') as f:
            json.dump(patch_data, f)
        pd = PatchData(tmpdir)
        files = pd.get_files_to_patch(new_build, local_files, cl)
        assert files == []


def test_get_files_to_patch_out_of_date(monkeypatch):
    # With different hashes, should include out of date files
    new_build = {"files": {"a.txt": {"hash": "h1"}, "b.txt": {"hash": "h2"}}}
    local_files = {"a.txt": "h1", "b.txt": "old_hash"}  # b.txt is out of date
    cl = DummyChangeLog(valid=True)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        patch_data = {
            "files": new_build["files"],
            "compression": {"enabled": False}
        }
        with open(os.path.join(tmpdir, "patchData.json"), 'w') as f:
            json.dump(patch_data, f)
        pd = PatchData(tmpdir)
        files = pd.get_files_to_patch(new_build, local_files, cl)
        assert files == ["b.txt"]


def test_get_files_to_patch_invalid(monkeypatch):
    # With invalid change log, should include invalid files
    new_build = {"files": {"a.txt": {"hash": "h1"}}}
    local_files = {"a.txt": "h1"}  # Hash matches but file is invalid
    cl = DummyChangeLog(valid=False)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        patch_data = {
            "files": new_build["files"],
            "compression": {"enabled": False}
        }
        with open(os.path.join(tmpdir, "patchData.json"), 'w') as f:
            json.dump(patch_data, f)
        pd = PatchData(tmpdir)
        files = pd.get_files_to_patch(new_build, local_files, cl)
        assert files == ["a.txt"]


def test_get_missing_blocks():
    files_to_patch = ["file1"]
    new_build = {"files": {"file1": {"blocks": ["b1", "b2"]}}}
    local_blocks = {"b1": b"data1"}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        patch_data = {
            "files": new_build["files"],
            "compression": {"enabled": False}
        }
        with open(os.path.join(tmpdir, "patchData.json"), 'w') as f:
            json.dump(patch_data, f)
        pd = PatchData(tmpdir)
        missing = pd.get_missing_blocks(files_to_patch, new_build, local_blocks)
        assert missing == {"b2"}


def test_find_bundles_and_blocks_to_fetch_full_and_partial():
    # Setup a build with two bundles
    new_build = {
        "bundles": {
            "bundle1": {"0": {"hash": "b1"}, "1": {"hash": "b2"}},
            "bundle2": {"0": {"hash": "b3"}, "1": {"hash": "b4"}, "2": {"hash": "b5"}}
        }
    }
    # Case 1: missing two of two in bundle1, one of three in bundle2
    missing_blocks = {"b1", "b2", "b3"}
    local_blocks = {}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        patch_data = {
            "bundles": new_build["bundles"],
            "compression": {"enabled": False}
        }
        with open(os.path.join(tmpdir, "patchData.json"), 'w') as f:
            json.dump(patch_data, f)
        pd = PatchData(tmpdir)
        bundles, blocks = pd.find_bundles_and_blocks_to_fetch(new_build, missing_blocks, local_blocks)
        assert bundles == {"bundle1"}  # All blocks in bundle1 are missing
        assert blocks == {"b3"}  # Only one block from bundle2 is missing


def test_find_bundles_threshold_equal():
    # 50% threshold should include
    new_build = {
        "bundles": {"bundle": {"0": {"hash": "x"}, "1": {"hash": "y"}}}
    }
    missing_blocks = {"x"}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        patch_data = {
            "bundles": new_build["bundles"],
            "compression": {"enabled": False}
        }
        with open(os.path.join(tmpdir, "patchData.json"), 'w') as f:
            json.dump(patch_data, f)
        pd = PatchData(tmpdir)
        bundles, blocks = pd.find_bundles_and_blocks_to_fetch(new_build, missing_blocks, {})
        assert bundles == {"bundle"}  # 50% threshold met
        assert blocks == set()  # No individual blocks to fetch
