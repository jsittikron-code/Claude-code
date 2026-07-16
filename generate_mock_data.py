"""
สร้างไฟล์ข้อมูลจำลอง mock_oee_data.xlsx สำหรับโรงงานผลิตแผ่นไม้ MDF
รันซ้ำได้ตลอดเพื่อสร้างข้อมูลชุดใหม่ (ใช้ seed เพื่อให้ผลลัพธ์คงที่)

หน่วยของข้อมูล
- Date          : วันที่ผลิต (ย้อนหลัง 14 วัน)
- Planned_Time  : เวลาที่วางแผนเดินเครื่อง (นาที)
- Downtime      : เวลาที่เครื่องหยุด/เสีย (นาที)
- Target_Speed  : ความเร็วเป้าหมายของสายการอัดแผ่น (แผ่น/ชั่วโมง)
- Actual_Output : จำนวนแผ่นที่ผลิตได้จริง (แผ่น)
- Defects       : จำนวนแผ่นที่เป็นของเสีย (แผ่น)
"""

from datetime import date, timedelta
import random

import pandas as pd

# ใช้ seed เพื่อให้ตัวเลขจำลองคงที่ทุกครั้งที่รัน
random.seed(2026)

# กำหนดช่วง 14 วันย้อนหลัง (จบที่ 16 ก.ค. 2026)
END_DATE = date(2026, 7, 16)
NUM_DAYS = 14
start_date = END_DATE - timedelta(days=NUM_DAYS - 1)

TARGET_SPEED = 45  # แผ่น/ชั่วโมง (สายการอัดแผ่น MDF)

rows = []
for i in range(NUM_DAYS):
    d = start_date + timedelta(days=i)

    # แผนเดินเครื่อง ~ 3 กะ (1,320-1,440 นาที)
    planned_time = random.choice([1320, 1380, 1440])

    # เวลาเครื่องหยุด: มีวันเสียหนักเป็นบางวันเพื่อให้กราฟมีความผันผวน
    if random.random() < 0.15:
        downtime = random.randint(240, 360)  # วันที่เครื่องเสียหนัก
    else:
        downtime = random.randint(60, 200)   # หยุดปกติ (เปลี่ยนแบบ/ปรับตั้ง)

    run_time_min = planned_time - downtime
    ideal_output = TARGET_SPEED * (run_time_min / 60.0)

    # ผลผลิตจริง = 88%-99% ของอุดมคติ (Performance)
    perf_ratio = random.uniform(0.88, 0.99)
    actual_output = int(round(ideal_output * perf_ratio))

    # ของเสีย 1%-5% ของผลผลิตจริง
    defect_ratio = random.uniform(0.01, 0.05)
    defects = int(round(actual_output * defect_ratio))

    rows.append(
        {
            "Date": d,
            "Planned_Time": planned_time,
            "Downtime": downtime,
            "Target_Speed": TARGET_SPEED,
            "Actual_Output": actual_output,
            "Defects": defects,
        }
    )

df = pd.DataFrame(rows)
df["Date"] = pd.to_datetime(df["Date"])

with pd.ExcelWriter("mock_oee_data.xlsx", engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="OEE_Data")

print("สร้าง mock_oee_data.xlsx สำเร็จ:", len(df), "แถว")
print(df.to_string(index=False))
