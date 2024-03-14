from typing import Dict, List

import subprocess
import shutil
import hashlib
from pathlib import Path
import asyncio
import os

import config


STORE_FOLDERS = [ "patterns", "includes", "magic", "constants", "yara", "encodings", "nodes", "themes" ]

async def get_pattern_metadata(file_path: str, type_: str) -> str:
    """
    Get the associated metadata value of a pattern file, using the `plcli` tool. Returns None if the tool is not found

    type: metadata type to get. Valid values (as of 2023/08/21): name, authors, description, mime, version

    if any error occurs, returns an empty string
    """

    std_folder = Path(config.Common.CONTENT_FOLDER) / "imhex" / "includes"
    
    # run plcli process
    process = await asyncio.create_subprocess_exec("plcli", "info", file_path, "-t", type_, "-I", std_folder, stdout=asyncio.subprocess.PIPE)
    await process.wait()

    stdout, _ = await process.communicate()

    if process.returncode != 0:
        print(stdout.decode())
        print(f"plcli command exited with return code {process.returncode}")
        return ""

    return stdout.decode()

async def semaphore_wrapper(task, semaphore):
    """
    Wrap a task inside a semaphore, to limit tasks concurrency
    """
    async with semaphore:
        await task

class PatternMetadata:
    def __init__(self):
        self.filepath = ""
        self.description = ""
        self.authors = []
        self.mime = []

    async def set_description(self):
        self.description = (await get_pattern_metadata(self.filepath, "description")).strip()

    async def set_author(self):
        raw_data = await get_pattern_metadata(self.filepath, "authors")
        self.authors = list(filter(None, raw_data.split("\n")))

    async def set_mime(self):
        raw_data = await get_pattern_metadata(self.filepath, "mime")
        self.mime = list(filter(None, raw_data.split("\n")))

    def __repr__(self):
        return f"PatternMetadata(filepath={self.filepath},description={self.description},authors={self.authors})"
    
async def get_all_pattern_metadata(folder: str) -> Dict[str, PatternMetadata]:
    """
    Get all metadata (authors and description) for all patterns in a given folder
    """

    # Max number of tasks (commands) that will be run at the same time
    sem = asyncio.Semaphore(50)

    mds = {}
    tasks = []
    for file in os.listdir(folder):
        md = PatternMetadata()
        mds[file] = md
        md.filepath = Path(folder) / file

        tasks.append(semaphore_wrapper(md.set_author(), sem))
        tasks.append(semaphore_wrapper(md.set_description(), sem))
        tasks.append(semaphore_wrapper(md.set_mime(), sem))
        
    await asyncio.gather(*tasks)

    return mds

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
        patterns_mds = asyncio.run(get_all_pattern_metadata(Path(".") / "content" / "imhex" / "patterns"))
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
                    if folder == "patterns" and patterns_mds:
                        md = patterns_mds[file.name]
                        data["authors"] = md.authors
                        data["desc"] = md.description
                        data["mime"] = md.mime
                    store[folder].append(data)

    return store
