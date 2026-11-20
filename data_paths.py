# -*- coding: utf-8 -*-
"""ตัวหาที่อยู่ของไฟล์ข้อมูล — ใช้ร่วมกันทุกแดชบอร์ดในโฟลเดอร์นี้
================================================================

ปัญหาที่โมดูลนี้แก้
  เดิมทุกแดชบอร์ดเขียนเส้นทางโฟลเดอร์ไว้ตายตัวในโค้ด พอมีคนจัดระเบียบ
  OneDrive แล้วย้ายหรือเปลี่ยนชื่อโฟลเดอร์ แดชบอร์ดจะพังทันทีหลายตัวพร้อมกัน
  (เกิดขึ้นจริงเมื่อ 2026-09-12 ตอนย้ายไฟล์ใบแจ้งซ่อมจากโฟลเดอร์
  'ทดสอบแยกข้อมูลย้อนหลัง' ไปไว้ที่ '1.เรื่องประเภทงานใบงานแจ้งซ่อม')

วิธีแก้
  แทนที่จะจำว่า "โฟลเดอร์ชื่ออะไร" ให้จำว่า "ไฟล์ชื่ออะไร" แล้วไล่หาเอา
  ลองรายชื่อโฟลเดอร์ที่รู้จักก่อนเพราะเร็วที่สุด ถ้าไม่เจอค่อยไล่ดูโฟลเดอร์
  ชั้นเดียวใต้โฟลเดอร์ฝ่าย ย้ายไปไหนในระดับนั้นก็ยังหาเจอเอง

วิธีใช้
    import data_paths
    MT_DIR = data_paths.repair_dir()          # โฟลเดอร์ใบแจ้งซ่อม
    path   = data_paths.find("ชื่อไฟล์.xlsx")   # หาไฟล์ใด ๆ ในโฟลเดอร์ฝ่าย

ตรวจสุขภาพแหล่งข้อมูลทั้งหมด
    python data_paths.py
"""

from __future__ import annotations

import functools
import glob
import os
import socket

HERE = os.path.dirname(os.path.abspath(__file__))
# ไฟล์ตั้งค่าโฟลเดอร์ฝ่าย (บรรทัดเดียว = path เต็ม) — ใช้เมื่อเครื่องนั้น sync
# OneDrive/SharePoint มาไว้ที่อื่นจนหาเองไม่เจอ ไม่เข้า git เพราะแต่ละเครื่องต่างกัน
DEPT_DIR_FILE = os.path.join(HERE, "data_folder.txt")
DEPT_TAIL = os.path.join("Cue_IE_PD", "ฝ่ายซ่อมบำรุงรักษา")
# ถ้าเจ้าของแชร์มาแค่โฟลเดอร์ฝ่าย (ไม่ใช่ทั้ง Cue_IE_PD) ทางลัดจะอยู่ที่รากของ OneDrive เลย
# และ OneDrive ตั้งชื่อทางลัดบนดิสก์เป็น "<ชื่อเจ้าของ>'s files - <ชื่อโฟลเดอร์>"
# (เจอจริงที่คอมห้องช่าง 20 พ.ย. 2569: "Sitikron Jetjoho's files - ฝ่ายซ่อมบำรุงรักษา")
DEPT_TAILS = (DEPT_TAIL, "ฝ่ายซ่อมบำรุงรักษา", "* - ฝ่ายซ่อมบำรุงรักษา")


def _find_dept_dir() -> str:
    """หาโฟลเดอร์ฝ่ายบนเครื่องที่รันอยู่ — โค้ดชุดเดียวใช้ได้ทุกบัญชี Windows

    เดิมฝังโปรไฟล์ผู้ใช้คนเดียวไว้ตายตัว พอคนอื่น clone ไปรันบนเครื่องตัวเอง
    ทุกแดชบอร์ดหาข้อมูลไม่เจอ ลำดับการหา
      1. ตัวแปรสภาพแวดล้อม IE_DEPT_DIR
      2. ไฟล์ data_folder.txt ข้างโค้ด
      3. OneDrive ของบริษัทในโปรไฟล์ผู้ใช้ที่รันอยู่ (OneDrive - Modernform*)
    ไม่เจอเลยก็คืนตำแหน่งที่น่าจะเป็น ให้ข้อความ error ปลายทางบอก path ที่ไปหา
    """
    env = os.environ.get("IE_DEPT_DIR", "").strip().strip('"')
    if env:
        return env
    try:
        with open(DEPT_DIR_FILE, encoding="utf-8-sig") as f:
            txt = f.readline().strip().strip('"')
        if txt:
            return txt
    except OSError:
        pass
    roots = [os.environ.get("OneDriveCommercial", "")]
    roots += sorted(glob.glob(os.path.join(os.path.expanduser("~"),
                                           "OneDrive - Modernform*")))
    for r in roots:
        for tail in DEPT_TAILS:
            for d in sorted(glob.glob(os.path.join(glob.escape(r), tail))) if r else ():
                if os.path.isdir(d):
                    return d
    return os.path.join(os.path.expanduser("~"),
                        "OneDrive - Modernform Tower Co Ltd", DEPT_TAIL)


