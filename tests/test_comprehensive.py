from __future__ import annotations

import os
import random
import string
import subprocess
import sys
from pathlib import Path
import shutil
import json
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def generate_random_text(size_kb: int) -> str:
    """Generate random text of specified size in KB using a predefined list of words."""
    words = [
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "I",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at"
    ]
    # Calculate approximately how many words we need (average word length + space is ~5 chars)
    words_needed = (size_kb * 1024) // 5
    return ' '.join(random.choice(words) for _ in range(words_needed))

def generate_test_data(base_dir: Path) -> None:
    """Generate initial test data with various file types and sizes."""
    # Create directory structure
    dirs = [
        "docs",
        "docs/api",
        "docs/user_guides",
        "data",
        "data/raw",
        "data/processed",
        "config",
        "logs"
    ]
    
    for dir_path in dirs:
        (base_dir / dir_path).mkdir(parents=True, exist_ok=True)
    
    # Generate text files of varying sizes
    text_files = {
        "docs/api/README.md": 2,  # 2KB
        "docs/user_guides/tutorial.txt": 50,  # 50KB
        "data/raw/large_dataset.txt": 1024,  # 1MB
        "config/settings.json": 5,  # 5KB
        "logs/app.log": 100,  # 100KB
    }
    
    for file_path, size_kb in text_files.items():
        with open(base_dir / file_path, 'w') as f:
            f.write(generate_random_text(size_kb))
    
    # Create a JSON config file with some structure
    config = {
        "app_name": "TestApp",
        "version": "1.0.0",
        "settings": {
            "debug": True,
            "max_connections": 100,
            "timeout": 30,
            "features": ["auth", "logging", "metrics"]
        }
    }
    with open(base_dir / "config/config.json", 'w') as f:
        json.dump(config, f, indent=2)

def modify_test_data(base_dir: Path) -> None:
    """Make various modifications to the test data."""
    # Modify some existing files
    with open(base_dir / "docs/api/README.md", 'a') as f:
        f.write("\n\n## New Section\nAdded in the second version.")
    
    # Add new files
    with open(base_dir / "docs/api/changelog.md", 'w') as f:
        f.write("# Changelog\n\n## Version 1.0.1\n- Added new features\n- Fixed bugs")
    
    # Create a large new file
    with open(base_dir / "data/raw/new_dataset.txt", 'w') as f:
        f.write(generate_random_text(2048))  # 2MB
    
    # Delete some files
    (base_dir / "logs/app.log").unlink()
    
    # Modify the config
    with open(base_dir / "config/config.json", 'r') as f:
        config = json.load(f)
    config["version"] = "1.0.1"
    config["settings"]["features"].append("new_feature")
    with open(base_dir / "config/config.json", 'w') as f:
        json.dump(config, f, indent=2)

@pytest.fixture(scope="function")
def test_directories(tmp_path: Path) -> dict[str, Path]:
    """Create and yield test directories, cleaning up after the test.
    
    Args:
        tmp_path: pytest fixture providing a temporary directory
        
    Returns:
        Dictionary containing paths to test, patch, and install directories
    """
    # Create our test directories under the pytest tmp_path
    directories = {
        "test_dir": tmp_path / "comprehensive_test",
        "patch_dir": tmp_path / "comprehensive_patch",
        "install_root": tmp_path / "comprehensive_install"
    }
    
    # Create the directories
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    
    yield directories
    
    # Cleanup is handled automatically by pytest's tmp_path fixture

