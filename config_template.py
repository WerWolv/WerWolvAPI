import os
import importlib
from pathlib import Path

class Common:
    # Secret key used by the flask server. Can be any string value.
    SECRET = b''

    # folder used for internal stuff, e.g. caching the repositories
    DATA_FOLDER = "data"

    # Folder exposed through the webserver at /content
    CONTENT_FOLDER = "content"

class ImHexApi:
    # Secret used to verify GitHub's pushes to this API
    SECRET = b''

    # webhook to ping when we get a new crash
    CRASH_WEBHOOK = ""

    DATABASE_QUEUE_PERIOD = 0.1
    DATABASE_RETRY_PERIOD = 1


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