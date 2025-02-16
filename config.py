from typing import Union
import os
import importlib
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

def getenv_float(key: str) -> Union[float, None]:
    value = os.getenv(key)
    if value == None or not value.isdigit():
        return None
    else:
        return float(value)
    

class Common:
    # Secret key used by the flask server. Can be any string value.
    SECRET = os.getenv("COMMON_SECRET")

    # folder used for internal stuff, e.g. caching the repositories
    DATA_FOLDER = os.getenv("DATA_FOLDER") or "data"

    # Folder exposed through the webserver at /content
    CONTENT_FOLDER = os.getenv("CONTENT_FOLDER") or "content"

class ImHexApi:
    # Secret used to verify GitHub's pushes to this API
    SECRET = os.getenv("IMHEXAPI_SECRET").encode()

    # webhook to ping when we get a new crash
    CRASH_WEBHOOK = os.getenv("CRASH_WEBHOOK")

    DATABASE_QUEUE_PERIOD = getenv_float("DATABASE_QUEUE_PERIOD") or 0.1
    DATABASE_RETRY_PERIOD = getenv_float("DATABASE_RETRY_PERIOD") or 1


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
