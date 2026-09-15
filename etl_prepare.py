# -*- coding: utf-8 -*-
"""ขั้นที่ 1 ของงานอัปเดตประจำวัน — ย้ายไฟล์ export เข้าโฟลเดอร์ลงวันที่

หาไฟล์ r-jobtran-mc และ r-jobtran-oee ในโฟลเดอร์ Downloads แล้วย้ายเข้า
00_ข้อมูลดิบ_MOS\\<ปี พ.ศ.-เดือน-วัน>\\ ตามที่ update_mos.py คาดหวัง

กฎความปลอดภัย 3 ข้อ (เขียนขึ้นหลังทดสอบแล้วพลาดจริงทั้งสามแบบ)
  1. วันที่ของโฟลเดอร์อ่านจาก "ชื่อไฟล์" ไม่ใช่นาฬิกาเครื่อง และแปลงเป็น พ.ศ.
     ด้วยการบวก 543 ไม่ใช่เติม "25" ข้างหน้า (เติม 25 จะได้ 2526 ผิดไป 43 ปี)
  2. ไฟล์ mc กับ oee ต้องเป็นของ "วันเดียวกัน" เท่านั้น ไม่งั้นหยุด
     เพราะใน Downloads มี export เก่าค้างอยู่นับร้อยไฟล์ ถ้าหยิบตัวใหม่สุด
     ของแต่ละชนิดมาจับคู่กันเฉย ๆ จะได้ใบงานของวันหนึ่งคู่กับ OEE ของอีกวัน
  3. ไฟล์ต้องใหม่พอ (ภายใน MAX_AGE_DAYS วัน) ไม่งั้นหยุดและเตือน
     กันกรณีลืม export แล้วเผลอเอาไฟล์เก่ามาอัปเดตซ้ำ

รันเดี่ยว ๆ ได้:  python etl_prepare.py
"""

import datetime as dt
import glob
import os
import re
import shutil
import sys

DEPT_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา"
)
RAW_ROOT = os.path.join(DEPT_DIR, "00_ข้อมูลดิบ_MOS")
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")

PATTERNS = {
    "ใบงานรายเครื่อง": "r-jobtran-mc*.xls*",
    "OEE": "r-jobtran-oee*.xls*",
}
STAMP = re.compile(r"_(\d{2})(\d{2})(\d{2})(\d{6})")   # _YYMMDDhhmmss
# ยอมรับแค่ export ของวันนี้หรือเมื่อวาน — เผื่อกรณีดึงตอนเย็นแล้วมารันเช้าวันรุ่งขึ้น
# ตั้งหลวมกว่านี้ไม่ได้ เพราะใน Downloads มี export เก่าค้างอยู่เป็นร้อยไฟล์
# ถ้าไฟล์ของวันนี้ถูกใช้ไปแล้ว สคริปต์จะถอยไปหยิบไฟล์เก่ามาใช้แทนโดยไม่มีใครรู้
MAX_AGE_DAYS = 1

# รหัสผลลัพธ์พิเศษ: ไม่มีไฟล์ให้ย้าย แต่ไม่ถือว่าผิดพลาด
#
# ทำไมต้องแยกรหัสนี้ออกมา
#   สคริปต์นี้ "ย้าย" ไฟล์ออกจาก Downloads พอย้ายเสร็จ Downloads ก็ว่าง
#   ถ้ารอบถัดไปถือว่า "ไม่มีไฟล์" เป็นความผิดพลาดแล้วหยุดทั้งกระบวนการ
#   ไฟล์ที่ย้ายไปแล้วแต่ยังไม่ได้โหลดเข้าฐานจะค้างอยู่ตลอดไป กดปุ่มกี่ครั้งก็ไม่มีอะไรเกิดขึ้น
#   (เกิดขึ้นจริง 14-15 ก.ย. 2569 ข้อมูลค้างสองวันโดยที่หน้าจอไม่บอกอะไร)
#
#   ตัวเรียกต้องเดินต่อไปขั้นถัดไปเสมอเมื่อได้รหัสนี้ เพราะ ETL ตัดแถวซ้ำอยู่แล้ว
#   รันซ้ำกับข้อมูลเดิมไม่เสียหาย แต่ไม่รันเลยคือข้อมูลหาย
NOTHING_TO_MOVE = 2


