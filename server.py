import mimetypes
from pathlib import Path
import importlib

import config
from cache import cache

from flask import Flask, send_from_directory
app = Flask(__name__)

cache.init_app(app = app, config={ "CACHE_TYPE": "filesystem", "CACHE_DIR": Path("./data/cache")})
cache.clear()

@app.route("/")
def base():
    return "WerWolv's API Endpoints"

@app.route("/content/<path:filename>")
def download_content(filename):    
    content_path = Path(app.root_path) / "content"
    return send_from_directory(directory = content_path, path = filename, as_attachment = True, mimetype="Content-Type: application/octet-stream")


app.secret_key = config.Common.SECRET

modules = (Path(__file__).parent / "api").glob("*.py")
__all__ = [f.stem for f in modules if f.is_file() and f.name != '__init__.py']
for file in __all__:
    module = importlib.import_module("api." + file)

    @module.app.route("/")
    def base():
        return file.capitalize() + " API Endpoint"

    module.setup()
    module.init()
    app.register_blueprint(module.app)

if __name__ == "__main__":
    app.run()