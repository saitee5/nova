import sqlite3
import os

def merge():
    src_db = "vigil.db"
    dst_db = "backend/vigil.db"
    if not os.path.exists(src_db) or not os.path.exists(dst_db):
        print("One of the databases does not exist.")
        return

    con_src = sqlite3.connect(src_db)
    con_dst = sqlite3.connect(dst_db)

    # 1. Merge permits
    cur_src = con_src.cursor()
    cur_dst = con_dst.cursor()

    cur_src.execute("SELECT permit_id, permit_type, zone_id, holder, status, window_start, window_end FROM permits")
    permits = cur_src.fetchall()
    print(f"Found {len(permits)} permits in source DB.")
    for p in permits:
        cur_dst.execute("""
            INSERT OR REPLACE INTO permits (permit_id, permit_type, zone_id, holder, status, window_start, window_end)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, p)

    # 2. Merge sensor_readings
    cur_src.execute("SELECT id, ts, zone_id, sensor_type, value, unit, is_anomaly, cycle_num FROM sensor_readings")
    readings = cur_src.fetchall()
    print(f"Found {len(readings)} sensor_readings in source DB.")
    cur_dst.execute("SELECT count(*) FROM sensor_readings")
    dst_readings_count = cur_dst.fetchone()[0]
    if dst_readings_count == 0:
        cur_dst.executemany("""
            INSERT INTO sensor_readings (id, ts, zone_id, sensor_type, value, unit, is_anomaly, cycle_num)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, readings)
        print(f"Inserted {len(readings)} sensor_readings into {dst_db}.")
    else:
        print(f"{dst_db} already has {dst_readings_count} sensor_readings.")

    con_dst.commit()
    con_src.close()
    con_dst.close()
    print("Merge complete!")

if __name__ == "__main__":
    merge()