def file_date(path: str):
    """วันที่จากชื่อไฟล์ → (date ค.ศ., ชื่อโฟลเดอร์ พ.ศ.) หรือ None"""
    m = STAMP.search(os.path.basename(path))
    if not m:
        return None
    yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        d = dt.date(2000 + yy, mm, dd)
    except ValueError:
        return None
    return d, f"{d.year + 543}-{d.month:02d}-{d.day:02d}"


def scan():
    """จัดกลุ่มไฟล์ใน Downloads ตามวันที่ในชื่อไฟล์"""
    by_day = {}
    for label, pat in PATTERNS.items():
        for f in glob.glob(os.path.join(DOWNLOADS, pat)):
            info = file_date(f)
            if not info:
                continue
            d, _ = info
            by_day.setdefault(d, {}).setdefault(label, []).append(f)
    return by_day


def main() -> int:
    by_day = scan()
    if not by_day:
        print("  ไม่พบไฟล์ export จาก MOS ในโฟลเดอร์ Downloads เลย")
        print(f"  ดึง export จาก MOS มาไว้ที่ {DOWNLOADS} ก่อน")
        return NOTHING_TO_MOVE

    today = dt.date.today()
    newest_day = max(by_day)
    age = (today - newest_day).days
    group = by_day[newest_day]
    _, folder = file_date(group[next(iter(group))][0])

    print(f"  ไฟล์ใหม่ที่สุดใน Downloads เป็นของวันที่ {folder} (อายุ {age} วัน)")

    if age > MAX_AGE_DAYS:
        print(f"\n  ไม่มีไฟล์ใหม่ให้ย้าย (ไฟล์ใน Downloads เก่าเกิน {MAX_AGE_DAYS} วัน)")
        print("  ถ้าเพิ่งดึง export มา ให้ตรวจว่าลงในโฟลเดอร์ Downloads จริงไหม")
        return NOTHING_TO_MOVE

    missing = [k for k in PATTERNS if k not in group]
    if "ใบงานรายเครื่อง" in missing:
        print("\n  ไม่มีไฟล์ใบงานรายเครื่อง (r-jobtran-mc) ของวันนี้ใน Downloads")
        return NOTHING_TO_MOVE
    if missing:
        print(f"\n  วันที่ {folder} มีแต่ใบงาน ขาดไฟล์ {', '.join(missing)}")
        print("  ต้องมีครบทั้งสองไฟล์และเป็นของวันเดียวกัน จึงจะย้ายได้")
        print("  ดึง export ที่ขาดจาก MOS ก่อนแล้วรันใหม่")
        return NOTHING_TO_MOVE

    dest = os.path.join(RAW_ROOT, folder)

    # ถ้าไฟล์ชุดนี้ถูกย้ายเข้าไปแล้ว ให้บอกแล้วผ่านไป ไม่ต้องหาไฟล์เก่ามาแทน
    already = os.path.isdir(dest) and all(
        os.path.exists(os.path.join(
            dest, os.path.basename(max(group[k], key=lambda p: os.path.basename(p)))))
        for k in PATTERNS)
    if already:
        print(f"\n  ไฟล์ชุดนี้อยู่ในโฟลเดอร์ {folder} แล้ว ไม่ต้องย้ายซ้ำ")
        return NOTHING_TO_MOVE

    os.makedirs(dest, exist_ok=True)
    print(f"  โฟลเดอร์ปลายทาง: {folder}\n")

    moved = skipped = 0
    for label in PATTERNS:
        # ถ้ามีหลายไฟล์ของชนิดเดียวกันในวันเดียวกัน เอาตัว export ล่าสุด
        src = max(group[label], key=lambda p: os.path.basename(p))
        tgt = os.path.join(dest, os.path.basename(src))
        if os.path.exists(tgt):
            print(f"  มีอยู่แล้ว ข้าม: {os.path.basename(src)}")
            skipped += 1
            continue
        shutil.move(src, tgt)
        print(f"  ย้ายแล้ว: {os.path.basename(src)}")
        moved += 1

    print(f"\n  ย้าย {moved} ไฟล์ ข้าม {skipped} ไฟล์ เข้าโฟลเดอร์ {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
