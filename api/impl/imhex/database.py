import sqlite3
import atexit
import config
from pathlib import Path

class async_database:

    def __init__(self, _database: sqlite3.Connection, *, queue_period = 0.1, retry_period = 1, error_callback = lambda e: None):
        self._database = _database
        self._query_queue = []
        self.queue_period = queue_period
        self.retry_period = retry_period
        self.error_callback = error_callback
        self.open = True

    def fetchone(self, query, data, callback):
        self._query_queue.append((query, data, 'fetchone', callback))

    def fetchall(self, query, data, callback):
        self._query_queue.append((query, data, 'fetchall', callback))    

    def exists(self, table, field, data, *, exists=lambda: None, not_exists=lambda: None):
        self.fetchone(f"SELECT EXISTS(SELECT 1 FROM {table} WHERE {field} = ?)", data, lambda query_result: exists() if query_result[0] == 1 else not_exists())

    def commit(self):
        self._query_queue.append((None, None, 'commit', None))
        
    def update(self, query, data):
        self._query_queue.append((query, data, 'update', None))

    def execute(self, query, data):
        self.update(query, data)    

    def close(self):
        self.open = False
        self._database.close()

    def _process_queue_item(self, item):
        try:
            query_result = self._database.execute(item[0], item[1])
            match item[2]:
                case 'fetchone':
                    item[3](query_result.fetchone())
                case 'fetchall':
                    item[3](query_result.fetchall())
                case 'commit':
                    self._database.commit()
                    item[3]()
                case 'update':
                    self._database.execute(item[0], item[1])
                    self._database.commit()
        except sqlite3.OperationalError as e:
            self.error_callback(e)
            print(e)
            if e.sqlite_errorname == 'database is locked':
                return 'retry'
            else:
                return 'failed'
        except sqlite3.ProgrammingError as e:
            print(item)    
        return 'ok'
    
    def _begin_query_process(self):
        import time
        while self.open:
            if len(self._query_queue) > 0:
                # wait for queue period
                time.sleep(self.queue_period)
                item = self._query_queue.pop(0)
                result = self._process_queue_item(item)
                if result == 'retry':
                    self._query_queue.insert(0, item)
                    time.sleep(self.retry_period)
                elif result == 'failed':
                    print("Query failed.")

                
    
def define_database(name, tables, path=None, *, queue_period = 0.1, retry_period = 1, error_callback = lambda e: None):
    db_file = path or Path(config.Common.DATA_FOLDER) / f"{name}.db"

    # create database file if it doesn't exist
    if not db_file.exists():
        db_file.parent.mkdir(parents = True, exist_ok = True)
        db_file.touch()

    # connect to database
    db = sqlite3.connect(db_file, check_same_thread = False)

    db_object = async_database(db, queue_period = queue_period, retry_period = retry_period)
    
    # start query processing thread
    import threading
    process_thread = threading.Thread(target=db_object._begin_query_process, daemon=True)
    process_thread.start()

    # build database structure
    for table_name, structure in tables.items():
        db_object.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join([f'{key} {value}' for key, value in structure.items()])})", ())

    # make sure database is closed on exit
    def shutdown():
        db_object.close()
        process_thread.join()

    atexit.register(shutdown)

    return db_object

def do_update(db: async_database, where, data):
    # build query
    query = f"INSERT OR REPLACE INTO {where} ({', '.join(data.keys())}) VALUES ({', '.join(['?' for _ in data.keys()])})"

    # order data according to structure
    db.execute(query, tuple(data.values()))