DEPT_DIR = _find_dept_dir()

# ไฟล์ตัวแทนของแต่ละชุดข้อมูล ใช้เป็นหมุดสำหรับหาโฟลเดอร์
ANCHOR_REPAIR = "รายงานซ่อมบำรุง_เครื่อง_2020-2026.xlsx"

# ชื่อโฟลเดอร์ที่เคยใช้ เรียงจากที่ใช้อยู่ปัจจุบันไปหาของเก่า
KNOWN_REPAIR_DIRS = (
    "1.เรื่องประเภทงานใบงานแจ้งซ่อม",
    "ทดสอบแยกข้อมูลย้อนหลัง",
)


class DataFolderNotFound(FileNotFoundError):
    """หาโฟลเดอร์ข้อมูลไม่เจอ — ข้อความบอกชัดว่าไปหาที่ไหนมาแล้วบ้าง"""


@functools.lru_cache(maxsize=32)
def locate_dir(anchor_file: str, candidates: tuple = (), label: str = "") -> str:
    """คืนโฟลเดอร์ที่มีไฟล์ชื่อ anchor_file อยู่จริง

    ลำดับการหา
      1. โฟลเดอร์ในรายชื่อ candidates (เร็วที่สุด ไม่ต้องสแกน)
      2. ไล่ดูทุกโฟลเดอร์ชั้นเดียวใต้ DEPT_DIR
    """
    for c in candidates:
        d = os.path.join(DEPT_DIR, c)
        if os.path.exists(os.path.join(d, anchor_file)):
            return d

    for d in sorted(glob.glob(os.path.join(DEPT_DIR, "*"))):
        if os.path.isdir(d) and os.path.exists(os.path.join(d, anchor_file)):
            return d

    raise DataFolderNotFound(
        f"หาโฟลเดอร์ข้อมูล{(' ' + label) if label else ''}ไม่เจอ\n\n"
        f"มองหาไฟล์: {anchor_file}\n"
        f"ในโฟลเดอร์: {DEPT_DIR}\n"
        f"ลองชื่อที่รู้จักแล้ว: {', '.join(candidates) if candidates else '(ไม่มี)'}\n"
        f"และไล่ดูทุกโฟลเดอร์ชั้นเดียวใต้โฟลเดอร์ฝ่ายแล้วก็ยังไม่เจอ\n\n"
        f"ถ้าเพิ่งย้ายไฟล์ ให้ย้ายกลับ หรือเพิ่มชื่อโฟลเดอร์ใหม่ใน data_paths.py"
    )


def repair_dir() -> str:
    """โฟลเดอร์ที่เก็บใบแจ้งซ่อม 6 หมวด + ไฟล์วิเคราะห์ปัญหา-สาเหตุ"""
    return locate_dir(ANCHOR_REPAIR, KNOWN_REPAIR_DIRS, "ใบแจ้งซ่อม")


def find(filename: str, candidates: tuple = ()) -> str:
    """หาไฟล์ใด ๆ ในโฟลเดอร์ฝ่าย → คืนเส้นทางเต็ม"""
    return os.path.join(locate_dir(filename, candidates, filename), filename)


