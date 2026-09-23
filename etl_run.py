# -*- coding: utf-8 -*-
"""อัปเดตข้อมูล MOS ประจำวัน — ทำครบทุกขั้นในคำสั่งเดียว

ขั้นตอน
  1. ย้ายไฟล์ export จาก Downloads เข้าโฟลเดอร์ลงวันที่   (etl_prepare.py)
  2. ตรวจคุณภาพข้อมูล ยังไม่เขียนอะไร                    (update_mos.py --check)
  3. อัปเดตฐานหลักทั้ง 3 เรื่อง + parquet                  (update_mos.py)
  4. สั่ง Excel คำนวณสูตร เซฟ แล้ว export OEE parquet     (etl_recalc_excel.py)

ทำไมงานทั้งหมดอยู่ในไฟล์ Python ไม่ใช่ในไฟล์ .bat
    ไฟล์ .bat ที่มีภาษาไทยกับวงเล็บในคำสั่ง echo ทำให้ cmd.exe แปลผิดและพัง
    (เจอจริงเมื่อ 2026-09-12) Python จัดการ UTF-8 ได้ถูกต้องเสมอ
    ไฟล์ .bat จึงเหลือหน้าที่เดียวคือเรียกสคริปต์นี้ และมีแต่อักษรอังกฤษ

รันเดี่ยว ๆ ได้:  python etl_run.py
อยากให้ถามยืนยัน: python etl_run.py --ask
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEPT_DIR = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา"
)
UPDATE_MOS = os.path.join(DEPT_DIR, "00_ETL_Pipeline", "update_mos.py")

LINE = "=" * 62


def head(text: str) -> None:
    print("\n" + LINE)
    print("  " + text)
    print(LINE)


def run(args, label: str) -> int:
    """รันสคริปต์ลูก ให้ผลลัพธ์ไหลออกหน้าจอสด ๆ แล้วบอกเวลาที่ใช้"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    t0 = time.time()
    try:
        rc = subprocess.call([sys.executable] + args, env=env, cwd=HERE)
    except Exception as e:
        print(f"  เรียก {label} ไม่สำเร็จ: {e}")
        return 1
    print(f"  (ใช้เวลา {time.time() - t0:.0f} วินาที)")
    return rc


def snapshot():
    """อ่านสถานะข้อมูลปัจจุบัน — ใช้เทียบก่อนกับหลังเพื่อพิสูจน์ว่าเขียนจริง

    มีไว้เพราะบทเรียนเมื่อ 2026-09-12: หน้าจอขึ้นว่าจบงานแล้ว แต่ฐานข้อมูล
    ไม่ได้ถูกเขียน และไม่มีใครรู้จนผ่านไปสองชั่วโมง ข้อความว่า "เสร็จ" อย่างเดียว
    เชื่อไม่ได้ ต้องเอาตัวเลขจริงมากางให้ดู
    """
    try:
        import pandas as pd
        import data_paths
        df = pd.read_parquet(data_paths.workcenter_parquet())
        s = pd.to_datetime(df["Start"], errors="coerce")
        return len(df), s.max()
    except Exception:
        return None, None


def report(before_rows, before_last) -> None:
    """กางตัวเลขให้เห็นว่าข้อมูลเพิ่มขึ้นจริงหรือไม่"""
    import datetime as dt

    rows, last = snapshot()
    if rows is None:
        print("  อ่านไฟล์ข้อมูลเพื่อตรวจผลไม่ได้ ให้เปิดแดชบอร์ดดูเองอีกที")
        return

    added = rows - before_rows if before_rows else None
    print(f"  แถวข้อมูลรวม     {rows:,}" + (f"   (เพิ่มขึ้น {added:,} แถว)" if added is not None else ""))
    print(f"  ข้อมูลล่าสุดถึง   {last:%Y-%m-%d %H:%M}")

    if added == 0:
        print()
        print("  *** ไม่มีแถวใหม่เข้ามาเลย ***")
        print("  แปลว่า export รอบนี้ไม่มีข้อมูลที่ยังไม่เคยเข้าฐาน")
        print("  ถ้าเพิ่งดึงไฟล์มาสด ๆ แล้วยังเป็นแบบนี้ ให้บอกคนดูแลระบบ")
        return

    if last is not None:
        gap = (dt.datetime.now() - last.to_pydatetime()).total_seconds() / 3600
        if gap > 20:
            print()
            print(f"  *** ข้อมูลล่าสุดเก่ากว่าปัจจุบัน {gap:.0f} ชั่วโมง ***")
            print("  ตรวจว่าดึง export ถูกไฟล์หรือไม่")

    check_oee_duplicates()


