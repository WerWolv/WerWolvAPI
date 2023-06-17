from flask import Blueprint, request, Response
import os
from pathlib import Path
import hashlib
import subprocess
import shutil
import threading

import config
from cache import cache

import hashlib
import hmac
import json
from datetime import date
import random
import tarfile
import requests

from database import do_update, define_database

api_name = Path(__file__).stem
app = Blueprint(api_name, __name__, url_prefix = "/" + api_name)

app_data_folder = Path(config.Common.DATA_FOLDER) / api_name
app_content_folder = Path(config.Common.CONTENT_FOLDER) / api_name

# telemetry database
telemetry_primary_structure = {
    "uuid": "varchar(36) primary key", # make uuid unique, so that it only records latest launch
    "version": "varchar(30)",
    "os": "varchar(30)",
    "crash_count": "int",
}

telemetry_primary_table = {
    "telemetry": telemetry_primary_structure,
}

telemetry_db = None

store_folders = [ "patterns", "includes", "magic", "constants", "yara", "encodings", "nodes", "themes" ]
tips_folder = "tips"

def setup():
    os.system(f"git -C {app_data_folder} clone https://github.com/WerWolv/ImHex-Patterns --recurse-submodules")
    os.system(f"git -C {app_data_folder} clone https://github.com/file/file")

def init():
    update_data()
    print("Setting up telemetry database...")
    global telemetry_db
    telemetry_db = define_database("imhex/telemetry", telemetry_primary_table)
    print("Done!")

def update_git_repo(repo):
    repo_dir = app_data_folder / repo
    subprocess.call([ "git", "reset", "--hard" ], cwd = repo_dir)
    subprocess.call([ "git", "clean", "-fd" ], cwd = repo_dir)
    subprocess.call([ "git", "pull" ], cwd = repo_dir)

def update_data():
    try:
        print("Pulling changes...")
        update_git_repo("ImHex-Patterns")
        update_git_repo("file")
        
        print("Building...")
        file_repo_dir = app_data_folder / "file"
        
        shutil.copytree(f'{file_repo_dir}/magic/Magdir/', app_data_folder / "ImHex-Patterns/magic/standard_magic")

        if app_content_folder.exists():
            shutil.rmtree(app_content_folder)
        os.makedirs(app_content_folder)

        print("Taring...")
        for store_folder in store_folders:
            store_path = app_data_folder / "ImHex-Patterns" / store_folder
            for entry in store_path.iterdir():
                if entry.is_dir():
                    shutil.make_archive(entry, "tar", entry)

        print("Copying...")
        for folder in store_folders:
            shutil.copytree(app_data_folder / "ImHex-Patterns" / folder, app_content_folder / folder, False, shutil.ignore_patterns('_schema.json'))

        print("Done!");
    finally:
        cache.set("store_up_to_date", False)
        cache.set("updater_running", False)

@app.route("/pattern_hook", methods = [ 'POST' ])
def pattern_hook():
    signature = hmac.new(config.ImHexApi.SECRET, request.data, hashlib.sha1).hexdigest()

    if "X-Hub-Signature" not in request.headers:
        return Response(status = 401)


    if hmac.compare_digest(signature, request.headers['X-Hub-Signature'].split('=')[1]):
        print("Repository push detected!")

        if not cache.get("updater_running"):
            cache.set("updater_running", True)
            threading.Thread(target = update_data).start()
        else:
            print("Already updating. Skipped building again")

        return Response(status = 200)
    else:
        return Response(status = 401)

@app.route("/crash_upload", methods = [ 'POST' ])
def crash_upload():
    if "file" not in request.files:
        return Response(status = 400)

    file = request.files["file"]

    if file.filename == "":
        return Response(status = 400)

    webhook_data = {
        "content": "New crash report!"
    }

    form_data = {
        "file": (file.filename, file.stream, file.mimetype)
    }

    return requests.post(config.ImHexApi.CRASH_WEBHOOK, files = form_data).text