# ---------------------------------------------------------------------------
# เครื่องอัปเดตข้อมูล — มีได้เครื่องเดียว
# ---------------------------------------------------------------------------
# ทำไมต้องมี: พอระบบรันได้สองเครื่อง (โน้ตบุ๊กเดิม + คอมห้องช่าง) ทั้งสองเครื่องมีปุ่มอัปเดต
# MOS/Solar ครบ และอ่าน-เขียนไฟล์ Excel/parquet ชุดเดียวกันบน OneDrive ถ้ากดอัปเดตจากสองเครื่อง
# OneDrive จะแตกไฟล์เป็นสำเนา conflict แล้วข้อมูลแยกเป็นสองชุดโดยไม่มีอะไรฟ้อง
# ไฟล์นี้อยู่ในโฟลเดอร์ข้อมูล (ไม่ใช่ข้างโค้ด) ทุกเครื่องจึงเห็นค่าเดียวกัน
# ย้ายเครื่องอัปเดต: ดับเบิลคลิก ตั้งเครื่องนี้เป็นเครื่องอัปเดต.bat บนเครื่องใหม่
ETL_MACHINE_FILE = os.path.join(DEPT_DIR, "00_ETL_Pipeline", "etl_machine.txt")


def this_machine() -> str:
    return (os.environ.get("COMPUTERNAME") or socket.gethostname()).strip().upper()


def etl_machine() -> str:
    """ชื่อเครื่องที่กำหนดให้เป็นเครื่องอัปเดต — "" ถ้ายังไม่เคยกำหนด หรืออ่านไฟล์ไม่ได้"""
    try:
        with open(ETL_MACHINE_FILE, encoding="utf-8-sig") as f:
            return f.readline().strip().upper()
    except OSError:
        return ""


def etl_block_reason() -> str:
    """"" ถ้าเครื่องนี้กดอัปเดตข้อมูลได้ ไม่งั้นคืนข้อความบอกว่าทำไมไม่ได้และต้องทำอะไร

    ยังไม่เคยกำหนดเครื่อง = อนุญาต (พฤติกรรมเดิม) ระบบจะไม่ล็อกใครออกเพราะไฟล์หาย
    """
    owner, me = etl_machine(), this_machine()
    if not owner or owner == me:
        return ""
    return (
        f"  *** เครื่องนี้ ({me}) ไม่ใช่เครื่องอัปเดตข้อมูล — เครื่องที่กำหนดไว้คือ {owner}\n"
        "      ไม่ได้ทำอะไรกับข้อมูล ระบบให้อัปเดตจากเครื่องเดียว กันไฟล์บน OneDrive ชนกัน\n"
        "      ถ้าย้ายงานอัปเดตมาเครื่องนี้แล้วจริง ๆ ให้ดับเบิลคลิก ตั้งเครื่องนี้เป็นเครื่องอัปเดต.bat"
    )


# ---------------------------------------------------------------------------
# ข้อมูล Workcenter — ออกมาจาก ETL ตัวเดียวของฝ่าย
# ---------------------------------------------------------------------------
ETL_DIR = os.path.join(DEPT_DIR, "00_ETL_Pipeline")
WC_PARQUET = os.path.join(ETL_DIR, "parquet", "workcenter_data.parquet")
WC_MASTER = os.path.join(DEPT_DIR, "9.workcenter operation",
                         "Workcenter_ฐานข้อมูลหลัก_2569.xlsx")


def workcenter_parquet() -> str:
    """ไฟล์ parquet ที่ 00_ETL_Pipeline/update_mos.py สร้างให้ทุกครั้งที่รัน

    นี่คือแหล่งข้อมูล Workcenter เพียงแหล่งเดียวที่แดชบอร์ดควรอ่าน
    กฎการแปลงข้อมูลทั้งหมดอยู่ในบล็อก CONFIG ของ update_mos.py ที่เดียว
    ห้ามเขียนกฎซ้ำที่นี่หรือในแดชบอร์ด (ดู 00_ETL_Pipeline/อ่านก่อน.md)
    """
    if not os.path.exists(WC_PARQUET):
        raise DataFolderNotFound(
            "ไม่พบไฟล์ข้อมูล Workcenter\n\n"
            f"มองหา: {WC_PARQUET}\n\n"
            "ไฟล์นี้ถูกสร้างโดย ETL ของฝ่าย รันด้วยคำสั่ง\n"
            "    python \"00_ETL_Pipeline\\update_mos.py\" --check\n"
            "    python \"00_ETL_Pipeline\\update_mos.py\"\n\n"
            "โดยต้องวางไฟล์ export จาก MOS ไว้ที่\n"
            "    00_ข้อมูลดิบ_MOS\\<ปี พ.ศ.-เดือน-วัน>\\"
        )
    return WC_PARQUET


