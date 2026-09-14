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
import subprocess
import sys
import time


def _excel_pids() -> set:
    """หมายเลขโปรเซส EXCEL.EXE ที่กำลังรันอยู่ตอนนี้"""
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=20)
        return {int(ln.split('","')[1]) for ln in r.stdout.splitlines()
                if ln.startswith('"EXCEL.EXE"')}
    except Exception:
        return set()

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

    before = _excel_pids()
    xl = win32.DispatchEx("Excel.Application")
    ours = _excel_pids() - before          # โปรเซส Excel ที่เราเป็นคนเปิด
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.AskToUpdateLinks = False
    ok = True
    try:
        for p in paths:
            if not os.path.exists(p):
                print(f"  ข้าม ไม่พบไฟล์: {os.path.basename(p)}")
                continue
            # Excel ปฏิเสธคำสั่งได้ถ้ามันกำลังยุ่ง หรือไฟล์เพิ่งถูกอ่านค้างอยู่
            # (com_error 'Call was rejected by callee') รอแล้วลองใหม่มักผ่าน
            for attempt in range(1, 4):
                try:
                    wb = xl.Workbooks.Open(p, UpdateLinks=0, ReadOnly=False)
                    xl.CalculateFullRebuild()
                    wb.Save()
                    wb.Close(False)
                    print(f"  คำนวณและเซฟแล้ว: {os.path.basename(p)}")
                    break
                except Exception as e:
                    if attempt == 3:
                        ok = False
                        print(f"  ผิดพลาด {os.path.basename(p)}: {e}")
                    else:
                        print(f"  ลองใหม่ครั้งที่ {attempt + 1} ({os.path.basename(p)})")
                        time.sleep(5)
    finally:
        # ต้องปิด Excel ให้ได้เสมอ ถ้าเหลือค้างไว้ มันจะถือไฟล์แล้วทำให้
        # รอบถัดไปสั่งงานไม่ได้ และแดชบอร์ดอ่านช่องสูตรได้เป็นค่าว่าง
        # (เจอจริงเมื่อ 2026-09-14 มี Excel ค้างจากรอบก่อนแล้วรอบใหม่ล้มทั้งหมด)
        try:
            xl.Quit()
        except Exception:
            pass
        del xl
        time.sleep(2)
        stuck = ours & _excel_pids()
        for pid in stuck:
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=20)
                print(f"  ปิด Excel ที่ค้างอยู่ (pid {pid})")
            except Exception:
                pass
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


def export_parquet() -> bool:
    """แปลงชีต Report1 ของไฟล์ OEE เป็น parquet ให้แดชบอร์ดอ่าน

    ทำไมต้องทำตรงนี้ ไม่ใช่ใน update_mos.py
        ตอน ETL เขียนเสร็จ คอลัมน์สูตรยังไม่ถูกคำนวณ ถ้า export ตอนนั้นจะได้ค่าว่าง
        ต้องรอ Excel คำนวณและเซฟก่อน (ฟังก์ชัน recalc ข้างบน) แล้วค่อย export

    ทำไมต้องมี parquet
        ไฟล์ OEE ถูกอ่านโดยแดชบอร์ด 7 จาก 9 ตัว ถ้าไฟล์ถูกเปิดค้างใน Excel
        หรือ OneDrive กำลัง sync จอจะเสียพร้อมกันหมด อ่านจาก parquet แทนตัดปัญหานี้
        และเร็วกว่าด้วย
    """
    import pandas as pd

    src = os.path.join(DEPT_DIR, VERIFY[0])
    out_dir = os.path.join(DEPT_DIR, "00_ETL_Pipeline", "parquet")
    out = os.path.join(out_dir, "oee_report1.parquet")
    if not os.path.exists(src):
        print("  ข้าม export parquet: ไม่พบไฟล์ OEE")
        return True
    try:
        df = pd.read_excel(src, sheet_name="Report1", engine="calamine")

        # MOS เก็บ Trans_date ปนกัน บางแถวเป็นวันที่จริง บางแถวเป็นข้อความ
        # parquet รับคอลัมน์ที่มีสองชนิดไม่ได้ ต้องแปลงให้เป็นชนิดเดียวก่อน
        df["Trans_date"] = pd.to_datetime(df["Trans_date"], errors="coerce")
        for c in df.columns:
            if df[c].dtype == "object":
                num = pd.to_numeric(df[c], errors="coerce")
                # คอลัมน์ที่แปลงเป็นตัวเลขได้เกือบหมด ถือว่าเป็นตัวเลขที่ปนข้อความ
                df[c] = num if num.notna().sum() >= df[c].notna().sum() * 0.9 \
                    else df[c].astype("string")

        os.makedirs(out_dir, exist_ok=True)
        tmp = out + ".tmp"
        df.to_parquet(tmp, index=False)
        os.replace(tmp, out)      # เปลี่ยนชื่อทับทีเดียว กันไฟล์ครึ่ง ๆ ตอน OneDrive sync
        print("  export parquet: %d แถว %d คอลัมน์ (%.1f MB)"
              % (len(df), df.shape[1], os.path.getsize(out) / 1e6))
        return True
    except Exception as e:
        print(f"  export parquet ไม่สำเร็จ: {e}")
        print("  ไม่กระทบการอัปเดต แดชบอร์ดจะถอยไปอ่านไฟล์ Excel เอง")
        return True   # ไม่ถือเป็นความล้มเหลวของทั้งงาน


def main() -> int:
    print("สั่ง Excel คำนวณสูตรและเซฟ")
    # ถึง recalc จะล้ม ก็ยังต้องตรวจและ export ต่อ เพราะบางไฟล์อาจสำเร็จไปแล้ว
    # และ parquet ที่ได้ยังดีกว่าไม่มีเลย
    ok_recalc = recalc(TARGETS)
    ok_verify = verify()
    export_parquet()
    if not ok_recalc:
        print("\n  สั่ง Excel ไม่สำเร็จบางไฟล์")
        print("  ถ้าตัวเลขบนแดชบอร์ดหาย ให้เปิดไฟล์เรื่อง 2 และ 3 ด้วย Excel")
        print("  แล้วกด Save 1 ครั้ง หรือรัน  python etl_recalc_excel.py  ใหม่อีกรอบ")
    return 0 if (ok_recalc and ok_verify) else 1


if __name__ == "__main__":
    sys.exit(main())