@app.route("/store")
def store():   
    if not cache.get("store_up_to_date"):
        store = {}
        for folder in store_folders:
            store[folder] = []
            for file in (Path(".") / "content" / "imhex" / folder).iterdir():
                if not file.is_dir():
                    with open(file, "rb") as fd:
                        store[folder].append({
                            "name": Path(file).stem.replace("_", " ").title(),
                            "desc": "",
                            "file": file.name,
                            "url": f"{request.root_url}content/imhex/{folder}/{file.name}",
                            "hash": hashlib.sha256(fd.read()).hexdigest(),
                            "folder": Path(file).suffix == ".tar"
                            })

        cache.set("store_up_to_date", True)
        cache.set("store", store)

    return cache.get("store")

@app.route("/tip")
def get_tip():    
    current_day = date.today().weekday()

    if cache.get("tip_update_date") != current_day:
        cache.set("tip_update_date", current_day)

        files = [file for file in (app_data_folder / "ImHex-Patterns" / tips_folder).iterdir()]
        files = [file for file in files if file.name != "_schema.json"]
        
        with open(random.choice(files)) as fd:
            json_data = json.load(fd)
            tips = json_data['tips']
            cache.set("tip", random.choice(tips))


    return cache.get("tip")

def get_tag():
    return requests.get("https://api.github.com/repos/WerWolv/ImHex/releases/latest").json()["tag_name"]

@app.route("/update/<release>/<os>")
def get_update_link(release, os):
    tag = get_tag()

    if release == "latest":
        base = f"https://github.com/WerWolv/ImHex/releases/download/{tag}/imhex-{tag[1:]}"
        if os == "win-msi":
            return f"{base}-win64.msi"
        elif os == "win-zip":
            return f"{base}-Windows-Portable.zip"
        elif os == "win-zip-nogpu":
            return f"{base}-Windows-Portable-NoGPU.zip"
        elif os == "macos-dmg":
            return f"{base}-macOS.dmg"
        elif os == "macos-dmg-nogpu":
            return f"{base}-macOS-NoGPU.dmg"
        elif os == "linux-flatpak":
            return "https://flathub.org/apps/details/net.werwolv.ImHex"
        elif os == "linux-deb":
            return f"{base}-Ubuntu-22.04.deb"
        elif os == "linux-appimage":
            return f"{base}.AppImage"
        elif os == "linux-arch":
            return f"{base}-ArchLinux.pkg.tar.zst"
        elif os == "linux-fedora-latest":
            return f"{base}-Fedora-Latest.rpm"
        elif os == "linux-fedora-rawhide":
            return f"{base}-Fedora-Rawhide.rpm"
        else:
            return ""
    elif release == "nightly":
        base = "https://nightly.link/WerWolv/ImHex/workflows/build/master"
        if os == "win-msi":
            return f"{base}/Windows%20Installer.zip"
        elif os == "win-zip":
            return f"{base}/Windows%20Portable.zip"
        elif os == "win-zip-nogpu":
            return f"{base}/Windows%20Portable%20NoGPU.zip"
        elif os == "macos-dmg":
            return f"{base}/macOS%20DMG.zip"
        elif os == "macos-dmg-nogpu":
            return f"{base}/macOS%20DMG-NoGPU.zip"
        elif os == "linux-flatpak":
            return "https://flathub.org/apps/details/net.werwolv.ImHex"
        elif os == "linux-deb":
            return f"{base}/Ubuntu%2022.04%20DEB.zip"
        elif os == "linux-appimage":
            return f"{base}/Linux%20AppImage.zip"
        elif os == "linux-arch":
            return f"{base}/ArchLinux%20.pkg.tar.zst.zip"
        elif os == "linux-fedora-latest":
            return f"{base}/Fedora%20Latest%20RPM.zip"
        elif os == "linux-fedora-rawhide":
            return f"{base}/Fedora%20Rawhide%20RPM.zip"
        else:
            return ""
    else:
        return ""

@app.route("/telemetry", methods = [ 'POST' ])
def post_telemetry():
    data = request.json

    if data is None:
        return Response(status = 400)
    
    # make the keys sorted in same order as the structure
    data = {}
    for key in telemetry_primary_structure.keys():
        if key in request.json:
            data[key] = request.json[key]
        else:
            return Response(status = 400)
    
    do_update(telemetry_db, telemetry_primary_structure, "telemetry", data)

    return Response(status = 200, response="OK")
    
@app.route("/pattern_count")
def get_pattern_count():
    return str(len([file for file in (app_data_folder / "ImHex-Patterns" / "patterns").iterdir() if file.is_file()]))
