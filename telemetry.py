from database import define_database, do_update
from datetime import date, datetime

# telemetry database
telemetry_primary_structure = {
    "uuid": "varchar(36) primary key", # make uuid unique, so that it only records latest launch
    "version": "varchar(30)",
    "os": "varchar(30)",
    "timestamp": "datetime default current_timestamp"
}

telemetry_crash_count_history_structure = {
    "timestamp": "date default current_date primary key",
    "crash_count": "int"
}
telemetry_tables = {
    "telemetry": telemetry_primary_structure,
    "crash_count_history": telemetry_crash_count_history_structure
}

telemetry_db = define_database("imhex/telemetry", telemetry_tables)

current_statistics = None

def update_telemetry(uuid, version, os):
    do_update(telemetry_db, ["uuid", "version", "os"], "telemetry", {
        "uuid": uuid,
        "version": version,
        "os": os
    })

def increment_crash_count():
    today = date.today()
    # do some sql magic
    # todo: abstract and generify this
    telemetry_db.execute("INSERT OR REPLACE INTO crash_count_history (timestamp, crash_count) VALUES (?, COALESCE((SELECT crash_count FROM crash_count_history WHERE timestamp = ?), 0) + 1)", (today, today))
    telemetry_db.commit()

def make_statistics():
    # obtain all telemetry data
    telemetry_data = telemetry_db.execute("SELECT * FROM telemetry").fetchall()
    crash_history_data = telemetry_db.execute("SELECT * FROM crash_count_history").fetchall()

    unique_users = len(telemetry_data)
    os_averages = {}
    version_average = {}

    for telemetry in telemetry_data:
        # select the 'os' field
        _, version, os, timestamp = telemetry

        # process os entries
        os_name, os_version, os_architecture = os.split("/")
        # shorten os_version major {version info} -> major
        os_version = os_version.split(" ")[0]
        # shorten linux and derivatives versions, e.g. 5.4.0-42-generic -> 5.4.0
        if os_version.count("-") > 1:
            os_version = os_version[:os_version.find("-")]  
        if os_name not in os_averages:
            os_averages[os_name] = {
                "avg": 0,
                "versions": {}
            }
            if os_version not in os_averages[os_name]["versions"]:
                os_averages[os_name]["versions"][os_version] = 0
            os_averages[os_name]["versions"][os_version] += 1
            os_averages[os_name]["avg"] += 1

        if version not in version_average:
            version_average[version] = 0
        version_average[version] += 1

    # process average 
    for os_name, os_data in os_averages.items():
        os_data["avg"] /= unique_users
        for os_version, _ in os_data["versions"].items():
            os_data["versions"][os_version] /= unique_users    

    # process version average
    for version, _ in version_average.items():
        version_average[version] /= unique_users

    # create crash histogram
    crash_histogram = {}

    for crash_history in crash_history_data:
        timestamp, crash_count = crash_history
        crash_histogram[timestamp] = crash_count

    return {
        "unique_users": unique_users,
        "os_stat": os_averages,
        "version_stat": version_average,
        "crash_histogram": crash_histogram
    }

def update_data():
    print("Updating telemetry data...")
    # get statistics
    statistics = make_statistics()

    # make it into json
    import json
    statistics_json = json.dumps(statistics)

    # write it to file
    with open("data/imhex/statistics.json", "w") as fd:
        fd.write(statistics_json)

    # update current statistics
    global current_statistics
    current_statistics = statistics
    print("Telemetry data updated")


def setup_background_task():
    # setup background task
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_data, 'interval', hours = 24, id = "update_statistics")
    scheduler.start()

    # update data now
    scheduler.modify_job("update_statistics", next_run_time = datetime.now())

if __name__ == "__main__":
    # get argv
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "increment_crash_count":
            increment_crash_count()
            print("Crash count incremented")
        elif sys.argv[1] == "make_statistics":
            statistics = make_statistics()
            # make it into json
            import json
            statistics_json = json.dumps(statistics, indent = 4)
            with open("data/statistics.json", "w") as fd:
                fd.write(statistics_json)
            print("Statistics generated")