def workcenter_signature() -> tuple:
    """ลายเซ็นข้อมูล Workcenter — เปลี่ยนเมื่อ ETL รันใหม่ ใช้เป็นกุญแจแคช"""
    out = []
    for p in (WC_PARQUET, WC_MASTER):
        out.append((os.path.basename(p),
                    round(os.path.getmtime(p), 3) if os.path.exists(p) else 0))
    return tuple(out)


# ---------------------------------------------------------------------------
# ข้อมูล Solar Inverter — ออกมาจาก solar_etl.py (ปุ่ม อัปเดต Solar.bat)
# ---------------------------------------------------------------------------
# โฟลเดอร์โครงการอยู่ลึก 2 ชั้นใต้โฟลเดอร์ฝ่าย จึงใช้ locate_dir() ตรง ๆ ไม่ได้
# หาด้วยชื่อโฟลเดอร์ก่อน ถ้าถูกย้ายค่อยไล่หาโฟลเดอร์ชื่อลงท้ายด้วย "Solar" ใต้ชั้นที่สอง
SOLAR_RAW_NAME = "01_ข้อมูลดิบ_Solar Cell"
KNOWN_SOLAR_DIRS = (
    r"0.1 Project_IE\1.โครงการบริหารพลังงาน Solar",
)


@functools.lru_cache(maxsize=1)
def solar_project_dir() -> str:
    """โฟลเดอร์โครงการบริหารพลังงาน Solar (มี 01_ข้อมูลดิบ_Solar Cell อยู่ข้างใน)"""
    for c in KNOWN_SOLAR_DIRS:
        d = os.path.join(DEPT_DIR, c)
        if os.path.isdir(os.path.join(d, SOLAR_RAW_NAME)):
            return d
    for d in sorted(glob.glob(os.path.join(DEPT_DIR, "*", "*Solar*"))):
        if os.path.isdir(os.path.join(d, SOLAR_RAW_NAME)):
            return d
    raise DataFolderNotFound(
        "หาโฟลเดอร์โครงการ Solar ไม่เจอ\n\n"
        f"มองหาโฟลเดอร์ย่อย: {SOLAR_RAW_NAME}\n"
        f"ใต้: {DEPT_DIR}\\<โฟลเดอร์ใด ๆ>\\<โฟลเดอร์ชื่อมี Solar>\n"
        f"ลองชื่อที่รู้จักแล้ว: {', '.join(KNOWN_SOLAR_DIRS)}\n\n"
        "ถ้าเพิ่งย้ายโฟลเดอร์ ให้เพิ่มชื่อใหม่ใน KNOWN_SOLAR_DIRS ของ data_paths.py"
    )


def solar_raw_dir() -> str:
    """โฟลเดอร์ที่วางไฟล์ EVE export: <นี่>\\<ปี พ.ศ.-เดือน-วัน>_EVE_Export\\*.xlsx"""
    return os.path.join(solar_project_dir(), SOLAR_RAW_NAME)


def solar_parquet_dir() -> str:
    """โฟลเดอร์ parquet ที่ solar_etl.py เขียน — แดชบอร์ดอ่านจากที่นี่ที่เดียว"""
    return os.path.join(solar_raw_dir(), "parquet")


SOLAR_PARQUET_FILES = ("solar_readings.parquet", "solar_daily.parquet",
                       "solar_profile15.parquet")


def solar_signature() -> tuple:
    """ลายเซ็นข้อมูล Solar — เปลี่ยนเมื่อ ETL รันใหม่ ใช้เป็นกุญแจแคชและตัวจับรีเฟรช"""
    try:
        d = solar_parquet_dir()
    except DataFolderNotFound:
        return ()
    return tuple(
        (f, round(os.path.getmtime(os.path.join(d, f)), 3)
            if os.path.exists(os.path.join(d, f)) else 0)
        for f in SOLAR_PARQUET_FILES
    )


