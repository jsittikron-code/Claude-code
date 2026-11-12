# -*- coding: utf-8 -*-
"""ลบแถว OEE ที่ซ้ำคีย์ (เครื่อง, วัน) ออกจากชีต Report1

ปัญหา
    update_mos.py ตัดแถวซ้ำเฉพาะฝั่ง Workcenter (บรรทัด 640) แต่ฝั่ง OEE
    ต่อแถวใหม่ท้ายชีตโดยไม่เทียบกับของเดิม รันสองรอบในวันเดียวจึงได้แถวซ้ำ
    ซึ่งจะเกิดทุกครั้งที่อัปเดตเช้าแล้วอัปเดตบ่ายอีกรอบ

    เจอเมื่อ 2026-09-17 วันที่ 12 ก.ย. มี 132 แถวจาก 50 เครื่อง (ควรมี 50)
    ทำให้ยอดรวมของวันนั้นพองเป็นสองเท่า

เก็บแถวไหนไว้
    เก็บแถวที่ "เวลาทำงานจริง/วัน" มากที่สุดของแต่ละคีย์
    เพราะ MOS ส่งออกเป็นภาพรวมของวัน ณ เวลาที่ดึง ยิ่งดึงสายยิ่งสะสมมาก
    ไม่ใช้วิธีเก็บแถวสุดท้าย เพราะ export ของวันถัดไปอาจครอบคลุมวันก่อนแค่บางส่วน

    ตรวจกับวันข้างเคียงแล้ว: เก็บแถวมากสุดได้ 10,537 นาที ใกล้เคียง
    11 ก.ย. 10,264 นาที และ 15 ก.ย. 11,775 นาที ส่วนเก็บแถวสุดท้ายได้ 4,110 นาที
    ซึ่งต่ำผิดปกติ

รัน:  python fix_oee_duplicates.py          ดูว่าจะลบอะไรบ้าง ไม่แก้ไฟล์
      python fix_oee_duplicates.py --apply  แก้จริง (สำรองไฟล์ก่อนเสมอ)
"""

import datetime as dt
import os
import shutil
import sys

import openpyxl
import pandas as pd

import data_paths

DEPT_DIR = data_paths.DEPT_DIR
OEE = os.path.join(DEPT_DIR, r"3.เรื่องOverall Equipment Effectiveness"
                             r"\OEE_ฐานข้อมูลหลัก_2569.xlsx")
KEEP_BY = "เวลาทำงานจริง/วัน"


def find_duplicates():
    """คืนรายการแถว Excel ที่ต้องลบ (เลขแถวจริงในชีต)"""
    df = pd.read_excel(OEE, sheet_name="Report1", engine="calamine")
    df = df.assign(
        _row=range(2, len(df) + 2),                       # แถว 1 เป็นหัวตาราง
        _d=pd.to_datetime(df["Trans_date"], errors="coerce").dt.date,
        _keep=pd.to_numeric(df[KEEP_BY], errors="coerce").fillna(-1),
    )
    df = df[df["_d"].notna()]
    dup = df[df.duplicated(subset=["MC", "_d"], keep=False)]
    if dup.empty:
        return [], df

    drop_rows = []
    for (mc, d), g in dup.groupby(["MC", "_d"]):
        keep = g.loc[g["_keep"].idxmax(), "_row"]
        drop_rows += [r for r in g["_row"] if r != keep]
    return sorted(drop_rows), df


def main() -> int:
    apply = "--apply" in sys.argv
    drop_rows, df = find_duplicates()

    if not drop_rows:
        print("  ไม่พบแถวซ้ำ ไม่ต้องแก้อะไร")
        return 0

    dup = df[df.duplicated(subset=["MC", "_d"], keep=False)]
    print("  พบแถวซ้ำ %d แถว จาก %d คู่คีย์" % (len(dup), dup.groupby(["MC", "_d"]).ngroups))
    print("  กระจายตามวัน:")
    for d, n in dup.groupby("_d").size().items():
        print("    %s  %d แถว (ควรมี %d)" % (d, n, dup[dup["_d"] == d]["MC"].nunique()))
    print("  จะลบ %d แถว เหลือแถวที่ %s มากที่สุดของแต่ละคีย์" % (len(drop_rows), KEEP_BY))

    if not apply:
        print("\n  โหมดดูอย่างเดียว ไม่ได้แก้ไฟล์")
        print("  ถ้าจะแก้จริง สั่ง  python fix_oee_duplicates.py --apply")
        return 0

    bdir = os.path.join(DEPT_DIR, "_backup_ROLLBACK", dt.datetime.now().strftime("%Y%m%d"))
    os.makedirs(bdir, exist_ok=True)
    bak = os.path.join(bdir, os.path.basename(OEE))
    if not os.path.exists(bak):
        shutil.copy2(OEE, bak)
        print("\n  สำรองไฟล์แล้ว: %s" % bak)

    wb = openpyxl.load_workbook(OEE)
    ws = wb["Report1"]
    for r in sorted(drop_rows, reverse=True):     # ลบจากล่างขึ้นบน เลขแถวจะได้ไม่เลื่อน
        ws.delete_rows(r)
    wb.save(OEE)
    wb.close()
    print("  ลบแล้ว %d แถว" % len(drop_rows))

    left, _ = find_duplicates()
    print("  ตรวจซ้ำ: เหลือแถวซ้ำ %d แถว" % len(left))
    print("\n  ขั้นต่อไป ต้องให้ Excel คำนวณสูตรใหม่แล้ว export parquet")
    print("  สั่ง  python etl_recalc_excel.py")
    return 0 if not left else 1


if __name__ == "__main__":
    sys.exit(main())
