"""Native filesystem paths without changing serialized project-relative paths."""
import os
from pathlib import Path

def native_path(path):
    value=str(Path(path).resolve())
    if os.name != 'nt' or value.startswith('\\\\?\\'):return Path(value)
    return Path('\\\\?\\UNC\\'+value[2:] if value.startswith('\\\\') else '\\\\?\\'+value)
