# WerWolvAPI

Public repository for my main API endpoint found at https://api.werwolv.net

## Available APIs

- ImHex: In-App "store", tips, repository pulling and updating, etc.
- Misc: Miscelaneous stuff that doesn't fit anywhere really or is too small and insignificant for its own API

## Running

- install dependencies (`pip install -r requirements.txt`)
- potentially create and put variables in .env according to you needs (see .env.example and config.py)
- run using `uwsgi --http :9090 --master -w wsgi:app` (the `uwsgi` command should have been installed by the `uwsgi` dependency)
