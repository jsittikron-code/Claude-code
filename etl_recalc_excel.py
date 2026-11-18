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

import data_paths


def _excel_pids() -> set:
    """หมายเลขโปรเซส EXCEL.EXE ที่กำลังรันอยู่ตอนนี้"""
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=20)
        return {int(ln.split('","')[1]) for ln in r.stdout.splitlines()
                if ln.startswith('"EXCEL.EXE"')}
    except Exception:
        return set()

DEPT_DIR = data_paths.DEPT_DIR

RETRIES = 6          # จำนวนครั้งที่ลองเปิดไฟล์ด้วย Excel ก่อนยอมแพ้ (ดูเหตุผลใน recalc)
RECALC_CYCLES = 3    # ทำรอบ เปิด-คำนวณ-เซฟ-ตรวจไฟล์ ซ้ำได้กี่รอบ ถ้าไฟล์ที่เซฟยังว่าง (ดู main)

# ทำ OEE ก่อน เพราะแดชบอร์ด 7 ใน 9 ตัวอ่านไฟล์นี้ ถ้ามีอะไรล้มให้ล้มที่ไฟล์สำคัญน้อยกว่า
TARGETS = [
    os.path.join(DEPT_DIR, r"3.เรื่องOverall Equipment Effectiveness"
                           r"\OEE_ฐานข้อมูลหลัก_2569.xlsx"),
    os.path.join(DEPT_DIR, r"2.เรื่องMTBF-MTTR\รายละเอียด"
                           r"\MTBF-MTTR_ฐานข้อมูลหลัก_2569.xlsx"),
]

# ช่องที่ต้องมีค่าหลังคำนวณ ใช้ยืนยันว่าขั้นตอนนี้ได้ผลจริง
VERIFY = (r"3.เรื่องOverall Equipment Effectiveness\OEE_ฐานข้อมูลหลัก_2569.xlsx",
          "Report1", "หมวดหมู่เครื่อง")


def _canary_filled(wb, sheet: str, col_name: str):
    """อ่านช่องสูตรแถวสุดท้ายของชีตผ่าน Excel โดยตรง — มีค่าแล้วหรือยัง

    ใช้เช็กก่อนเซฟ เพราะ CalculationState บอกว่าเสร็จได้ทั้งที่ค่ายังไม่ลงช่อง
    คืน True = มีค่า, False = ยังว่าง, None = ตรวจไม่ได้ (บอกเหตุผลออกจอ)

    ทำไม "ตรวจไม่ได้" ต้องเป็น None ไม่ใช่ True
        เดิมคืน True ทุกกรณีที่อ่านไม่ได้ แปลว่าถ้าใครเปลี่ยนชื่อคอลัมน์หรือย้ายหัวตาราง
        ตัวกันนี้จะหายไปเงียบ ๆ แล้วเรากลับไปสู่สภาพก่อน 1 ต.ค. 2569 โดยไม่รู้ตัว
    """
    try:
        ws = wb.Worksheets(sheet)
    except Exception:
        print(f"  ตรวจช่องสูตรไม่ได้: ไม่พบชีต '{sheet}'")
        return None
    try:
        col = None
        for c in range(1, 200):
            v = ws.Cells(1, c).Value
            if v is None or v == "":
                break
            if str(v).strip() == col_name:
                col = c
                break
        if col is None:
            print(f"  ตรวจช่องสูตรไม่ได้: ไม่พบคอลัมน์ '{col_name}' ในแถวที่ 1 ของ '{sheet}'")
            return None
        last = ws.Cells(ws.Rows.Count, 1).End(-4162).Row      # xlUp
        if last < 2:
            print(f"  ตรวจช่องสูตรไม่ได้: ชีต '{sheet}' ไม่มีแถวข้อมูล")
            return None
        v = ws.Cells(last, col).Value
        return v is not None and str(v).strip() != ""
    except Exception as e:
        print(f"  ตรวจช่องสูตรไม่ได้: {e}")
        return None


