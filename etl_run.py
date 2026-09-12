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
    """รันสคริปต์ลูก ให้ผลลัพธ์ไหลออกหน้าจอสด ๆ"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        return subprocess.call([sys.executable] + args, env=env, cwd=HERE)
    except Exception as e:
        print(f"  เรียก {label} ไม่สำเร็จ: {e}")
        return 1


def main() -> int:
    head("อัปเดตข้อมูล MOS ประจำวัน")
    if not os.path.exists(UPDATE_MOS):
        print("  ไม่พบสคริปต์ ETL ของฝ่ายที่")
        print("  " + UPDATE_MOS)
        print("\n  ตรวจว่า OneDrive ซิงก์โฟลเดอร์ฝ่ายครบหรือยัง")
        return 1

    head("ขั้น 1/4  ย้ายไฟล์ export เข้าโฟลเดอร์ลงวันที่")
    if run([os.path.join(HERE, "etl_prepare.py")], "etl_prepare.py") != 0:
        print("\n  หยุดที่ขั้น 1 — ยังไม่มีการเขียนข้อมูลใด ๆ")
        return 1

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
    if run([UPDATE_MOS], "update_mos.py") != 0:
        print("\n  อัปเดตไม่สำเร็จ — ไฟล์เดิมถูกสำรองไว้ในโฟลเดอร์ _backup_ROLLBACK_ แล้ว")
        return 1

    head("ขั้น 4/4  ให้ Excel คำนวณสูตรแล้วเซฟ")
    rc = run([os.path.join(HERE, "etl_recalc_excel.py")], "etl_recalc_excel.py")

    head("เสร็จเรียบร้อย" if rc == 0 else "เสร็จแล้ว แต่ขั้น 4 มีปัญหา")
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
    input("  กด Enter เพื่อปิดหน้าต่าง...")
    sys.exit(code)
