"""ชุดข้อมูลฝึก — เลียนแบบข้อมูลจริงของฝ่ายซ่อมบำรุง/ผลิต
============================================================

สร้างด้วยตัวสุ่มที่ล็อกเมล็ดไว้ (`random.Random(2026)`) ผลจึง **เหมือนเดิมทุกครั้ง**
ซึ่งจำเป็นมาก เพราะเฉลยของแบบฝึกหัด pandas อ้างอิงตัวเลขจากชุดข้อมูลนี้โดยตรง
ถ้าข้อมูลเปลี่ยนทุกครั้งที่เปิดแอป การตรวจคำตอบจะเชื่อถือไม่ได้

ไฟล์ที่ได้ถูกส่งเข้าไปวางในโฟลเดอร์ชั่วคราวตอนตรวจคำตอบ ผู้เรียนจึงเปิดอ่านได้ตรง ๆ
ด้วยชื่อสั้น ๆ เช่น `pd.read_csv("production.csv")` เหมือนไฟล์อยู่ข้างสคริปต์
"""

from __future__ import annotations

import random
from datetime import date, timedelta

MACHINES = [
    # (รหัส, ชื่อ, สายการผลิต, ปีที่ติดตั้ง, กำลังไฟ kW)
    ("M01", "เลื่อยตัดแผ่น", "Line A", 2016, 15.0),
    ("M02", "เครื่องปิดขอบ", "Line A", 2018, 11.5),
    ("M03", "เครื่องเจาะ CNC", "Line A", 2021, 22.0),
    ("M04", "เลื่อยตัดแผ่น", "Line B", 2014, 15.0),
    ("M05", "เครื่องปิดขอบ", "Line B", 2019, 11.5),
    ("M06", "เครื่องพ่นสี", "Line B", 2020, 30.0),
    ("M07", "เครื่องประกอบ", "Line C", 2022, 7.5),
    ("M08", "เครื่องห่อฟิล์ม", "Line C", 2017, 5.5),
]

CAUSES = [
    "มอเตอร์ร้อนเกิน", "สายพานขาด", "เซนเซอร์เพี้ยน", "ลมดันตก",
    "ใบมีดสึก", "ระบบไฟฟ้าขัดข้อง", "โปรแกรมค้าง", "หัวฉีดอุดตัน",
]
TECHS = ["สมชาย", "วิรัช", "ปกรณ์", "ธนา"]
SHIFTS = ["กะเช้า", "กะบ่าย"]

START = date(2026, 6, 1)
DAYS = 30


def _rows_production() -> list[tuple]:
    rnd = random.Random(2026)
    rows = []
    for d in range(DAYS):
        day = START + timedelta(days=d)
        if day.weekday() == 6:                      # อาทิตย์หยุด
            continue
        for code, _name, line, year, _kw in MACHINES:
            for shift in SHIFTS:
                planned = 480
                # เครื่องเก่าเสียบ่อยกว่า — ใส่ความสัมพันธ์นี้ไว้ให้ผู้เรียนหาเจอ
                age = 2026 - year
                downtime = max(0, int(rnd.gauss(6 + age * 2.2, 12)))
                downtime = min(downtime, 240)
                run_min = planned - downtime
                rate = rnd.uniform(0.75, 1.0)
                total = int(run_min * rate * 1.2)
                reject = int(total * rnd.uniform(0.005, 0.06))
                rows.append((day.isoformat(), code, line, shift, planned,
                             downtime, total - reject, reject))
    return rows


def _rows_breakdown() -> list[tuple]:
    rnd = random.Random(77)
    rows = []
    bid = 1
    for d in range(DAYS):
        day = START + timedelta(days=d)
        if day.weekday() == 6:
            continue
        for code, _name, _line, year, _kw in MACHINES:
            age = 2026 - year
            if rnd.random() < 0.06 + age * 0.012:
                rows.append((f"B{bid:03d}", day.isoformat(), code,
                             rnd.choice(CAUSES), int(rnd.triangular(15, 300, 60)),
                             rnd.choice(TECHS)))
                bid += 1
    return rows


def _csv(header: list[str], rows: list[tuple]) -> str:
    out = [",".join(header)]
    out += [",".join(str(c) for c in r) for r in rows]
    return "\n".join(out) + "\n"


