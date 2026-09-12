# -*- coding: utf-8 -*-
"""สำรองโค้ดทั้งโปรเจกต์ขึ้น OneDrive

ทำอะไร
    บีบ repo ทั้งก้อนพร้อมประวัติทุกคอมมิตเป็นไฟล์เดียว (git bundle)
    แล้ววางใน OneDrive ของฝ่าย ซึ่งซิงก์ขึ้นคลาวด์เองอัตโนมัติ

ทำไมใช้ bundle ไม่ใช่ก๊อปโฟลเดอร์ .git ไปวางตรง ๆ
    โฟลเดอร์ .git มีไฟล์ย่อยเป็นพัน ๆ ไฟล์ ถ้าให้ OneDrive ซิงก์ทีละไฟล์
    มีโอกาสซิงก์ไม่ครบแล้วได้ repo ที่เสียหาย ส่วน bundle เป็นไฟล์เดียว
    ซิงก์สำเร็จหรือไม่สำเร็จไปเลย ไม่มีสภาพครึ่ง ๆ และกู้คืนได้ครบทั้งประวัติ

เก็บกี่ชุด
    เก็บไฟล์ลงวันที่ไว้ KEEP ชุดล่าสุด เผื่อกรณีที่ไฟล์ล่าสุดเสียหรือคอมมิตผิด
    ยังมีของเก่าให้ย้อนกลับได้ พร้อมไฟล์ 'ล่าสุด' ที่ชี้ชุดใหม่สุดเสมอ

รันเอง:       python backup_code.py
รันอัตโนมัติ: ถูกเรียกจาก git hook ทุกครั้งที่คอมมิต (ดู .git/hooks/post-commit)
กู้คืน:       อ่านวิธีในไฟล์ วิธีกู้คืนโค้ด.txt ที่อยู่ในโฟลเดอร์สำรอง
"""

import datetime as dt
import glob
import os
import shutil
import subprocess
import sys

# git hook เรียกสคริปต์นี้โดยไม่ได้ตั้ง encoding ให้ คอนโซลจึงพิมพ์ภาษาไทยไม่ได้
# และโยน UnicodeEncodeError ทั้งที่งานสำรองสำเร็จไปแล้ว จึงบังคับ UTF-8 ที่นี่เลย
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJ = os.path.dirname(os.path.abspath(__file__))
DEST = (
    r"C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD"
    r"\ฝ่ายซ่อมบำรุงรักษา\_backup_โค้ดแดชบอร์ด"
)
KEEP = 10
NAME = "Claude-code"

RESTORE_DOC = """วิธีกู้คืนโค้ดแดชบอร์ดจากไฟล์สำรอง
==========================================

ไฟล์ในโฟลเดอร์นี้คือสำเนาโค้ดทั้งโปรเจกต์ พร้อมประวัติการแก้ทุกครั้ง
หนึ่งไฟล์ = repo ทั้งก้อน ไม่ต้องมีไฟล์อื่นประกอบ

กู้คืนทำยังไง
  1. ติดตั้ง Git ถ้าเครื่องใหม่ยังไม่มี   https://git-scm.com/download/win
  2. เปิด Command Prompt แล้วสั่ง

        git clone "<ชื่อไฟล์ .bundle>" Claude-code

     จะได้โฟลเดอร์ Claude-code กลับมาครบ พร้อมประวัติทุกคอมมิต

  3. ติดตั้งไลบรารีที่ต้องใช้

        cd Claude-code
        pip install -r requirements.txt
        pip install xlsxwriter pywin32

  4. สร้างไฟล์ผู้ใช้ใหม่ เพราะรหัสผ่านไม่ได้ถูกสำรองมาด้วยโดยตั้งใจ

        python manage_users.py

สิ่งที่ไม่ได้อยู่ในไฟล์สำรองนี้ (ตั้งใจไม่เก็บ)
  - .streamlit/secrets.toml   รหัสผ่านผู้ใช้แดชบอร์ด
  - py_progress/ กับ pbi_progress/   ความก้าวหน้าผู้เรียน
  - ข้อมูล Excel ของฝ่าย ซึ่งอยู่บน OneDrive อยู่แล้วคนละที่กับโค้ด

ตรวจว่าไฟล์สำรองยังดีอยู่ไหม
        git bundle verify "<ชื่อไฟล์ .bundle>"
"""


def run(args, **kw):
    return subprocess.run(args, cwd=PROJ, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def main() -> int:
    if not os.path.isdir(os.path.join(PROJ, ".git")):
        print("  ไม่ใช่ git repo — ข้ามการสำรอง")
        return 1

    # มีคอมมิตค้างไหม เตือนไว้ให้รู้ตัว แต่ยังสำรองต่อ
    st = run(["git", "status", "--porcelain"])
    dirty = [ln for ln in st.stdout.splitlines() if ln.strip()]

    n = run(["git", "rev-list", "--count", "HEAD"]).stdout.strip() or "?"
    head = run(["git", "log", "-1", "--format=%h %s"]).stdout.strip()

    try:
        os.makedirs(DEST, exist_ok=True)
    except Exception as e:
        print(f"  สร้างโฟลเดอร์สำรองไม่ได้: {e}")
        return 1

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    out = os.path.join(DEST, f"{NAME}_{stamp}.bundle")
    tmp = out + ".tmp"

    r = run(["git", "bundle", "create", tmp, "--all"])
    if r.returncode != 0 or not os.path.exists(tmp):
        print("  สร้างไฟล์สำรองไม่สำเร็จ:\n" + (r.stderr or "")[:400])
        return 1

    v = run(["git", "bundle", "verify", tmp])
    if v.returncode != 0:
        print("  ไฟล์สำรองที่ได้ใช้ไม่ได้ ยกเลิก:\n" + (v.stderr or "")[:400])
        os.remove(tmp)
        return 1

    os.replace(tmp, out)
    size = os.path.getsize(out) / 1e6

    latest = os.path.join(DEST, f"{NAME}_ล่าสุด.bundle")
    try:
        shutil.copy2(out, latest)
    except Exception:
        pass

    with open(os.path.join(DEST, "วิธีกู้คืนโค้ด.txt"), "w", encoding="utf-8") as f:
        f.write(RESTORE_DOC)

    # เก็บชุดลงวันที่ไว้ KEEP ชุด ที่เหลือลบทิ้ง
    old = sorted(glob.glob(os.path.join(DEST, f"{NAME}_2*.bundle")))
    removed = 0
    for p in old[:-KEEP]:
        try:
            os.remove(p)
            removed += 1
        except Exception:
            pass

    print(f"  สำรองโค้ดแล้ว: {os.path.basename(out)}  ({size:.1f} MB)")
    print(f"  {n} คอมมิต · ล่าสุด {head}")
    print(f"  เก็บไว้ {len(old) - removed} ชุด" + (f" (ลบชุดเก่า {removed})" if removed else ""))
    if dirty:
        print(f"  หมายเหตุ: มีไฟล์แก้ค้างยังไม่คอมมิต {len(dirty)} ไฟล์ — ของพวกนี้ยังไม่ถูกสำรอง")
    return 0


if __name__ == "__main__":
    sys.exit(main())