# ---------------------------------------------------------------------------
# ตรวจสุขภาพแหล่งข้อมูล — python data_paths.py
# ---------------------------------------------------------------------------
DATASETS = {
    "Workcenter master": r"9.workcenter operation\Workcenter_ฐานข้อมูลหลัก_2569.xlsx",
    "parquet (ETL สร้าง)": r"00_ETL_Pipeline\parquet\workcenter_data.parquet",
    "โฟลเดอร์ข้อมูลดิบ MOS": r"00_ข้อมูลดิบ_MOS",
    "สคริปต์ ETL": r"00_ETL_Pipeline\update_mos.py",
    "MTBF-MTTR master": r"2.เรื่องMTBF-MTTR\รายละเอียด\MTBF-MTTR_ฐานข้อมูลหลัก_2569.xlsx",
    "OEE master": r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx",
    "ทะเบียนเครื่องจักร": r"5.งานทะเบียนเครื่องจักร\ทะเบียนเครื่องจักร_DataMaster_2569.xlsx",
    "บิลค่าไฟ 2569": (r"4.เรื่องการใช้ปริมาณไฟฟ้าภายในโรงงาน\งานระบบไฟฟ้าโรงงาน"
                      r"\งานระบบไฟฟ้า\Bill_33-5\2569\สรุปค่าไฟฟ้า 2569.xlsx"),
    "มิเตอร์ภายใน": (r"4.เรื่องการใช้ปริมาณไฟฟ้าภายในโรงงาน\งานระบบไฟฟ้าโรงงาน"
                     r"\ระบบไฟฟ้าภายใน\ETL"),
    "Solar ข้อมูลดิบ EVE": os.path.join(KNOWN_SOLAR_DIRS[0], SOLAR_RAW_NAME),
    "Solar parquet (ETL สร้าง)": os.path.join(KNOWN_SOLAR_DIRS[0], SOLAR_RAW_NAME,
                                             "parquet", "solar_daily.parquet"),
}

REPAIR_FILES = (
    "รายงานซ่อมบำรุง_เครื่อง_2020-2026.xlsx",
    "รายงานซ่อมบำรุง_ซ่อมสร้าง_2020-2026.xlsx",
    "รายงานซ่อมบำรุง_ลับคม_2020-2026.xlsx",
    "รายงานซ่อมบำรุง_ซ่อมรถยนต์_2020-2026.xlsx",
    "รายงานซ่อมบำรุง_เครื่องมือเล็ก_2020-2026.xlsx",
    "รายงานซ่อมบำรุง_ดัดแปลง_2020-2026.xlsx",
    "วิเคราะห์ปัญหา-สาเหตุ_รายเครื่อง.xlsx",
)


def health() -> bool:
    """ตรวจว่าแหล่งข้อมูลทุกชุดยังอยู่ครบไหม"""
    import datetime

    def line(name, path):
        if os.path.exists(path):
            t = datetime.datetime.fromtimestamp(os.path.getmtime(path))
            age = (datetime.datetime.now() - t).days
            flag = "  <-- เก่า %d วัน" % age if age > 14 else ""
            print("  OK   %-28s %s%s" % (name[:28], t.strftime("%Y-%m-%d %H:%M"), flag))
            return True
        print("  หาย  %-28s %s" % (name[:28], path))
        return False

    print("ตรวจแหล่งข้อมูลทั้งหมด")
    print("โฟลเดอร์ฝ่าย: %s" % DEPT_DIR)
    print("-" * 64)
    ok = os.path.isdir(DEPT_DIR)
    if not ok:
        print("  หาย  โฟลเดอร์ฝ่าย — OneDrive อาจยังไม่ซิงก์")
        return False

    for name, rel in DATASETS.items():
        ok &= line(name, os.path.join(DEPT_DIR, rel))

    try:
        rd = repair_dir()
        print("\nโฟลเดอร์ใบแจ้งซ่อม: %s" % os.path.basename(rd))
        for f in REPAIR_FILES:
            ok &= line(f.replace("รายงานซ่อมบำรุง_", "").replace("_2020-2026.xlsx", ""),
                       os.path.join(rd, f))
    except DataFolderNotFound as e:
        print("\n%s" % e)
        ok = False

    # รอบ ETL ล่าสุด — บอกว่าวางไฟล์ดิบถึงวันไหนแล้ว
    raw_root = os.path.join(DEPT_DIR, "00_ข้อมูลดิบ_MOS")
    if os.path.isdir(raw_root):
        days = sorted(d for d in os.listdir(raw_root)
                      if os.path.isdir(os.path.join(raw_root, d)))
        print("\nโฟลเดอร์ข้อมูลดิบที่วางไว้แล้ว %d รอบ" % len(days))
        for d in days[-3:]:
            n = len(os.listdir(os.path.join(raw_root, d)))
            print("  %-14s %d ไฟล์" % (d, n))

    print("\nผล: %s" % ("ครบทุกชุด" if ok else "มีชุดที่หายไป ดูรายการข้างบน"))
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if health() else 1)
