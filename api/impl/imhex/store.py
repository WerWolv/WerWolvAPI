from dataclasses import dataclass
from typing import Dict, List

import subprocess
import shutil
import hashlib
from pathlib import Path
import json


STORE_FOLDERS = [ "patterns", "includes", "magic", "constants", "yara", "encodings", "nodes", "themes" ]

@dataclass
class PatternMetadata:
    filepath: str
    description: str
    authors: List[str]
    mimes: List[str]

def get_all_pattern_metadata(folder: str) -> Dict[str, PatternMetadata]:
    """
    Get all metadata (authors and description) for all patterns in a given folder
    """

    result = subprocess.run(["plcli", "massinfo", "-p", folder], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print("plcli not found, skipping metadata retrieval")
        return None
    
    try:
        patterns_json = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Error decoding plcli massinfo output")
        return None

    patterns_objs = {}
    for filepath, pattern in patterns_json.items():
        obj = PatternMetadata(
            filepath=filepath,
            description=pattern["description"],
            authors=pattern["authors"],
            mimes=pattern["MIMEs"],
        )
        patterns_objs[filepath] = obj

    return patterns_objs

def is_plcli_found() -> bool:
    """
    Check if the plcli executable is found in the PATH
    """
    return shutil.which("plcli") is not None

def gen_store(root_url: str) -> Dict[str, List[Dict]]:
    """
    Generate an object representing the ImHex store, that can be returned by /imhex/store
    """

    if is_plcli_found():
        patterns_mds = get_all_pattern_metadata(Path(".") / "content" / "imhex" / "patterns")
    else:
        patterns_mds = None

    store = {}
    for folder in STORE_FOLDERS:
        store[folder] = []
        for file in (Path(".") / "content" / "imhex" / folder).iterdir():
            if not file.is_dir():
                with open(file, "rb") as fd:
                    data = {
                        "name": Path(file).stem.replace("_", " ").title(),
                        "file": file.name,
                        "url": f"{root_url}content/imhex/{folder}/{file.name}",
                        "hash": hashlib.sha256(fd.read()).hexdigest(),
                        "folder": Path(file).suffix == ".tar",

                        "authors": [],
                        "desc": "",
                        "mime": "",
                        }
                    if folder == "patterns" and patterns_mds and file.name in patterns_mds:
                        md = patterns_mds[file.name]
                        data["authors"] = md.authors
                        data["desc"] = md.description
                        data["mime"] = md.mimes
                    store[folder].append(data)

    return store
