"""ชุดข้อมูลตัวอย่างสำหรับฝึก Power BI — โรงงานผลิตเฟอร์นิเจอร์ (star schema)
=============================================================================

ออกแบบให้ "เหมือนงานจริงของฝ่ายซ่อมบำรุงรักษา" คือมี OEE, downtime, เครื่องจักร,
กะทำงาน และยอดผลิต เพื่อให้แบบฝึกหัด DAX ที่ทำในแอปนี้ ย้ายไปใช้กับข้อมูลจริงได้ทันที

โครงสร้าง (star schema มาตรฐาน 1 fact + 4 dimension)

    Production (fact)  ── MachineID ──▶ Machine
                       ── ProductID ──▶ Product
                       ── Date      ──▶ Date
                       ── ShiftID   ──▶ Shift

ข้อมูลสร้างจาก seed คงที่ ⇒ ทุกเครื่อง ทุกครั้งที่เปิด ได้ตัวเลขชุดเดียวกันเสมอ
ทำให้เฉลยของแบบฝึกหัดตรงกันเสมอ และดาวน์โหลดไปเปิดใน Power BI Desktop แล้วได้เลขเท่ากัน
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd

from pbi.dax_engine import Model

SEED = 20260807
START = "2025-01-01"
END = "2026-06-30"

TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

MACHINES = [
    # MachineID, ชื่อ, สายการผลิต, ประเภท, เครื่องวิกฤต, กำลังผลิตมาตรฐาน (ชิ้น/นาที)
    ("M01", "เครื่องตัด CT-01",        "Line A", "ตัด",      True,  1.20),
    ("M02", "เครื่องตัด CT-02",        "Line A", "ตัด",      False, 1.10),
    ("M03", "เครื่องเจาะ CNC DL-01",   "Line A", "เจาะ",     True,  0.85),
    ("M04", "เครื่องเจาะ CNC DL-02",   "Line B", "เจาะ",     True,  0.90),
    ("M05", "เครื่องปิดขอบ EG-01",     "Line B", "ปิดขอบ",   True,  1.05),
    ("M06", "เครื่องปิดขอบ EG-02",     "Line B", "ปิดขอบ",   False, 0.95),
    ("M07", "บู้ทพ่นสี CO-01",         "Line C", "พ่นสี",    True,  0.60),
    ("M08", "บู้ทพ่นสี CO-02",         "Line C", "พ่นสี",    False, 0.55),
    ("M09", "เครื่องขัดเงา PO-01",     "Line C", "ขัดเงา",   False, 0.75),
    ("M10", "เครื่องปิดผิว LA-01",     "Line D", "ปิดผิว",   True,  1.00),
    ("M11", "เครื่อง Membrane PR-01",  "Line D", "ปิดผิว",   False, 0.70),
    ("M12", "เครื่องห่อโค้ง SF-01",    "Line D", "ห่อโค้ง",  False, 0.80),
]

PRODUCTS = [
    ("P01", "โต๊ะทำงาน 120",   "โต๊ะ",   3200.0),
    ("P02", "โต๊ะทำงาน 150",   "โต๊ะ",   3900.0),
    ("P03", "โต๊ะประชุม",      "โต๊ะ",   8500.0),
    ("P04", "ตู้เอกสาร 2 ชั้น", "ตู้",    4100.0),
    ("P05", "ตู้เอกสาร 4 ชั้น", "ตู้",    6300.0),
    ("P06", "ลิ้นชัก 3 ชั้น",   "ตู้",    2750.0),
    ("P07", "แผงกั้น 120",     "พาร์ทิชัน", 1850.0),
    ("P08", "แผงกั้น 160",     "พาร์ทิชัน", 2350.0),
]

SHIFTS = [("S1", "กะเช้า"), ("S2", "กะบ่าย")]

DOWN_REASONS = ["เครื่องเสีย", "รอวัสดุ", "ปรับตั้งเครื่อง", "ซ่อมบำรุงตามแผน",
                "ไฟฟ้าขัดข้อง", "รอคำสั่งผลิต"]


# ===========================================================================
# สร้างตารางมิติและตารางข้อเท็จจริง
# ===========================================================================
def _dim_machine() -> pd.DataFrame:
    return pd.DataFrame(MACHINES, columns=[
        "MachineID", "MachineName", "Line", "MachineType", "IsCritical", "StdRate"])


def _dim_product() -> pd.DataFrame:
    return pd.DataFrame(PRODUCTS, columns=[
        "ProductID", "ProductName", "Category", "UnitPrice"])


def _dim_shift() -> pd.DataFrame:
    return pd.DataFrame(SHIFTS, columns=["ShiftID", "ShiftName"])


def _dim_date() -> pd.DataFrame:
    d = pd.date_range(START, END, freq="D")
    df = pd.DataFrame({"Date": d})
    df["Year"] = d.year
    df["Quarter"] = "Q" + d.quarter.astype(str)
    df["MonthNo"] = d.month
    df["MonthName"] = [TH_MONTHS[m - 1] for m in d.month]
    df["MonthYear"] = [f"{TH_MONTHS[m - 1]} {(y + 543) % 100:02d}"
                       for m, y in zip(d.month, d.year)]
    df["YearMonth"] = d.year * 100 + d.month          # ใช้เรียงลำดับเดือน
    df["WeekdayName"] = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."] * 0 + [
        ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."][w] for w in d.weekday]
    df["IsWeekend"] = d.weekday >= 5
    return df


def _fact_production(dates: pd.DataFrame, machines: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    work = dates.loc[~dates["IsWeekend"], "Date"].to_numpy()

    n_m, n_s = len(machines), len(SHIFTS)
    n = len(work) * n_m * n_s

    date_col = np.repeat(work, n_m * n_s)
    machine_col = np.tile(np.repeat(machines["MachineID"].to_numpy(), n_s), len(work))
    shift_col = np.tile(np.array([s[0] for s in SHIFTS]), len(work) * n_m)

    std_rate = machines.set_index("MachineID")["StdRate"]
    rate = std_rate.reindex(machine_col).to_numpy()
    critical = machines.set_index("MachineID")["IsCritical"].reindex(machine_col).to_numpy()

    # เวลาที่วางแผนไม่เท่ากันทุกกะ — กะปกติ 8 ชม. บางกะสั้นลงเพราะแผนงานหรือหยุดตามแผน
    # (ต้องให้ต่างกันจริง ไม่งั้น "ค่าเฉลี่ยของสัดส่วน" กับ "สัดส่วนของยอดรวม"
    #  จะได้เลขเท่ากันพอดี ทำให้แบบฝึกหัดที่สอนความต่างของสองอย่างนี้ไม่มีความหมาย)
    planned = rng.choice([480.0, 420.0, 300.0], n, p=[0.72, 0.20, 0.08])
    # เครื่องวิกฤตเดินหนักกว่า และมีโอกาสเสียมากกว่าเล็กน้อย
    base_avail = np.where(critical, 0.88, 0.91)
    # ใส่แนวโน้มเสื่อมสภาพตามเวลา เพื่อให้ time intelligence มีเรื่องให้เล่า
    months = ((pd.DatetimeIndex(date_col).year - 2025) * 12
              + pd.DatetimeIndex(date_col).month - 1).to_numpy()
    trend = np.where(critical, -0.0035, -0.0012) * months
    avail = np.clip(base_avail + trend + rng.normal(0, 0.055, n), 0.45, 0.995)

    down = np.round(planned * (1 - avail), 0)

    # เหตุเสียฉุกเฉิน — ของจริงกระจายแบบหางยาว (นาน ๆ ครั้งแต่หนักมาก)
    # ถ้าไม่ใส่ ข้อมูลจะเรียบเกินไปจนแบบฝึกหัด "หาเครื่องที่ downtime สูงผิดปกติ" ไม่มีคำตอบ
    breakdown = rng.random(n) < np.where(critical, 0.055, 0.035)
    extra = np.where(breakdown, np.round(rng.uniform(45, 300, n), 0), 0.0)
    down = np.minimum(down + extra, planned - 30.0)     # เหลือเวลาเดินเครื่องอย่างน้อย 30 นาที

    run = planned - down

    perf = np.clip(rng.normal(0.93, 0.05, n), 0.55, 1.0)
    theoretical = run * rate
    total_qty = np.round(theoretical * perf, 0)

    quality = np.clip(rng.normal(0.975, 0.02, n), 0.80, 1.0)
    good = np.round(total_qty * quality, 0)
    reject = total_qty - good

    reason = rng.choice(DOWN_REASONS, n, p=[0.20, 0.22, 0.24, 0.16, 0.07, 0.11])
    reason = np.where(breakdown, "เครื่องเสีย", reason)
    reason = np.where(down <= 0, "ไม่มี", reason)

    # เลือกสินค้าตามสายการผลิต ให้มีความสัมพันธ์แบบมีเหตุผล
    line = machines.set_index("MachineID")["Line"].reindex(machine_col).to_numpy()
    prod_pool = {
        "Line A": ["P01", "P02", "P03"],
        "Line B": ["P04", "P05", "P06"],
        "Line C": ["P01", "P04", "P07"],
        "Line D": ["P07", "P08", "P02"],
    }
    product_col = np.array([
        prod_pool[ln][rng.integers(0, 3)] for ln in line
    ], dtype=object)

    df = pd.DataFrame({
        "ProdID": np.arange(1, n + 1),
        "Date": date_col,
        "MachineID": machine_col,
        "ProductID": product_col,
        "ShiftID": shift_col,
        "PlannedMin": planned,
        "RunMin": run,
        "DownMin": down,
        "DownReason": reason,
        "GoodQty": good,
        "RejectQty": reject,
    })
    return df


# ===========================================================================
# ประกอบเป็นชุดข้อมูลและโมเดลของเอนจิน
# ===========================================================================
def build_frames() -> dict[str, pd.DataFrame]:
    """คืนตารางทั้ง 5 แยกกัน (ใช้ดาวน์โหลดไปทำ star schema จริงใน Power BI)"""
    dim_date = _dim_date()
    dim_machine = _dim_machine()
    return {
        "Production": _fact_production(dim_date, dim_machine),
        "Machine": dim_machine,
        "Product": _dim_product(),
        "Date": dim_date,
        "Shift": _dim_shift(),
    }


def build_model(frames: dict[str, pd.DataFrame] | None = None) -> Model:
    """แบนตารางทั้งหมดเป็นตารางกว้างตารางเดียว แล้วห่อเป็น Model ของเอนจิน DAX"""
    f = frames or build_frames()
    wide = (f["Production"]
            .merge(f["Machine"], on="MachineID", how="left")
            .merge(f["Product"], on="ProductID", how="left")
            .merge(f["Date"], on="Date", how="left")
            .merge(f["Shift"], on="ShiftID", how="left"))

    owner = {}
    for tname, df in f.items():
        for c in df.columns:
            owner.setdefault(c, tname)
    # คีย์ที่ปรากฏทั้งใน fact และ dim ให้ถือว่าเป็นของ dim (ตามความหมายในโมเดลดาว)
    owner["MachineID"] = "Machine"
    owner["ProductID"] = "Product"
    owner["ShiftID"] = "Shift"
    owner["Date"] = "Date"

    base = pd.DataFrame({f"{owner[c]}[{c}]": wide[c] for c in wide.columns})
    tables = {t: [c for c in df.columns if owner[c] == t] for t, df in f.items()}
    # คอลัมน์คีย์ที่ย้ายไปอยู่ dim ต้องไม่หายไปจากรายการของ dim นั้น
    for t in tables:
        tables[t] = [c for c in dict.fromkeys(tables[t])]

    keys = {
        "Production": None,
        "Machine": "Machine[MachineID]",
        "Product": "Product[ProductID]",
        "Date": "Date[Date]",
        "Shift": "Shift[ShiftID]",
    }

    return Model(
        base=base,
        tables=tables,
        keys=keys,
        fact="Production",
        date_key="Date[Date]",
        measures=BUILTIN_MEASURES,
    )


# measure สำเร็จรูปที่ผู้เรียนอ้างถึงได้ด้วย [ชื่อ] ในสนามซ้อม
BUILTIN_MEASURES: dict[str, str] = {
    "Total Good": "SUM(Production[GoodQty])",
    "Total Reject": "SUM(Production[RejectQty])",
    "Total Qty": "SUM(Production[GoodQty]) + SUM(Production[RejectQty])",
    "Planned Minutes": "SUM(Production[PlannedMin])",
    "Run Minutes": "SUM(Production[RunMin])",
    "Down Minutes": "SUM(Production[DownMin])",
    "Availability": "DIVIDE(SUM(Production[RunMin]), SUM(Production[PlannedMin]))",
    "Quality": "DIVIDE(SUM(Production[GoodQty]), SUM(Production[GoodQty]) + SUM(Production[RejectQty]))",
    "Revenue": "SUMX(Production, Production[GoodQty] * Product[UnitPrice])",
}


SCHEMA_DOC = {
    "Production": [
        ("ProdID", "จำนวนเต็ม", "รหัสบรรทัดการผลิต (คีย์หลักของตาราง fact)"),
        ("Date", "วันที่", "วันที่ผลิต → เชื่อมกับ Date[Date]"),
        ("MachineID", "ข้อความ", "รหัสเครื่อง → เชื่อมกับ Machine[MachineID]"),
        ("ProductID", "ข้อความ", "รหัสสินค้า → เชื่อมกับ Product[ProductID]"),
        ("ShiftID", "ข้อความ", "รหัสกะ → เชื่อมกับ Shift[ShiftID]"),
        ("PlannedMin", "ทศนิยม", "เวลาที่วางแผนเดินเครื่อง (นาที)"),
        ("RunMin", "ทศนิยม", "เวลาเดินเครื่องจริง (นาที)"),
        ("DownMin", "ทศนิยม", "เวลาหยุด (นาที) = PlannedMin − RunMin"),
        ("DownReason", "ข้อความ", "สาเหตุการหยุดหลักของกะนั้น"),
        ("GoodQty", "ทศนิยม", "จำนวนชิ้นดี"),
        ("RejectQty", "ทศนิยม", "จำนวนชิ้นเสีย"),
    ],
    "Machine": [
        ("MachineID", "ข้อความ", "คีย์หลัก"),
        ("MachineName", "ข้อความ", "ชื่อเครื่องที่ใช้แสดงผล"),
        ("Line", "ข้อความ", "สายการผลิต Line A–D"),
        ("MachineType", "ข้อความ", "ประเภทงาน เช่น ตัด เจาะ พ่นสี"),
        ("IsCritical", "ตรรกะ", "เป็นเครื่องวิกฤตของสายหรือไม่"),
        ("StdRate", "ทศนิยม", "กำลังผลิตมาตรฐาน (ชิ้น/นาที) ใช้คำนวณ Performance"),
    ],
    "Product": [
        ("ProductID", "ข้อความ", "คีย์หลัก"),
        ("ProductName", "ข้อความ", "ชื่อสินค้า"),
        ("Category", "ข้อความ", "หมวดสินค้า"),
        ("UnitPrice", "ทศนิยม", "ราคาต่อหน่วย (บาท)"),
    ],
    "Date": [
        ("Date", "วันที่", "คีย์หลัก — ต้องทำเครื่องหมาย Mark as date table"),
        ("Year", "จำนวนเต็ม", "ปี ค.ศ."),
        ("Quarter", "ข้อความ", "Q1–Q4"),
        ("MonthNo", "จำนวนเต็ม", "เลขเดือน 1–12 (ใช้ Sort by column)"),
        ("MonthName", "ข้อความ", "ชื่อเดือนไทยแบบย่อ"),
        ("MonthYear", "ข้อความ", "เดือน+ปี พ.ศ. เช่น ม.ค. 68"),
        ("YearMonth", "จำนวนเต็ม", "เช่น 202501 ใช้เรียงลำดับ MonthYear"),
        ("WeekdayName", "ข้อความ", "ชื่อวันในสัปดาห์"),
        ("IsWeekend", "ตรรกะ", "เป็นวันหยุดสุดสัปดาห์หรือไม่"),
    ],
    "Shift": [
        ("ShiftID", "ข้อความ", "คีย์หลัก"),
        ("ShiftName", "ข้อความ", "ชื่อกะ"),
    ],
}


def to_excel_bytes(frames: dict[str, pd.DataFrame]) -> bytes:
    """รวมทุกตารางเป็นไฟล์ Excel เดียว (1 ชีตต่อ 1 ตาราง) สำหรับดาวน์โหลด"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in frames.items():
            out = df.copy()
            if "Date" in out.columns:
                out["Date"] = pd.to_datetime(out["Date"]).dt.date
            out.to_excel(xw, sheet_name=name, index=False)
    return buf.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")