def test_comprehensive_patching(test_directories: dict[str, Path]) -> None:
    """Test the complete patching workflow including creation, application, and validation.
    
    This test verifies that:
    1. Initial patch creation works
    2. Initial patch application works
    3. Initial validation passes
    4. Second patch creation works
    5. Second patch application works
    6. Final validation passes
    
    Args:
        test_directories: Fixture providing paths to test directories
    """
    test_dir = test_directories["test_dir"]
    patch_dir = test_directories["patch_dir"]
    install_root = test_directories["install_root"]
    
    # Create initial test data
    generate_test_data(test_dir)
    
    # Create and apply first patch
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(patch_dir),
        "--compress",
        "--compression-level", "8"
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Initial patch creation failed: {result.stderr}"
    
    apply_cmd = [
        sys.executable, "-m", "src.gluu", "apply",
        str(install_root),
        "--patch-data", str(patch_dir)
    ]
    result = subprocess.run(apply_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Initial patch application failed: {result.stderr}"
    
    # Validate first installation
    validate_cmd = [
        sys.executable, "-m", "src.gluu", "validate",
        str(install_root)
    ]
    result = subprocess.run(validate_cmd, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "1", "Initial validation failed"
    
    # Modify test data and create second patch
    modify_test_data(test_dir)
    
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(patch_dir),
        "--patch-data", str(patch_dir),
        "--compress",
        "--compression-level", "8"
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Second patch creation failed: {result.stderr}"
    
    # Apply second patch
    apply_cmd = [
        sys.executable, "-m", "src.gluu", "apply",
        str(install_root),
        "--patch-data", str(patch_dir)
    ]
    result = subprocess.run(apply_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Second patch application failed: {result.stderr}"
    
    # Final validation
    validate_cmd = [
        sys.executable, "-m", "src.gluu", "validate",
        str(install_root)
    ]
    result = subprocess.run(validate_cmd, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "1", "Final validation failed"

def test_block_size_variations(test_directories: dict[str, Path]) -> None:
    """Test patching with different block sizes.
    
    Args:
        test_directories: Fixture providing paths to test directories
    """
    test_dir = test_directories["test_dir"]
    patch_dir = test_directories["patch_dir"]
    install_root = test_directories["install_root"]
    
    # Test different block sizes
    block_sizes = [32768, 65536, 131072]  # 32KB, 64KB, 128KB
    
    for block_size in block_sizes:
        # Create test data
        generate_test_data(test_dir)
        
        # Create patch with specific block size
        create_cmd = [
            sys.executable, "-m", "src.gluu", "create",
            str(test_dir),
            "--output", str(patch_dir),
            "--block-size", str(block_size)
        ]
        result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
        assert result.returncode == 0, f"Patch creation failed with block size {block_size}: {result.stderr}"
        
        # Apply and validate
        apply_cmd = [
            sys.executable, "-m", "src.gluu", "apply",
            str(install_root),
            "--patch-data", str(patch_dir)
        ]
        result = subprocess.run(apply_cmd, capture_output=True, text=True, check=True)
        assert result.returncode == 0, f"Patch application failed with block size {block_size}: {result.stderr}"
        
        validate_cmd = [
            sys.executable, "-m", "src.gluu", "validate",
            str(install_root)
        ]
        result = subprocess.run(validate_cmd, capture_output=True, text=True, check=True)
        assert result.stdout.strip() == "1", f"Validation failed with block size {block_size}"
        
        # Clean up for next iteration
        shutil.rmtree(install_root)
        install_root.mkdir()

def test_compression_features(test_directories: dict[str, Path]) -> None:
    """Test patching with different compression settings.
    
    Args:
        test_directories: Fixture providing paths to test directories
    """
    test_dir = test_directories["test_dir"]
    patch_dir = test_directories["patch_dir"]
    install_root = test_directories["install_root"]
    
    # Test different compression levels
    compression_levels = [1, 5, 9]  # Low, medium, high compression
    
    for level in compression_levels:
        # Create test data
        generate_test_data(test_dir)
        
        # Create patch with compression
        create_cmd = [
            sys.executable, "-m", "src.gluu", "create",
            str(test_dir),
            "--output", str(patch_dir),
            "--compress",
            "--compression-level", str(level)
        ]
        result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
        assert result.returncode == 0, f"Patch creation failed with compression level {level}: {result.stderr}"
        
        # Apply and validate
        apply_cmd = [
            sys.executable, "-m", "src.gluu", "apply",
            str(install_root),
            "--patch-data", str(patch_dir)
        ]
        result = subprocess.run(apply_cmd, capture_output=True, text=True, check=True)
        assert result.returncode == 0, f"Patch application failed with compression level {level}: {result.stderr}"
        
        validate_cmd = [
            sys.executable, "-m", "src.gluu", "validate",
            str(install_root)
        ]
        result = subprocess.run(validate_cmd, capture_output=True, text=True, check=True)
        assert result.stdout.strip() == "1", f"Validation failed with compression level {level}"
        
        # Clean up for next iteration
        shutil.rmtree(install_root)
        install_root.mkdir()

def test_dictionary_features(test_directories: dict[str, Path]) -> None:
    """Test patching with dictionary path and regeneration features.
    
    Args:
        test_directories: Fixture providing paths to test directories
    """
    test_dir = test_directories["test_dir"]
    patch_dir = test_directories["patch_dir"]
    install_root = test_directories["install_root"]
    dict_path = patch_dir / "custom.dict"  # File path for dictionary
    
    # Ensure dictionary directory exists and is empty
    if dict_path.exists():
        dict_path.unlink()
    
    # Test dictionary regeneration
    generate_test_data(test_dir)
    
    # First create a patch without dictionary to establish baseline
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(patch_dir),
        "--compress",
        "--compression-level", "5"  # Required when using compression
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Initial patch creation failed: {result.stderr}"
    
    # Now test dictionary regeneration
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(patch_dir),
        "--compress",
        "--compression-level", "5",  # Required when using compression
        "--dict-path", str(dict_path),  # File path where dictionary will be stored
        "--regen-dict"
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Patch creation with dictionary regeneration failed: {result.stderr}"
    assert dict_path.exists(), f"Dictionary file was not created at {dict_path}"
    
    # Test using existing dictionary
    modify_test_data(test_dir)
    
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(patch_dir),
        "--compress",
        "--compression-level", "5",  # Required when using compression
        "--dict-path", str(dict_path)  # File path where dictionary is stored
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Patch creation with existing dictionary failed: {result.stderr}"
    
    # Clean up dictionary file
    if dict_path.exists():
        dict_path.unlink()

def test_validation_failures(test_directories: dict[str, Path]) -> None:
    """Test validation failures by corrupting the installation.
    
    Args:
        test_directories: Fixture providing paths to test directories
    """
    test_dir = test_directories["test_dir"]
    patch_dir = test_directories["patch_dir"]
    install_root = test_directories["install_root"]
    
    # Create and apply initial patch
    generate_test_data(test_dir)
    
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(patch_dir)
    ]
    subprocess.run(create_cmd, capture_output=True, text=True, check=True)
    
    apply_cmd = [
        sys.executable, "-m", "src.gluu", "apply",
        str(install_root),
        "--patch-data", str(patch_dir)
    ]
    result = subprocess.run(apply_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Patch application failed: {result.stderr}"
    
    # Corrupt a file by modifying its content and metadata
    target_file = install_root / "install" / "docs/api/README.md"  # Note: files are in install subdirectory
    target_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write new content and ensure it has different size
    with open(target_file, 'w') as f:
        f.write("Corrupted content" * 100)  # Make it significantly different in size
    
    # Validate should fail
    validate_cmd = [
        sys.executable, "-m", "src.gluu", "validate",
        str(install_root)
    ]
    result = subprocess.run(validate_cmd, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "0", "Validation should have failed with corrupted file"

def test_error_cases(test_directories: dict[str, Path]) -> None:
    """Test various error cases and invalid inputs.
    
    Args:
        test_directories: Fixture providing paths to test directories
    """
    test_dir = test_directories["test_dir"]
    patch_dir = test_directories["patch_dir"]
    
    # Test invalid block size
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(patch_dir),
        "--block-size", "0"  # Invalid block size
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True)
    assert result.returncode != 0, "Should fail with invalid block size"
    
    # Test invalid compression level
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(patch_dir),
        "--compress",
        "--compression-level", "10"  # Invalid compression level
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True)
    assert result.returncode != 0, "Should fail with invalid compression level"
    
    # Test non-existent directory
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir / "non_existent"),
        "--output", str(patch_dir)
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True)
    assert result.returncode != 0, "Should fail with non-existent directory"

def test_different_paths(test_directories: dict[str, Path]) -> None:
    """Test patching with different output and patch data paths.
    
    Args:
        test_directories: Fixture providing paths to test directories
    """
    test_dir = test_directories["test_dir"]
    patch_dir = test_directories["patch_dir"]
    install_root = test_directories["install_root"]
    
    # Create nested output directory
    nested_output = patch_dir / "nested" / "output"
    nested_output.mkdir(parents=True)
    
    # Create test data
    generate_test_data(test_dir)
    
    # Test with nested output path
    create_cmd = [
        sys.executable, "-m", "src.gluu", "create",
        str(test_dir),
        "--output", str(nested_output)
    ]
    result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Patch creation failed with nested output path: {result.stderr}"
    
    # Test applying from nested path
    apply_cmd = [
        sys.executable, "-m", "src.gluu", "apply",
        str(install_root),
        "--patch-data", str(nested_output)
    ]
    result = subprocess.run(apply_cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0, f"Patch application failed with nested patch data path: {result.stderr}"
    
    # Validate
    validate_cmd = [
        sys.executable, "-m", "src.gluu", "validate",
        str(install_root)
    ]
    result = subprocess.run(validate_cmd, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "1", "Validation failed with nested paths" 