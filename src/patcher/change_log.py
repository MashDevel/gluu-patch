import os
import json
from typing import Dict, Optional

class ChangeLog:
    def __init__(self, app_data_path: str):
        self.app_data_path = app_data_path
        self.changelog_path = f"{app_data_path}/changelog.json"
        self._data: Dict = self.load()

    def load(self) -> Dict:
        try:
            with open(self.changelog_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.changelog_path), exist_ok=True)
        with open(self.changelog_path, 'w') as f:
            json.dump(self._data, f)

    def validate_current_installation(self) -> bool:
        for filename in self._data:
            if ".DS_Store" in filename:
                continue
            if not self.is_valid(filename):
                return False
        return True

    def is_valid(self, filename: str) -> bool:
        filepath = os.path.join(os.path.dirname(self.app_data_path), 'install', filename)
        if not os.path.exists(filepath):
            return False
        try:
            current_metadata = self._get_file_metadata(filepath)
            stored_metadata = self._data[filename]
            return (stored_metadata["size"] == current_metadata["size"] and 
                   stored_metadata["lastMod"] == current_metadata["lastMod"])
        except KeyError:
            return False

    def update_metadata(self, filename: str) -> None:
        if ".DS_Store" in filename:
            return
        filepath = os.path.join(os.path.dirname(self.app_data_path), 'install', filename)
        self._data[filename] = self._get_file_metadata(filepath)

    def remove_file(self, filename: str) -> None:
        self._data.pop(filename, None)

    def _get_file_metadata(self, filepath: str) -> Dict[str, str]:
        return {
            "size": str(os.path.getsize(filepath)),
            "lastMod": str(os.path.getmtime(filepath))
        } 