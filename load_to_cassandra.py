
from cassandra.cluster import Cluster
import subprocess

HDFS_FILE = "/public_transport_delay/mapreduce_output/part-r-00000"

# Read MapReduce output from HDFS

result = subprocess.run(
    ["C:\\hadoop\\bin\\hdfs.cmd", "dfs", "-cat", HDFS_FILE],
    capture_output=True,
    text=True,
    check=True,
    shell=True
)

cluster = Cluster(["127.0.0.1"], port=9042)
session = cluster.connect("transport_analysis")

insert_query = """
INSERT INTO delay_summary (
    category, category_name, total_journeys, delayed_journeys,
    delay_rate, avg_delay_all, avg_delay_when_delayed
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""

statement = session.prepare(insert_query)
loaded = 0

try:
    for line in result.stdout.splitlines():
        parts = line.split("\t")

        if len(parts) != 6:
            print("Skipping unexpected row:", line)
            continue

        key = parts[0]
        if "|" not in key:
            print("Skipping invalid key:", key)
            continue

        category, category_name = key.split("|", 1)

        total_journeys = int(parts[1])
        delayed_journeys = int(parts[2])
        delay_rate = float(parts[3])
        avg_delay_all = float(parts[4])
        avg_delay_when_delayed = float(parts[5])

        session.execute(statement, (
            category, category_name, total_journeys,
            delayed_journeys, delay_rate, avg_delay_all,
            avg_delay_when_delayed
        ))
        loaded += 1

    print(f"Successfully loaded {loaded} summary rows into Cassandra.")

finally:
    cluster.shutdown()
