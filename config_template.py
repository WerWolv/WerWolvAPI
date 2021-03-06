import os
import importlib
from pathlib import Path

class Common:
    SECRET = b''

    DATA_FOLDER = ""
    CONTENT_FOLDER = ""

class ImHexApi:
    SECRET = b''




def setup():
    os.makedirs(Common.DATA_FOLDER, exist_ok = True)
    os.makedirs(Common.CONTENT_FOLDER, exist_ok = True)

    modules = (Path(__file__).parent / "api").glob("*.py")
    __all__ = [f.stem for f in modules if f.is_file() and f.name != '__init__.py']
    for file in __all__:
        module = importlib.import_module("api." + file)

        os.makedirs(module.app_data_folder, exist_ok = True)
        os.makedirs(module.app_content_folder, exist_ok = True)

        module.setup()

if __name__ == "__main__":
    setup()