def _saved_canary(path: str, sheet: str, col_name: str):
    """อ่านช่องสูตรแถวสุดท้ายจาก "ไฟล์บนดิสก์" (ค่าที่ Excel ฝังไว้) → True/False/None"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet]
        hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        if col_name not in hdr:
            return None
        ci = hdr.index(col_name)
        last = None
        for row in ws.iter_rows(min_row=max(ws.max_row - 5, 2), values_only=True):
            if row[0] is not None:
                last = row
        wb.close()
        if last is None:
            return None
        v = last[ci]
        return v is not None and str(v).strip() != ""
    except Exception:
        return None


def recalc(paths) -> bool:
    try:
        import win32com.client as win32
    except ImportError:
        print("  ไม่มีโมดูล pywin32 — ติดตั้งด้วย  pip install pywin32")
        print("  หรือเปิดไฟล์เรื่อง 2 และ 3 ด้วย Excel แล้วกด Save เองครั้งเดียว")
        return False

    ok = True
    for p in paths:
        if not os.path.exists(p):
            print(f"  ข้าม ไม่พบไฟล์: {os.path.basename(p)}")
            continue
        # ให้ Excel ทำงานกับ "สำเนาในเครื่อง" ไม่ใช่ไฟล์ใน OneDrive โดยตรง
        #
        # 18 พ.ย. 2569: Excel เปิดไฟล์ MTBF ใน OneDrive ไม่ได้ 4 ครั้ง พอครั้งที่ 5 เปิดได้
        # กลับได้รุ่นเก่าของวันที่ 5 พ.ย. (Office ดึงจากแคชของ OneDrive แทนไฟล์ที่ขั้น 3
        # เพิ่งเขียน) แล้วเซฟทับ แถวเหตุการณ์ 5–17 พ.ย. หายทั้งหมด โดย log ยังบอกว่าเรียบร้อย
        # สำเนาที่อยู่นอก OneDrive ไม่มีแคชหรือรุ่นบนคลาวด์ให้ Excel สับสน
        # และก่อนวางกลับ ตรวจว่าทุกชีตมีแถวไม่น้อยกว่าก่อนเปิด ถ้าน้อยลง = ไม่วางกลับ
        #
        # เปิด Excel ใหม่คนละอินสแตนซ์ต่อไฟล์ด้วย (5 พ.ย. 2569: อินสแตนซ์ที่เพิ่งเซฟไฟล์
        # หนึ่งยุ่งนานกว่า 75 วิ ตอบ 'Call was rejected by callee' ทำให้เปิดไฟล์ถัดไปไม่ได้)
        if not _recalc_via_local_copy(win32, p):
            ok = False
    return ok


def _sheet_rows(path: str) -> dict:
    """จำนวนแถวของทุกชีต (อ่านจากไฟล์บนดิสก์) ใช้จับว่าไฟล์ถูกเซฟทับด้วยรุ่นเก่า"""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        return {ws.title: (ws.max_row or 0) for ws in wb.worksheets}
    finally:
        wb.close()


def _recalc_via_local_copy(win32, p: str) -> bool:
    import shutil
    import tempfile
    name = os.path.basename(p)
    work_dir = os.path.join(tempfile.gettempdir(), "etl_recalc_excel")
    os.makedirs(work_dir, exist_ok=True)
    work = os.path.join(work_dir, name)
    try:
        before = _sheet_rows(p)
        shutil.copy2(p, work)
    except Exception as e:
        print(f"  *** คัดลอกไฟล์มาทำงานไม่ได้ ({name}): {e}")
        return False

    ok = _recalc_one(win32, work)

    # ไฟล์ที่ Excel เซฟต้องมีแถวครบทุกชีตเท่ากับก่อนเปิด (สูตรเพิ่มได้ แถวห้ามหาย)
    try:
        after = _sheet_rows(work)
    except Exception as e:
        print(f"  *** อ่านไฟล์ที่ Excel เซฟไม่ได้ ({name}): {e} — ไม่วางกลับ ไฟล์เดิมใน OneDrive ไม่ถูกแตะ")
        return False
    lost = {s: (before[s], after.get(s, 0)) for s in before if after.get(s, 0) < before[s]}
    if lost:
        print(f"  *** ไฟล์ที่ Excel เซฟมีแถวน้อยกว่าก่อนเปิด — ไม่วางกลับ ไฟล์เดิมใน OneDrive ไม่ถูกแตะ ({name})")
        for s, (b, a) in lost.items():
            print(f"      ชีต {s}: ก่อน {b:,} แถว · หลัง {a:,} แถว")
        return False
    if not ok:
        # Excel ล้มหรือช่องสูตรยังว่าง ไฟล์ใน OneDrive ยังเป็นของที่ขั้น 3 เขียนไว้ครบ
        return False

    # วางกลับ: คัดลอกเป็นไฟล์ชั่วคราวข้างไฟล์จริงก่อน แล้วสลับทีเดียว
    tmp = p + ".recalc.tmp"
    for attempt in range(10):
        try:
            shutil.copy2(work, tmp)
            os.replace(tmp, p)
            return True
        except PermissionError:
            time.sleep(3)
        except Exception as e:
            print(f"  *** วางไฟล์กลับไม่สำเร็จ ({name}): {e}")
            break
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except OSError:
        pass
    print(f"  *** วางไฟล์ที่คำนวณแล้วกลับเข้า OneDrive ไม่ได้ ({name}) — ไฟล์ถูกถือไว้ ลองรันใหม่อีกครั้ง")
    return False


def _recalc_one(win32, p: str) -> bool:
    before = _excel_pids()
    xl = win32.DispatchEx("Excel.Application")
    ours = _excel_pids() - before          # โปรเซส Excel ที่เราเป็นคนเปิด
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.AskToUpdateLinks = False
    ok = True
    try:
        # Excel ปฏิเสธคำสั่งได้ถ้ามันกำลังยุ่ง หรือไฟล์เพิ่งถูกอ่านค้างอยู่
        # (com_error 'Call was rejected by callee') รอแล้วลองใหม่มักผ่าน
        #
        # ต้องรอนานพอ เพราะไฟล์ OEE ถูกขั้นที่ 3 เขียนเสร็จเพียงไม่กี่วินาทีก่อนถึงตรงนี้
        # และ OneDrive จะคว้าไฟล์ไปอัปโหลดทันที ช่วงนั้น Excel เปิดไม่ได้
        # เดิมลอง 3 ครั้ง ห่าง 5 วิ (~15 วิ) ไม่พอ: 24 ก.ย. 2569 08:01 MTBF ผ่าน
        # แต่ OEE ล้มทั้ง 3 ครั้ง สูตร 'หมวดหมู่เครื่อง' ว่างทั้งคอลัมน์จนมีคนมาสั่งใหม่ตอนบ่าย
        # ตอนนี้ลอง RETRIES ครั้ง รอนานขึ้นทีละ 5 วิ (5,10,15,...) รวมราว 1.5 นาที
        for attempt in range(1, RETRIES + 1):
            try:
                wb = xl.Workbooks.Open(p, UpdateLinks=0, ReadOnly=False)
                xl.Calculation = -4105          # xlCalculationAutomatic
                xl.CalculateFullRebuild()
                # ต้องรอให้ Excel คำนวณเสร็จก่อนเซฟ
                #
                # CalculateFullRebuild() สั่งแล้วคืนค่าทันที ไม่ได้รอให้เสร็จ
                # ถ้าเซฟเลย ค่าที่ฝังลงไฟล์จะยังว่าง แล้ว pandas อ่านช่องสูตร
                # ได้เป็นค่าว่าง ทั้งที่เปิดดูใน Excel เห็นตัวเลขปกติ
                # (เจอจริง 15 ก.ย. 2569 คอลัมน์ หมวดหมู่เครื่อง ว่างทั้ง 49 แถว)
                #
                # CalculationState: 0 = คำนวณเสร็จ, 1 = กำลังคำนวณ, 2 = รอคิว
                for _ in range(120):            # รอไม่เกิน 60 วินาที
                    if xl.CalculationState == 0:
                        break
                    time.sleep(0.5)

                # CalculationState == 0 ยังเชื่อไม่ได้ว่าค่าลงช่องแล้ว
                # 1 ต.ค. 2569 07:59 สถานะบอกเสร็จ เซฟ ปิด แล้วคอลัมน์ หมวดหมู่เครื่อง
                # ยังว่าง 46/46 ทั้งที่รอแล้ว — จึงต้อง "อ่านช่องจริง" ก่อนเซฟ
                # ถ้ายังว่าง สั่งคำนวณใหม่แล้วรออีก ทำซ้ำได้ไม่กี่รอบ
                computed = True          # True = มีค่า, False = ว่าง, None = ตรวจไม่ได้
                if os.path.basename(p) == os.path.basename(VERIFY[0]):
                    for round_ in range(1, 4):
                        state = _canary_filled(wb, VERIFY[1], VERIFY[2])
                        if state is None:
                            computed = None      # ตรวจไม่ได้ ไม่มีประโยชน์จะคำนวณซ้ำ
                            break
                        if state:
                            computed = True
                            break
                        computed = False
                        print(f"  ค่าในช่องสูตรยังว่าง สั่งคำนวณใหม่รอบ {round_}/3 "
                              f"({os.path.basename(p)})")
                        xl.CalculateFull()
                        for _ in range(120):
                            if xl.CalculationState == 0:
                                break
                            time.sleep(0.5)
                        time.sleep(2)
                wb.Save()
                wb.Close(False)
                # ค่าที่ Excel มีในหน่วยความจำ กับค่าที่ลงไฟล์จริง ไม่ใช่สิ่งเดียวกัน
                # 6 และ 8 ต.ค. 2569: ตัวเช็คข้างบนเห็นค่าครบ เซฟ ปิด แล้วไฟล์บนดิสก์ว่างทั้งคอลัมน์
                # จึงอ่านไฟล์ที่เซฟแล้วกลับมาดูทันที และพิมพ์เวลา/ขนาดไฟล์ไว้เป็นหลักฐาน
                # (ตัวตัดสินจริงคือ verify() ใน main ซึ่งอ่านไฟล์เหมือนที่แดชบอร์ดอ่าน)
                if os.path.basename(p) == os.path.basename(VERIFY[0]):
                    time.sleep(1)
                    st_ = os.stat(p)
                    on_disk = _saved_canary(p, VERIFY[1], VERIFY[2])
                    print(f"  ไฟล์หลังเซฟ: {time.strftime('%H:%M:%S', time.localtime(st_.st_mtime))} "
                          f"{st_.st_size:,} B · ช่องสูตรแถวสุดท้ายบนดิสก์: "
                          f"{'มีค่า' if on_disk else 'ว่าง' if on_disk is False else 'อ่านไม่ได้'}")
                    if on_disk is False:
                        computed = False
                if computed is True:
                    print(f"  คำนวณและเซฟแล้ว: {os.path.basename(p)}")
                elif computed is None:
                    ok = False
                    print(f"  เซฟแล้ว แต่ยืนยันค่าในช่องสูตรไม่ได้ (ดูเหตุผลบรรทัดบน): "
                          f"{os.path.basename(p)}")
                else:
                    ok = False
                    print(f"  เซฟแล้วแต่ค่าในช่องสูตรยังว่าง: {os.path.basename(p)}")
                break
            except Exception as e:
                if attempt == RETRIES:
                    ok = False
                    print(f"  ผิดพลาด {os.path.basename(p)} หลังลอง {RETRIES} ครั้ง: {e}")
                else:
                    wait = 5 * attempt
                    print(f"  เปิดไม่ได้ (น่าจะ OneDrive กำลังซิงก์) รอ {wait} วิ "
                          f"แล้วลองครั้งที่ {attempt + 1}/{RETRIES} ({os.path.basename(p)})")
                    time.sleep(wait)
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


def _read_sheet_retry(path: str, sheet: str):
    """อ่านชีตด้วย pandas โดยรอให้ไฟล์ถูกปล่อยก่อน

    หลัง Excel เซฟแล้วปิด OneDrive จะคว้าไฟล์ไปอัปโหลดทันที ช่วงนั้นเปิดอ่านจะได้
    PermissionError ทั้งที่ไฟล์ปกติดี (5 พ.ย. 2569 ล้มแบบนี้ 2 รอบติด ทั้งที่เซฟสำเร็จ)
    จึงลองซ้ำทุก 3 วิ ราวหนึ่งนาทีก่อนยอมแพ้
    """
    import pandas as pd
    last = None
    for attempt in range(20):
        try:
            return pd.read_excel(path, sheet_name=sheet, engine="calamine")
        except PermissionError as e:
            last = e
            if attempt == 0:
                print("  ไฟล์ถูกถือไว้ (OneDrive/Excel) — รอให้ปล่อยก่อนอ่าน", end="", flush=True)
            print(".", end="", flush=True)
            time.sleep(3)
    print()
    raise last


def verify() -> bool:
    """เปิดไฟล์ด้วย pandas แล้วดูว่าช่องสูตรมีค่าจริงไหม"""
    import pandas as pd
    rel, sheet, col = VERIFY
    path = os.path.join(DEPT_DIR, rel)
    if not os.path.exists(path):
        return True
    try:
        df = _read_sheet_retry(path, sheet)
    except PermissionError as e:
        print(f"\n  ตรวจผลไม่ได้ ไฟล์ยังถูกถือไว้: {e}")
        return False
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
        df = _read_sheet_retry(src, "Report1")

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
        # เปลี่ยนชื่อทับทีเดียว กันไฟล์ครึ่ง ๆ ตอน OneDrive sync
        # แต่บน Windows ถ้าแดชบอร์ดตัวใดกำลังอ่าน parquet อยู่พอดี replace จะล้ม (PermissionError)
        # แดชบอร์ด 7 ตัวอ่านไฟล์นี้ตลอด จึงลองซ้ำสั้น ๆ ก่อนยอมแพ้ และถ้ายอมแพ้ต้องบอกดัง ๆ
        # (1 ต.ค. และ 8 ต.ค. 2569 Excel เซฟสำเร็จแต่ parquet ค้างของเก่า โดยไม่มีใครรู้)
        last_err = None
        for attempt in range(6):
            try:
                os.replace(tmp, out)
                last_err = None
                break
            except PermissionError as e:
                last_err = e
                time.sleep(1 + attempt)
        if last_err is not None:
            raise last_err
        print("  export parquet: %d แถว %d คอลัมน์ (%.1f MB)"
              % (len(df), df.shape[1], os.path.getsize(out) / 1e6))
        return True
    except Exception as e:
        print(f"  *** export parquet ไม่สำเร็จ: {e}")
        print("  *** แดชบอร์ด OEE จะยังเห็นตัวเลขของรอบก่อน จนกว่าจะรัน  python etl_recalc_excel.py  ใหม่")
        return False


def main() -> int:
    print("สั่ง Excel คำนวณสูตรและเซฟ")
    # ตัวตัดสินว่าสำเร็จคือ verify() ซึ่งอ่านไฟล์ที่เซฟแล้วแบบเดียวกับที่แดชบอร์ดอ่าน
    # ไม่ใช่สิ่งที่ Excel บอกผ่าน COM — ล้มมา 3 ใน 5 รอบ (1, 6, 8 ต.ค. 2569) ทั้งที่ COM บอกว่าเรียบร้อย
    # ถ้ายังว่าง ให้ทำซ้ำทั้งรอบ (เปิด-คำนวณ-เซฟ) โดยเว้นช่วงให้ OneDrive ปล่อยไฟล์ก่อน
    ok_recalc = ok_verify = False
    for cycle in range(1, RECALC_CYCLES + 1):
        if cycle > 1:
            print(f"\n  ช่องสูตรยังว่างหลังเซฟ — รอ {10 * (cycle - 1)} วิ แล้วทำซ้ำรอบ {cycle}/{RECALC_CYCLES}")
            time.sleep(10 * (cycle - 1))
        ok_recalc = recalc(TARGETS)
        ok_verify = verify()
        if ok_verify:
            break
    # export ก็ต่อเมื่อค่าในไฟล์ครบ ไม่งั้น parquet ที่ได้จะว่างทั้งคอลัมน์ ซึ่งแย่กว่าของเก่า
    # (แดชบอร์ดเห็น 'ไม่ระบุ' ทั้งวัน) ของเก่าแค่ขาดวันล่าสุด และตัวตรวจสุขภาพจะฟ้องให้
    ok_export = export_parquet() if ok_verify else False
    if ok_verify and not ok_export:
        pass                       # export พิมพ์เหตุผลเองแล้ว
    elif not ok_verify:
        print("\n  *** ไม่ได้ export parquet เพราะช่องสูตรในไฟล์ยังว่างหลังลอง %d รอบ" % RECALC_CYCLES)
        print("  *** เปิดไฟล์เรื่อง 3 ด้วย Excel กด Save 1 ครั้ง แล้วรัน  python etl_recalc_excel.py")
    if not ok_recalc:
        print("\n  สั่ง Excel ไม่สำเร็จบางไฟล์")
        print("  ถ้าตัวเลขบนแดชบอร์ดหาย ให้เปิดไฟล์เรื่อง 2 และ 3 ด้วย Excel")
        print("  แล้วกด Save 1 ครั้ง หรือรัน  python etl_recalc_excel.py  ใหม่อีกรอบ")
    return 0 if (ok_recalc and ok_verify and ok_export) else 1


if __name__ == "__main__":
    sys.exit(main())
