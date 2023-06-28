from api.impl.imhex.database import define_database, do_update
import config
from datetime import date, datetime, timedelta

# telemetry database
telemetry_primary_structure = {
    "uuid": "varchar(36) primary key", # make uuid unique, so that it only records latest launch
    "format_version": "int",
    "imhex_version": "varchar(30)",
    "imhex_commit": "varchar(60)",
    "install_type": "varchar(30)",
    "os": "varchar(30)",
    "os_version": "varchar(30)",
    "arch": "varchar(30)",
    "gpu_vendor": "varchar(30)",
    "time": "datetime default current_timestamp"
}

telemetry_crash_count_history_structure = {
    "time": "date default current_date primary key",
    "crash_count": "int"
}

telemetry_unique_users_history_structure = {
    "time": "date default current_date primary key",
    "unique_users_total": "int", # unique users is always increasing, so we can just store the latest value
    "unique_users": "int" # unique users that day
}

telemetry_tables = {
    "telemetry": telemetry_primary_structure,
    "crash_count_history": telemetry_crash_count_history_structure,
    "unique_users_history": telemetry_unique_users_history_structure
}

def log_db_error(e):
    import requests
    form_data = {
        "content": f"```Database encountered error: {e}```"
    }

    requests.post(config.ImHexApi.DATABASE_ERROR_WEBHOOK, data=form_data)

telemetry_db = define_database("imhex/telemetry", telemetry_tables,
                            queue_period=config.ImHexApi.DATABASE_QUEUE_PERIOD,
                            retry_period=config.ImHexApi.DATABASE_RETRY_PERIOD,
                            error_callback=log_db_error)

current_statistics = {}

def update_telemetry(uuid, format_version, imhex_version, imhex_commit, install_type, os, os_version, arch, gpu_vendor):
    # check if the user is already in the database
    telemetry_db.exists("telemetry", "uuid", (uuid,), not_exists=increment_unique_users)
    do_update(telemetry_db, "telemetry", {
        "uuid": uuid,
        "format_version": format_version,
        "imhex_version": imhex_version,
        "imhex_commit": imhex_commit,
        "install_type": install_type,
        "os": os,
        "os_version": os_version,
        "arch": arch,
        "gpu_vendor": gpu_vendor,
    })

def increment_crash_count():
    today = date.today()
    # do some sql magic
    # todo: abstract and generify this
    telemetry_db.update("INSERT OR REPLACE INTO crash_count_history (time, crash_count) VALUES (?, COALESCE((SELECT crash_count FROM crash_count_history WHERE time = ?), 0) + 1)", (today, today))

def increment_unique_users():
    today = date.today()

    def process_unique_history(query_result):
        match len(query_result):
            case 0:
                # no data for today or yesterday, insert new data
                do_update(telemetry_db, "unique_users_history", {
                    "time": today,
                    "unique_users_total": 1,
                    "unique_users": 1
                })
            case 1:
                # might be today is only entry in database, or yesterday is only entry in database
                if query_result[0][0] == today:
                    # today is only entry in database, update data
                    do_update(telemetry_db, "unique_users_history", {
                        "time": today,
                        "unique_users_total": query_result[0][1] + 1,
                        "unique_users": query_result[0][2] + 1
                    })
                else:
                    # yesterday is only entry in database, insert new data
                    do_update(telemetry_db, "unique_users_history", {
                        "time": today,
                        "unique_users_total": query_result[0][1] + 1,
                        "unique_users": 1
                    })
            case 2:
                # data for today and yesterday, update data
                today_data = query_result[0]
                total_unique_users = today_data[1]
                today_unique_users = today_data[2]
                do_update(telemetry_db, "unique_users_history", {
                    "time": today,
                    "unique_users_total": total_unique_users + 1,
                    "unique_users": today_unique_users + 1
                })
            
    
    # get the last two entries in the database
    telemetry_db.fetchall("SELECT time, unique_users_total, unique_users FROM unique_users_history ORDER BY time DESC LIMIT 2", (), callback=process_unique_history)

if __name__ == "__main__":
    # get argv
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "increment_crash_count":
            increment_crash_count()
            print("Crash count incremented")