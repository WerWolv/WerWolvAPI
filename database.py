import sqlite3
import atexit
import config
from pathlib import Path

def define_database(name, tables, path=None):
    db_file = path or Path(config.Common.DATA_FOLDER) / f"{name}.db"

    # create database file if it doesn't exist
    if not db_file.exists():
        db_file.parent.mkdir(parents = True, exist_ok = True)
        db_file.touch()

    # connect to database
    db = sqlite3.connect(db_file, check_same_thread = False)

    # build database structure
    for table_name, structure in tables.items():
        db.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join([f'{key} {value}' for key, value in structure.items()])})")

    # make sure database is closed on exit
    atexit.register(db.close)

    return db

def do_update(db, structure, where, data):
    # build query
    query = f"INSERT OR REPLACE INTO {where} ({', '.join(structure.keys())}) VALUES ({', '.join(['?' for _ in structure.keys()])})"

    # execute query
    db.execute(query, tuple(data.values()))

    # commit changes
    db.commit()