MACHINE_CSV = _csv(
    ["machine_id", "name", "line", "install_year", "power_kw"],
    [(c, n, l, y, k) for c, n, l, y, k in MACHINES],
)

PRODUCTION_CSV = _csv(
    ["date", "machine_id", "line", "shift", "planned_min", "downtime_min",
     "good_qty", "reject_qty"],
    _rows_production(),
)

BREAKDOWN_CSV = _csv(
    ["bd_id", "date", "machine_id", "cause", "minutes", "technician"],
    _rows_breakdown(),
)

# ไฟล์ข้อความสำหรับฝึกงานกับ string/ไฟล์ (บทที่ 5)
LOG_TXT = """2026-06-01 07:12 M01 START
2026-06-01 09:40 M01 ALARM มอเตอร์ร้อนเกิน
2026-06-01 10:05 M01 RESUME
2026-06-01 16:00 M01 STOP
2026-06-02 07:05 M03 START
2026-06-02 11:22 M03 ALARM โปรแกรมค้าง
2026-06-02 11:58 M03 RESUME
2026-06-02 15:47 M03 ALARM เซนเซอร์เพี้ยน
2026-06-02 16:10 M03 STOP
2026-06-03 07:00 M06 START
2026-06-03 13:31 M06 ALARM หัวฉีดอุดตัน
2026-06-03 14:02 M06 RESUME
2026-06-03 16:00 M06 STOP
"""

# ไฟล์ประกอบที่ส่งให้แบบฝึกหัดใช้ (ชื่อไฟล์ -> เนื้อหา)
FILES = {
    "machines.csv": MACHINE_CSV,
    "production.csv": PRODUCTION_CSV,
    "breakdown.csv": BREAKDOWN_CSV,
    "machine_log.txt": LOG_TXT,
}

SCHEMA_DOC = {
    "machines.csv": [
        ("machine_id", "ข้อความ", "รหัสเครื่อง เช่น M01"),
        ("name", "ข้อความ", "ชื่อเครื่องจักร"),
        ("line", "ข้อความ", "สายการผลิต Line A/B/C"),
        ("install_year", "จำนวนเต็ม", "ปีที่ติดตั้ง"),
        ("power_kw", "ทศนิยม", "กำลังไฟฟ้า (kW)"),
    ],
    "production.csv": [
        ("date", "ข้อความ (YYYY-MM-DD)", "วันที่ผลิต"),
        ("machine_id", "ข้อความ", "รหัสเครื่อง"),
        ("line", "ข้อความ", "สายการผลิต"),
        ("shift", "ข้อความ", "กะเช้า / กะบ่าย"),
        ("planned_min", "จำนวนเต็ม", "เวลาที่วางแผนเดินเครื่อง (นาที)"),
        ("downtime_min", "จำนวนเต็ม", "เวลาหยุด (นาที)"),
        ("good_qty", "จำนวนเต็ม", "จำนวนชิ้นดี"),
        ("reject_qty", "จำนวนเต็ม", "จำนวนชิ้นเสีย"),
    ],
    "breakdown.csv": [
        ("bd_id", "ข้อความ", "รหัสใบแจ้งเสีย"),
        ("date", "ข้อความ (YYYY-MM-DD)", "วันที่เสีย"),
        ("machine_id", "ข้อความ", "รหัสเครื่อง"),
        ("cause", "ข้อความ", "สาเหตุที่บันทึกไว้"),
        ("minutes", "จำนวนเต็ม", "เวลาที่ใช้ซ่อม (นาที)"),
        ("technician", "ข้อความ", "ช่างผู้ซ่อม"),
    ],
    "machine_log.txt": [
        ("(บรรทัดข้อความ)", "ข้อความ", "รูปแบบ: วันที่ เวลา รหัสเครื่อง เหตุการณ์ [รายละเอียด]"),
    ],
}


def preview(name: str, lines: int = 8) -> str:
    """ตัวอย่างไม่กี่บรรทัดแรกของไฟล์ ไว้โชว์ในหน้าเว็บ"""
    text = FILES[name]
    head = text.splitlines()[:lines]
    more = len(text.splitlines()) - len(head)
    return "\n".join(head) + (f"\n... (อีก {more:,} บรรทัด)" if more > 0 else "")


def row_count(name: str) -> int:
    n = len(FILES[name].strip().splitlines())
    return n - 1 if name.endswith(".csv") else n
