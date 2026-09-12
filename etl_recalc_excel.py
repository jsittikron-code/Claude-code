# -*- coding: utf-8 -*-
"""ขั้นสุดท้ายของงานอัปเดตประจำวัน — สั่ง Excel คำนวณสูตรแล้วเซฟ

ทำไมต้องมีขั้นนี้
    update_mos.py เขียนสูตรลงไฟล์เรื่อง 2 และ 3 ด้วย openpyxl ซึ่งเขียนสูตรได้
    แต่คำนวณไม่ได้ ค่าที่ฝังไว้เดิมจึงหายไป ถ้าไม่เปิด Excel แล้วเซฟสักครั้ง
    pandas กับ Power BI จะอ่านช่องสูตรได้เป็นค่าว่าง
    (คู่มือ 00_ETL_Pipeline/อ่านก่อน.md ข้อ 4)

สคริปต์นี้ทำขั้นตอนนั้นให้อัตโนมัติผ่าน Excel COM จึงไม่ต้องเปิดเองด้วยมือ

รันเดี่ยว ๆ ได้:  python etl_recalc_excel.py
"""

import os
import sys

DEPT_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา"
)

TARGETS = [
    os.path.join(DEPT_DIR, r"2.เรื่องMTBF-MTTR\รายละเอียด"
                           r"\MTBF-MTTR_ฐานข้อมูลหลัก_2569.xlsx"),
    os.path.join(DEPT_DIR, r"3.เรื่องOverall Equipment Effectiveness"
                           r"\OEE_ฐานข้อมูลหลัก_2569.xlsx"),
]

# ช่องที่ต้องมีค่าหลังคำนวณ ใช้ยืนยันว่าขั้นตอนนี้ได้ผลจริง
VERIFY = (r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx",
          "Report1", "หมวดหมู่เครื่อง")


def recalc(paths) -> bool:
    try:
        import win32com.client as win32
    except ImportError:
        print("  ไม่มีโมดูล pywin32 — ติดตั้งด้วย  pip install pywin32")
        print("  หรือเปิดไฟล์เรื่อง 2 และ 3 ด้วย Excel แล้วกด Save เองครั้งเดียว")
        return False

    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.AskToUpdateLinks = False
    ok = True
    try:
        for p in paths:
            if not os.path.exists(p):
                print(f"  ข้าม ไม่พบไฟล์: {os.path.basename(p)}")
                continue
            try:
                wb = xl.Workbooks.Open(p, UpdateLinks=0, ReadOnly=False)
                xl.CalculateFullRebuild()
                wb.Save()
                wb.Close(False)
                print(f"  คำนวณและเซฟแล้ว: {os.path.basename(p)}")
            except Exception as e:
                ok = False
                print(f"  ผิดพลาด {os.path.basename(p)}: {e}")
    finally:
        xl.Quit()
    return ok


def verify() -> bool:
    """เปิดไฟล์ด้วย pandas แล้วดูว่าช่องสูตรมีค่าจริงไหม"""
    import pandas as pd
    rel, sheet, col = VERIFY
    path = os.path.join(DEPT_DIR, rel)
    if not os.path.exists(path):
        return True
    df = pd.read_excel(path, sheet_name=sheet, engine="calamine")
    if col not in df.columns:
        print(f"  ตรวจไม่ได้ ไม่พบคอลัมน์ {col}")
        return True
    d = pd.to_datetime(df["Trans_date"], errors="coerce")
    last = df[d.dt.date == d.max().date()]
    blank = last[col].isna().sum()
    print(f"\n  ตรวจผล: คอลัมน์ '{col}' ของวันล่าสุด ว่าง {blank} จาก {len(last)} แถว")
    if blank:
        print("  ยังว่างอยู่ — ให้เปิดไฟล์เรื่อง 3 ด้วย Excel แล้วกด Save เองอีกครั้ง")
        return False
    return True


def main() -> int:
    print("สั่ง Excel คำนวณสูตรและเซฟ")
    if not recalc(TARGETS):
        return 1
    return 0 if verify() else 1


if __name__ == "__main__":
    sys.exit(main())