def check_oee_duplicates() -> None:
    """เตือนถ้าไฟล์ OEE มีเครื่องเดียวกันซ้ำในวันเดียวกัน

    ETL ของฝ่ายตัดแถวซ้ำเฉพาะฝั่ง Workcenter ฝั่ง OEE ต่อท้ายชีตโดยไม่เทียบของเดิม
    อัปเดตสองรอบในวันเดียวจึงได้แถวซ้ำ แล้วยอดรวมของวันนั้นพองเป็นเท่าตัว
    (เจอ 2026-09-17 วันที่ 12 ก.ย. มี 132 แถวจาก 50 เครื่อง)

    ที่นี่ตรวจอย่างเดียว ไม่แก้ เพราะการลบแถวออกจากฐานควรให้คนตัดสินใจ
    ถ้าเจอ ให้รัน  python fix_oee_duplicates.py  ดูรายละเอียดก่อน
    """
    try:
        import os
        import pandas as pd
        import data_paths
        p = os.path.join(data_paths.DEPT_DIR,
                         r"00_ETL_Pipeline\parquet\oee_report1.parquet")
        if not os.path.exists(p):
            return
        o = pd.read_parquet(p)
        d = pd.to_datetime(o["Trans_date"], errors="coerce").dt.date
        dup = o.assign(_d=d).duplicated(subset=["MC", "_d"]).sum()
        if dup:
            print()
            print(f"  *** ไฟล์ OEE มีเครื่องซ้ำวันเดียวกัน {dup} แถว ***")
            print("  ตัวเลข OEE ของวันนั้นจะสูงเกินจริง")
            print("  ดูรายละเอียดด้วย  python fix_oee_duplicates.py")
    except Exception:
        pass


