# -*- coding: utf-8 -*-
"""ตัวอ่านข้อมูลดิบจากระบบ MOS — แทนการทำ ETL ด้วยมือ
================================================================

แนวคิด
  ไฟล์ที่ export จาก MOS ถูกวางไว้ในโฟลเดอร์ raw แล้วไม่แก้อีกเลย
  โมดูลนี้อ่านไฟล์ทั้งหมด ตัดแถวซ้ำ เติมคอลัมน์คำนวณ แล้วเก็บผลไว้ใน
  ไฟล์ parquet หนึ่งไฟล์ (cache) ซึ่งแดชบอร์ดอ่านได้ในเวลาไม่ถึงวินาที

  cache จะถูกสร้างใหม่ก็ต่อเมื่อโฟลเดอร์ raw เปลี่ยนเท่านั้น
  (ดูจากชื่อไฟล์ + เวลาแก้ไขของทุกไฟล์รวมกัน)

วิธีใช้ในแดชบอร์ด
    import mos_loader
    df = mos_loader.load_workcenter()

ตรวจความถูกต้องเทียบกับไฟล์ master เดิม
    python mos_loader.py --check
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import tempfile

import pandas as pd

# ---------------------------------------------------------------------------
# ที่อยู่ไฟล์
# ---------------------------------------------------------------------------
DEPT_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา"
)
WC_DIR = os.path.join(DEPT_DIR, "9.workcenter operation")
RAW_DIR = os.path.join(WC_DIR, "raw")
CACHE_DIR = os.path.join(WC_DIR, "cache")
CACHE_PATH = os.path.join(CACHE_DIR, "workcenter.parquet")
SIG_PATH = os.path.join(CACHE_DIR, "workcenter.sig.json")
# ฐานประวัติที่แปลงจาก master แล้ว — แยกไฟล์เพราะไม่ต้องสร้างใหม่ทุกครั้ง
SEED_CACHE = os.path.join(CACHE_DIR, "seed_history.parquet")
SEED_SIG = os.path.join(CACHE_DIR, "seed_history.sig.json")

# ไฟล์ master เดิม — ใช้เป็น "ฐานประวัติ" เท่านั้น เพราะไฟล์ดิบย้อนหลัง
# ก่อนเดือน ส.ค. 2569 เป็น export เฉพาะกิจที่ไม่ครบวัน จึงต่อประวัติไม่ได้
SEED_PATH = os.path.join(WC_DIR, "Workcenter_ฐานข้อมูลหลัก_2569.xlsx")

# ตารางหมวดหมู่เครื่อง อยู่ในไฟล์ OEE (หัวตารางอยู่แถวที่ 4)
OEE_PATH = os.path.join(
    DEPT_DIR, r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx"
)

RAW_GLOB = "r-jobtran-mc*.xls*"

# ---------------------------------------------------------------------------
# ค่าคงที่ของธุรกิจ
# ---------------------------------------------------------------------------
# รหัส Job สามตัวนี้เท่านั้นที่หมายถึงงานหยุดเครื่อง ต้องเทียบ "รหัสเต็ม"
# ห้ามดูแค่ตัวอักษรนำหน้า เพราะงานผลิตจริงจำนวนมากก็ขึ้นต้นด้วย P เช่น P000444865
# (เคยลองกฎดูตัวหน้าแล้วจัดงานผลิตผิดเป็นงานหยุดเครื่อง 918 แถว จาก 3,918 แถว)
PSEUDO_JOB = {
    "P000000001": "P-เปลี่ยนอุปกรณ์",
    "B000000001": "B-แจ้งเตือนBM",
    "BP00000001": "BP-ช่างซ่อมBM",
}
JOB_PROD = "PROD-งานผลิต"

# คีย์ที่ใช้ระบุว่าแถวไหนคือแถวเดียวกัน — ไฟล์ export คร่อมวันกัน
# แถวเดิมจึงโผล่ซ้ำในหลายไฟล์ ต้องตัดให้เหลือตัวเดียว
DEDUP_KEY = ["Machine", "Job", "Item", "Start", "End"]

TH_WEEKDAY = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

# คอลัมน์ที่แดชบอร์ดคาดหวัง — ต้องเหมือนชีต Data ของไฟล์ master เป๊ะ
MASTER_COLUMNS = [
    "Machine", "หมวดเครื่อง", "พนักงาน", "Job", "หมวดJob", "Item", "Description",
    "Qty", "Start", "End", "Duration(นาที)", "วันที่", "เดือน", "วันในสัปดาห์",
    "ชั่วโมงเริ่ม", "Reason", "แหล่งข้อมูล",
]


# ---------------------------------------------------------------------------
# อ่านไฟล์ดิบหนึ่งไฟล์
# ---------------------------------------------------------------------------
def _find_header_row(path: str, scan_rows: int = 6) -> int:
    """หาว่าแถวไหนคือหัวตาราง

    MOS ส่งออกไม่เหมือนกันทุกครั้ง บางไฟล์มีแบนเนอร์ 2 แถวก่อนหัวตาราง
    (หัวอยู่แถว index 2) บางไฟล์ไม่มีเลย (หัวอยู่แถว index 0)
    จึงต้องมองหาแถวที่มีคำว่า Machine แทนการกำหนดตายตัว
    """
    probe = pd.read_excel(path, sheet_name="Report2", header=None,
                          nrows=scan_rows, engine="calamine")
    for i in range(len(probe)):
        row = [str(x).strip() for x in probe.iloc[i].tolist()]
        if "Machine" in row and "Job" in row:
            return i
    raise ValueError(f"หาหัวตารางไม่เจอใน {os.path.basename(path)} "
                     f"(มองหาแถวที่มีทั้ง Machine และ Job ใน {scan_rows} แถวแรก)")


def read_raw_file(path: str) -> pd.DataFrame:
    """อ่านไฟล์ export หนึ่งไฟล์ → ตารางดิบ พร้อมคอลัมน์บอกที่มา"""
    header = _find_header_row(path)
    df = pd.read_excel(path, sheet_name="Report2", header=header, engine="calamine")
    df.columns = [str(c).strip() for c in df.columns]
    df["แหล่งข้อมูล"] = os.path.basename(path)
    return df


# ---------------------------------------------------------------------------
# ตารางหมวดหมู่เครื่อง
# ---------------------------------------------------------------------------
def _machine_category() -> dict:
    """รหัสเครื่อง → หมวดหมู่ อ่านจากชีต 'หมวดหมู่เครื่อง' ของไฟล์ OEE

    เครื่องที่ไม่มีในตารางนี้จะถูกจัดเป็น 'อื่นๆ' ตามที่ ETL เดิมทำ
    """
    try:
        cat = pd.read_excel(OEE_PATH, sheet_name="หมวดหมู่เครื่อง", header=3,
                            engine="calamine")
    except Exception:
        return {}
    if "รหัสเครื่อง" not in cat.columns or "หมวดหมู่" not in cat.columns:
        return {}
    cat = cat.dropna(subset=["รหัสเครื่อง"])
    return dict(zip(cat["รหัสเครื่อง"].astype(str).str.strip(),
                    cat["หมวดหมู่"].astype(str).str.strip()))


# ---------------------------------------------------------------------------
# เติมคอลัมน์คำนวณ
# ---------------------------------------------------------------------------
def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """เติมคอลัมน์ที่ ETL เดิมเคยเติมให้ด้วยมือ"""
    df = df.rename(columns={"Name": "พนักงาน"})

    df["Machine"] = df["Machine"].astype(str).str.strip()
    df["Job"] = df["Job"].astype(str).str.strip()
    df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
    df["End"] = pd.to_datetime(df["End"], errors="coerce")
    df = df.dropna(subset=["Start", "End"])

    # หมวดJob — เทียบรหัสเต็ม ไม่ใช่ตัวอักษรนำหน้า (ดูหมายเหตุที่ PSEUDO_JOB)
    df["หมวดJob"] = df["Job"].map(PSEUDO_JOB).fillna(JOB_PROD)

    # ระยะเวลา — มีบางแถวที่เวลาจบมาก่อนเวลาเริ่ม (พบ 5 แถวในข้อมูลจริง)
    # ETL เดิมบังคับให้เป็น 0 จึงทำเหมือนกันเพื่อให้ตัวเลขตรงกัน
    mins = (df["End"] - df["Start"]).dt.total_seconds() / 60
    df["Duration(นาที)"] = mins.clip(lower=0)

    df["วันที่"] = df["Start"].dt.date
    df["เดือน"] = df["Start"].dt.month
    df["วันในสัปดาห์"] = df["Start"].dt.weekday.map(lambda i: TH_WEEKDAY[i])
    df["ชั่วโมงเริ่ม"] = df["Start"].dt.hour

    lut = _machine_category()
    df["หมวดเครื่อง"] = df["Machine"].map(lut).fillna("อื่นๆ")

    df["Qty"] = pd.to_numeric(df.get("Qty"), errors="coerce").fillna(0)
    if "Reason" not in df.columns:
        df["Reason"] = pd.NA

    return df


# ---------------------------------------------------------------------------
# ประกอบร่าง
# ---------------------------------------------------------------------------
def _normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    """บังคับชนิดข้อมูลให้เหมือนกันทุกแถว ก่อนเขียนลง parquet

    จำเป็นเพราะฐานประวัติจาก master เก็บ Start/End/วันที่ เป็น "ข้อความ"
    แต่แถวที่อ่านจากไฟล์ดิบเป็นชนิดวันที่จริง พอเอามาต่อกันคอลัมน์เดียว
    จะมีสองชนิดปนกัน ซึ่ง parquet ไม่รับ

    สำคัญ: ฟังก์ชันนี้ "ไม่คำนวณค่าใหม่" — แปลงเฉพาะชนิดข้อมูลเท่านั้น
    เคยลองคำนวณ Duration ใหม่ทับของเดิมแล้วพบว่าตัวเลขบนหน้าจอขยับ เพราะ
    ETL เดิมปัดทศนิยม 2 ตำแหน่งกับข้อมูลเก่า 412,384 แถว แต่เก็บเต็มความ
    ละเอียดใน 1,842 แถวล่าสุด การคำนวณใหม่จึงไม่มีทางตรงกับของเดิมทั้งหมด
    แถวเก่าต้องเก็บค่าที่ ETL เดิมทำไว้ไม่แตะต้อง ส่วนแถวใหม่จากไฟล์ดิบ
    ให้ add_derived เป็นคนคำนวณ
    """
    df = df.copy()
    df["Start"] = pd.to_datetime(df["Start"], errors="coerce")
    df["End"] = pd.to_datetime(df["End"], errors="coerce")
    df = df.dropna(subset=["Start", "End"])

    # วันที่ ต้องแปลงชนิดเพราะ master เก็บเป็นข้อความ แต่ฝั่งไฟล์ดิบเป็นวันที่จริง
    # parquet ไม่รับสองชนิดในคอลัมน์เดียว (คอลัมน์นี้ไม่มีแดชบอร์ดตัวไหนอ่าน)
    if "วันที่" in df.columns:
        df["วันที่"] = pd.to_datetime(df["วันที่"], errors="coerce")

    for c, typ in (("เดือน", "Int16"), ("ชั่วโมงเริ่ม", "Int8")):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(typ)
    for c in ("Duration(นาที)", "Qty"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")

    for c in ("Machine", "หมวดเครื่อง", "พนักงาน", "Job", "หมวดJob", "Item",
              "Description", "Reason", "แหล่งข้อมูล", "วันในสัปดาห์", "ช่วงกะ"):
        if c in df.columns:
            df[c] = df[c].astype("string")
    return df


def _raw_files() -> list:
    return sorted(glob.glob(os.path.join(RAW_DIR, RAW_GLOB)))


def signature() -> list:
    """ลายเซ็นโฟลเดอร์ raw — เปลี่ยนเมื่อมีไฟล์เพิ่ม ลบ หรือถูกแก้"""
    return [[os.path.basename(f), round(os.path.getmtime(f), 3),
             os.path.getsize(f)] for f in _raw_files()]


def load_seed(verbose: bool = False) -> pd.DataFrame | None:
    """ฐานประวัติจากไฟล์ master — แปลงเป็น parquet เก็บไว้ครั้งเดียว

    ไฟล์ master เป็น xlsx ขนาด 75 MB อ่านครั้งละ 15 วินาที ถ้าอ่านใหม่ทุกครั้ง
    ที่มีไฟล์ดิบเข้ามา การวางไฟล์ประจำวันจะหน่วง 18 วินาทีทุกวัน
    จึงแปลงเป็น parquet เก็บไว้ อ่านรอบหลังเหลือไม่ถึงวินาที

    ประวัติชุดนี้หยุดนิ่งแล้ว ไม่มีอะไรมาแก้ ข้อมูลใหม่มาจากโฟลเดอร์ raw อย่างเดียว
    ถ้าไฟล์ master ถูกแก้ (เช่นยังทำ ETL เดิมคู่ขนานอยู่) ระบบจะสร้าง seed ใหม่เอง
    """
    if not os.path.exists(SEED_PATH):
        return None
    mtime = round(os.path.getmtime(SEED_PATH), 3)
    if os.path.exists(SEED_CACHE) and os.path.exists(SEED_SIG):
        try:
            with open(SEED_SIG, encoding="utf-8") as fh:
                if json.load(fh) == mtime:
                    if verbose:
                        print("ฐานประวัติ: ใช้ parquet ที่แปลงไว้แล้ว", flush=True)
                    return pd.read_parquet(SEED_CACHE)
        except Exception:
            pass
    if verbose:
        print("ฐานประวัติ: แปลง master เป็น parquet (ทำครั้งเดียว) ...", flush=True)
    base = pd.read_excel(SEED_PATH, sheet_name="Data", engine="calamine")
    base = _normalize_types(base)
    _save_atomic(base, SEED_CACHE)
    with open(SEED_SIG, "w", encoding="utf-8") as fh:
        json.dump(mtime, fh)
    if verbose:
        print("  ฐานประวัติ %d แถว" % len(base), flush=True)
    return base


def build(seed: bool = True, verbose: bool = True) -> pd.DataFrame:
    """อ่านไฟล์ดิบทั้งหมด (+ ฐานประวัติ) → ตารางเดียวที่ตัดซ้ำแล้ว"""
    frames, skipped = [], []

    if seed:
        base = load_seed(verbose=verbose)
        if base is not None:
            frames.append(base)

    for path in _raw_files():
        try:
            frames.append(add_derived(read_raw_file(path)))
        except Exception as e:
            skipped.append((os.path.basename(path), f"{type(e).__name__}: {e}"))

    if not frames:
        raise FileNotFoundError(
            f"ไม่พบไฟล์ข้อมูลเลย\nโฟลเดอร์ดิบ: {RAW_DIR}\nรูปแบบที่มองหา: {RAW_GLOB}")

    df = pd.concat(frames, ignore_index=True)
    before = len(df)
    # keep="first" — ฐานประวัติถูกต่อไว้เป็นก้อนแรก จึงชนะเสมอเมื่อแถวซ้ำกับไฟล์ดิบ
    # เหตุผล: ETL เดิมปัดทศนิยม Duration ไว้ ถ้าปล่อยให้ค่าที่คำนวณใหม่มาแทน
    # ตัวเลขประวัติบนหน้าจอจะขยับทั้งที่ข้อมูลเป็นแถวเดียวกัน
    # แถวของวันใหม่ที่ไม่มีในประวัติยังใช้ค่าที่คำนวณจากไฟล์ดิบตามปกติ
    df = df.drop_duplicates(subset=DEDUP_KEY, keep="first")
    df = _normalize_types(df)

    for c in MASTER_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[MASTER_COLUMNS + [c for c in df.columns if c not in MASTER_COLUMNS]]
    df = df.sort_values(["Machine", "Start"]).reset_index(drop=True)

    if verbose:
        print("รวม %d แถว ตัดซ้ำเหลือ %d แถว (ซ้ำ %d)" % (before, len(df), before - len(df)),
              flush=True)
        for name, why in skipped:
            print("  ข้ามไฟล์ %s — %s" % (name, why), flush=True)
    return df


def _save_atomic(df: pd.DataFrame, path: str) -> None:
    """เขียนไฟล์ชั่วคราวก่อนแล้วค่อยเปลี่ยนชื่อทับ

    ป้องกันกรณี OneDrive กำลัง sync แล้วมีคนอ่านไฟล์ครึ่ง ๆ กลาง ๆ
    การเปลี่ยนชื่อทับเป็นการกระทำที่สำเร็จทั้งหมดหรือไม่สำเร็จเลย
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".parquet", dir=os.path.dirname(path))
    os.close(fd)
    try:
        df.to_parquet(tmp, index=False)
        shutil.move(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_workcenter(force: bool = False) -> pd.DataFrame:
    """ตัวที่แดชบอร์ดเรียกใช้ — คืนตารางหน้าตาเดียวกับชีต Data ของ master เดิม"""
    sig = signature()
    if not force and os.path.exists(CACHE_PATH) and os.path.exists(SIG_PATH):
        try:
            with open(SIG_PATH, encoding="utf-8") as fh:
                if json.load(fh) == sig:
                    return pd.read_parquet(CACHE_PATH)
        except Exception:
            pass  # ลายเซ็นอ่านไม่ได้ — สร้างใหม่ให้ปลอดภัยไว้ก่อน

    df = build(verbose=False)
    _save_atomic(df, CACHE_PATH)
    with open(SIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(sig, fh, ensure_ascii=False)
    return df


def missing_days(df: pd.DataFrame | None = None) -> list:
    """วันทำงานที่ไม่มีข้อมูลเลย — ใช้เตือนบนหน้าจอว่าลืมวางไฟล์วันไหน

    นับเฉพาะช่วง 30 วันล่าสุด และไม่นับวันอาทิตย์ (โรงงานเดิน 6 วัน)
    """
    if df is None:
        df = load_workcenter()
    d = pd.to_datetime(df["Start"]).dt.normalize()
    have = set(d.dt.date)
    last = d.max().date()
    span = pd.date_range(last - pd.Timedelta(days=29), last, freq="D").date
    return [x for x in span if x not in have and x.weekday() != 6]


# ---------------------------------------------------------------------------
# โหมดตรวจสอบ — python mos_loader.py --check
# ---------------------------------------------------------------------------
def _classify_day(loader_n: int, master_n: int) -> str:
    """จัดประเภทความต่างรายวัน

    ไฟล์ export ของ MOS ไม่ได้ตัดตามวันที่ Start ตรง ๆ — งานที่เริ่มก่อน
    ช่วง export แต่ปิดในช่วงนั้นก็ติดมาด้วยไม่กี่แถว วันขอบจึงมีแถวหลุดมา
    เล็กน้อยโดยที่ไฟล์ไม่ได้ครอบคลุมทั้งวัน ต้องแยกออกจาก "ข้อมูลผิด"
    """
    if loader_n == master_n:
        return "ตรง"
    if loader_n > master_n:
        return "loader เกิน"                    # กรณีเดียวที่ถือว่าผิดจริง
    if master_n and loader_n / master_n < 0.5:
        return "ไฟล์ไม่ครอบคลุมวันนี้"
    return "master มีแถวซ้ำ"


def check() -> bool:
    """เทียบผลของ loader กับไฟล์ master เดิม

    เกณฑ์ผ่าน 3 ข้อ
      1. ไม่มีแถวที่ loader มีแต่ master ไม่มี  (ไม่สร้างข้อมูลปลอม)
      2. ทุกวันที่ไฟล์ดิบครอบคลุมจริง ต้องตรงเป๊ะ
      3. วันที่ master มากกว่า ต้องพิสูจน์ได้ว่าส่วนเกินคือแถวซ้ำของ master เอง
    """
    print("=" * 66)
    print("ตรวจ loader เทียบกับ master เดิม")
    print("=" * 66)

    new = build(seed=False, verbose=True)          # เฉพาะไฟล์ดิบ ไม่เอาฐานประวัติ
    old = pd.read_excel(SEED_PATH, sheet_name="Data", engine="calamine")
    old["Start"] = pd.to_datetime(old["Start"], errors="coerce")
    old = old.dropna(subset=["Start"])

    new["_d"] = pd.to_datetime(new["Start"]).dt.date
    old["_d"] = old["Start"].dt.date
    days = sorted(set(new["_d"]) & set(old["_d"]))

    a_day = new.groupby("_d").size()
    b_day = old.groupby("_d").size()
    rows = []
    for d in days:
        ln, mn = int(a_day.get(d, 0)), int(b_day.get(d, 0))
        rows.append((d, ln, mn, mn - ln, _classify_day(ln, mn)))
    tab = pd.DataFrame(rows, columns=["วันที่", "loader", "master", "ต่าง", "ผล"])
    print("\nเทียบรายวัน %d วัน (%s ถึง %s)" % (len(days), days[0], days[-1]))
    print(tab.to_string(index=False))

    n_ok = (tab["ผล"] == "ตรง").sum()
    n_over = (tab["ผล"] == "loader เกิน").sum()
    n_gap = (tab["ผล"] == "ไฟล์ไม่ครอบคลุมวันนี้").sum()
    n_dup = (tab["ผล"] == "master มีแถวซ้ำ").sum()

    # --- เกณฑ์ 1: ห้ามมีแถวที่ loader สร้างขึ้นเอง ---
    covered = tab.loc[tab["ผล"] != "ไฟล์ไม่ครอบคลุมวันนี้", "วันที่"]
    a = new[new["_d"].isin(set(covered))]
    b = old[old["_d"].isin(set(covered))]
    ka = set(map(tuple, a[DEDUP_KEY].astype(str).values))
    kb = set(map(tuple, b[DEDUP_KEY].astype(str).values))
    only_new = ka - kb

    # --- เกณฑ์ 3: ส่วนเกินของ master ต้องเป็นแถวซ้ำจริง ---
    dup_days = tab.loc[tab["ผล"] == "master มีแถวซ้ำ", "วันที่"]
    dup_proved, dup_detail = True, []
    for d in dup_days:
        sub = old[old["_d"] == d]
        n_dupe_rows = len(sub) - len(sub.drop_duplicates(subset=DEDUP_KEY))
        excess = int(b_day[d] - a_day[d])
        dup_detail.append((d, excess, n_dupe_rows))
        dup_proved &= n_dupe_rows == excess

    print("\nสรุป")
    print("  ตรงเป๊ะ                    %d วัน" % n_ok)
    print("  ไฟล์ไม่ครอบคลุม (ข้ามได้)   %d วัน" % n_gap)
    print("  master มีแถวซ้ำ            %d วัน" % n_dup)
    for d, excess, dupes in dup_detail:
        print("      %s  master เกิน %d แถว / เป็นแถวซ้ำใน master %d แถว  %s" % (
            d, excess, dupes, "อธิบายได้" if excess == dupes else "อธิบายไม่ได้"))
    print("  loader มีแถวเกิน           %d วัน" % n_over)
    print("  แถวที่ loader สร้างเอง      %d แถว" % len(only_new))

    ok = (n_over == 0) and (not only_new) and dup_proved
    print("\nผล: %s" % ("ผ่านทั้ง 3 เกณฑ์" if ok else "ไม่ผ่าน — ดูรายละเอียดข้างบน"))
    return ok


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        raise SystemExit(0 if check() else 1)
    df = load_workcenter(force="--force" in sys.argv)
    print("โหลดได้ %d แถว %d คอลัมน์" % (len(df), df.shape[1]))
    print("ช่วงข้อมูล: %s ถึง %s" % (df["Start"].min(), df["Start"].max()))
    miss = missing_days(df)
    print("วันทำงานที่ขาดใน 30 วันล่าสุด: %s" % (miss if miss else "ไม่มี"))
