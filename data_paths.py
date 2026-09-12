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

DEPT_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา"
)

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
# ตรวจสุขภาพแหล่งข้อมูล — python data_paths.py
# ---------------------------------------------------------------------------
DATASETS = {
    "Workcenter master": r"9.workcenter operation\Workcenter_ฐานข้อมูลหลัก_2569.xlsx",
    "Workcenter raw/": r"9.workcenter operation\raw",
    "Workcenter cache/": r"9.workcenter operation\cache",
    "MTBF-MTTR master": r"2.เรื่องMTBF-MTTR\รายละเอียด\MTBF-MTTR_ฐานข้อมูลหลัก_2569.xlsx",
    "OEE master": r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx",
    "ทะเบียนเครื่องจักร": r"5.งานทะเบียนเครื่องจักร\ทะเบียนเครื่องจักร_DataMaster_2569.xlsx",
    "บิลค่าไฟ 2569": (r"4.เรื่องการใช้ปริมาณไฟฟ้าภายในโรงงาน\งานระบบไฟฟ้าโรงงาน"
                      r"\งานระบบไฟฟ้า\Bill_33-5\2569\สรุปค่าไฟฟ้า 2569.xlsx"),
    "มิเตอร์ภายใน": (r"4.เรื่องการใช้ปริมาณไฟฟ้าภายในโรงงาน\งานระบบไฟฟ้าโรงงาน"
                     r"\ระบบไฟฟ้าภายใน\ETL"),
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

    print("\nผล: %s" % ("ครบทุกชุด" if ok else "มีชุดที่หายไป ดูรายการข้างบน"))
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if health() else 1)