def main() -> int:
    head("อัปเดตข้อมูล MOS ประจำวัน")
    before_rows, _ = snapshot()
    if not os.path.exists(UPDATE_MOS):
        print("  ไม่พบสคริปต์ ETL ของฝ่ายที่")
        print("  " + UPDATE_MOS)
        print("\n  ตรวจว่า OneDrive ซิงก์โฟลเดอร์ฝ่ายครบหรือยัง")
        return 1

    head("ขั้น 1/4  ย้ายไฟล์ export เข้าโฟลเดอร์ลงวันที่")
    rc1 = run([os.path.join(HERE, "etl_prepare.py")], "etl_prepare.py")
    # rc1 == 2 แปลว่าไม่มีไฟล์ใหม่ใน Downloads ให้ย้าย ซึ่งไม่ใช่ความผิดพลาด
    # ต้องเดินต่อเสมอ เพราะไฟล์ที่ย้ายไปแล้วในรอบก่อนอาจยังไม่ได้โหลดเข้าฐาน
    #
    # เดิมตรงนี้หยุดทันทีถ้า rc1 != 0 ผลคือ 14-15 ก.ย. 2569 รอบแรกย้ายไฟล์สำเร็จ
    # แต่ล้มทีหลัง พอกดซ้ำ Downloads ว่างแล้ว จึงหยุดที่ขั้นนี้ทุกครั้ง
    # ไฟล์ค้างอยู่ในโฟลเดอร์สองวันโดยกดปุ่มกี่ทีก็ไม่มีอะไรเกิดขึ้น
    if rc1 == 1:
        print("\n  หยุดที่ขั้น 1 — ยังไม่มีการเขียนข้อมูลใด ๆ")
        return 1
    if rc1 == 2:
        print("\n  ไม่มีไฟล์ใหม่ให้ย้าย — เดินต่อเผื่อมีไฟล์รอบก่อนที่ยังไม่ได้โหลดเข้าฐาน")

    head("ขั้น 2/4  ตรวจคุณภาพข้อมูล")
    if run([UPDATE_MOS, "--check"], "update_mos.py --check") != 0:
        print("\n  ด่านตรวจไม่ผ่าน — ยังไม่มีการเขียนข้อมูลใด ๆ")
        print("  อ่านข้อความด้านบนแล้วแก้ที่ต้นทางก่อน")
        return 1

    # ไม่ถามยืนยันแล้วโดยตั้งใจ
    #
    # เดิมมีคำถาม y/n ตรงนี้ ผลคือ 2026-09-12 ผู้ใช้กดปุ่มแล้วไฟล์ถูกย้ายเข้าระบบ
    # แต่ฐานข้อมูลไม่ถูกอัปเดต เพราะกด Enter เฉย ๆ ซึ่งนับเป็น "ไม่เอา"
    # หน้าจอขึ้นว่ายกเลิกแล้วจริง แต่ข้อความผ่านตาไป กลายเป็นข้อมูลขาดไป 2 ชั่วโมง
    #
    # ตัวกันความผิดพลาดจริง ๆ คือด่านตรวจคุณภาพข้อมูลข้างบน ถ้ามี error มันหยุดเอง
    # และ update_mos.py สำรองไฟล์ก่อนเขียนทุกครั้งอยู่แล้ว คำถามนี้จึงไม่ได้กันอะไร
    # มีแต่เพิ่มจังหวะให้พลาด
    #
    # ใครอยากได้คำถามคืน สั่ง  python etl_run.py --ask
    if "--ask" in sys.argv:
        print()
        ans = input("  ด่านตรวจผ่านแล้ว จะอัปเดตจริงไหม (Enter = เอา / n = ยกเลิก) : ").strip().lower()
        if ans in ("n", "no", "ไม่"):
            print("\n  ยกเลิกแล้ว ไม่มีการเขียนไฟล์ใด ๆ")
            return 0

    head("ขั้น 3/4  อัปเดตฐานข้อมูลหลัก")
    print("  ขั้นนี้เขียนไฟล์ Excel ขนาดใหญ่ ใช้เวลาหลายนาทีและหน้าจอจะเงียบ")
    print("  อย่าเพิ่งปิดหน้าต่าง รอจนขึ้นข้อความขั้นถัดไป\n")
    if run([UPDATE_MOS], "update_mos.py") != 0:
        print("\n  อัปเดตไม่สำเร็จ — ไฟล์เดิมถูกสำรองไว้ที่ _backup_ROLLBACK\\<วันที่> แล้ว")
        return 1

    head("ขั้น 4/4  ให้ Excel คำนวณสูตรแล้วเซฟ")
    print("  เปิด Excel เบื้องหลังเพื่อคำนวณสูตร ใช้เวลาราวหนึ่งถึงสองนาที\n")
    rc = run([os.path.join(HERE, "etl_recalc_excel.py")], "etl_recalc_excel.py")

    head("เสร็จเรียบร้อย" if rc == 0 else "เสร็จแล้ว แต่ขั้น 4 มีปัญหา")
    report(before_rows, None)
    print()
    if rc == 0:
        print("  แดชบอร์ดพอร์ต 8503 และ 8507 จะเห็นข้อมูลใหม่ในรอบรีเฟรชถัดไป")
        print("  Power BI ให้กด Refresh All เอง")
    else:
        print("  ฐานข้อมูลอัปเดตแล้ว แต่สูตรใน Excel อาจยังไม่ถูกคำนวณ")
        print("  ให้เปิดไฟล์เรื่อง 2 และ 3 ด้วย Excel แล้วกด Save 1 ครั้ง")
    return rc


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        print("\n\n  ยกเลิกโดยผู้ใช้")
        code = 1
    print()
    try:
        input("  กด Enter เพื่อปิดหน้าต่าง...")
    except EOFError:
        pass          # รันแบบไม่มีแป้นพิมพ์ ไม่ต้องรอ
    sys.exit(code)
