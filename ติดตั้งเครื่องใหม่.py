# -*- coding: utf-8 -*-
"""ติดตั้งระบบแดชบอร์ดบนเครื่องใหม่ — รันครั้งเดียวหลัง git clone
=================================================================

ทำไมต้องมีไฟล์นี้
  เดิมระบบผูกกับเครื่องและบัญชี Windows ของคนเขียนคนเดียว คนรับช่วงที่ clone
  โค้ดไปต้องเดาเองว่าต้องลงอะไร ข้อมูลอยู่ไหน ผู้ใช้มาจากไหน และทำให้เปิดเอง
  ตอนล็อกอินยังไง สคริปต์นี้ไล่ทำทีละขั้นและถามก่อนทุกขั้นที่เปลี่ยนเครื่อง

ขั้นตอน
  1. ตรวจ Python
  2. ลงไลบรารีจาก requirements.txt
  3. หาโฟลเดอร์ข้อมูลฝ่ายบน OneDrive (ไม่เจอให้วาง path แล้วบันทึกลง data_folder.txt)
  4. ตรวจไฟล์ผู้ใช้ .streamlit/secrets.toml
  5. สร้างทางลัดใน Startup ให้ระบบเปิดเองตอนล็อกอิน
  6. เปิดระบบทั้งหมดตอนนี้

กดซ้ำได้ปลอดภัย ขั้นไหนทำแล้วจะบอกว่าเรียบร้อยแล้วข้ามไป
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VBS = os.path.join(HERE, "เปิดระบบทั้งหมด_เบื้องหลัง.vbs")
SECRETS = os.path.join(HERE, ".streamlit", "secrets.toml")
DATA_FILE = os.path.join(HERE, "data_folder.txt")
STARTUP = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
LINK = os.path.join(STARTUP, "เปิดระบบแดชบอร์ด.lnk")


def ask(q: str) -> bool:
    return input(f"{q} [y/n] ").strip().lower() in ("y", "yes", "ใช่", "ย")


def step(n: int, title: str) -> None:
    print(f"\n[{n}/6] {title}")
    print("-" * 60)


# ไลบรารีใน requirements.txt ล็อกเวอร์ชันตามเครื่องที่ใช้งานจริง (Python 3.12)
# Python ที่ใหม่เกินไปจะไม่มีไฟล์สำเร็จรูป (wheel) ให้ pandas/numpy/pyarrow
# pip จะพยายามคอมไพล์เองแล้วล้ม เพราะต้องมี Visual Studio
# (เกิดจริง 18 พ.ย. 2569 เครื่องผู้รับมอบลง Python 3.15 แล้วขึ้น No module named streamlit)
SUPPORTED = ((3, 12), (3, 13))
VENV = os.path.join(HERE, ".venv")
VENV_PY = os.path.join(VENV, "Scripts", "python.exe")


def _version_of(cmd: list) -> tuple:
    """รันคำสั่ง Python แล้วคืน ((major, minor), path) หรือ None ถ้ารันไม่ได้"""
    try:
        r = subprocess.run(cmd + ["-c", "import sys;print(sys.version_info[0],sys.version_info[1],sys.executable)"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        a, b, path = r.stdout.strip().split(" ", 2)
        return (int(a), int(b)), path
    except Exception:
        return None


def _find_supported() -> str:
    """หา python.exe รุ่น 3.12/3.13 ที่ลงไว้ในเครื่อง คืน path หรือ '' ถ้าไม่เจอ"""
    la = os.environ.get("LOCALAPPDATA", "")
    cands = []
    for mj, mn in SUPPORTED:
        tag = f"{mj}.{mn}"
        cands += [["py", f"-V:{tag}"], ["py", f"-{tag}"],
                  [os.path.join(la, "Programs", "Python", f"Python{mj}{mn}", "python.exe")],
                  [os.path.join(la, "Python", f"pythoncore-{tag}-64", "python.exe")],
                  [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), f"Python{mj}{mn}", "python.exe")]]
    for c in cands:
        if len(c) == 1 and not os.path.exists(c[0]):
            continue
        got = _version_of(c)
        if got and got[0] in SUPPORTED:
            return got[1]
    return ""


def check_python() -> str:
    """เลือก Python ที่จะใช้กับโปรเจกต์ คืน path ของ python.exe หรือ '' ถ้ายังไม่มีรุ่นที่ใช้ได้

    เครื่องที่ Python หลักเป็น 3.12/3.13 ใช้ตัวนั้นเลยเหมือนเดิม
    ถ้าใหม่หรือเก่ากว่านั้น สร้าง .venv จาก 3.12/3.13 ไว้ในโฟลเดอร์โค้ด
    ไฟล์ .bat และ .vbs ทุกตัวจะใช้ .venv เองเมื่อมี — Python หลักของเครื่องไม่ถูกแตะ
    """
    step(1, "ตรวจ Python")
    v = sys.version_info
    print(f"  Python ของเครื่อง: {v.major}.{v.minor}.{v.micro}  ({sys.executable})")
    if os.path.exists(VENV_PY):
        got = _version_of([VENV_PY])
        if got and got[0] in SUPPORTED:
            print(f"  [ok] ใช้ .venv ในโฟลเดอร์โค้ด (Python {got[0][0]}.{got[0][1]})")
            return VENV_PY
        print("  [!] .venv เดิมใช้ไม่ได้ จะสร้างใหม่")
    if (v.major, v.minor) in SUPPORTED:
        print("  [ok] ใช้ได้")
        return sys.executable

    print(f"  [!] โปรเจกต์นี้ใช้ Python 3.12 หรือ 3.13 — รุ่น {v.major}.{v.minor} ยังลงไลบรารีบางตัวไม่ได้")
    base = _find_supported()
    if not base:
        print("  ยังไม่มี Python 3.12 ในเครื่อง")
        if ask("  ลง Python 3.12 ตอนนี้ไหม (ใช้คำสั่ง py install 3.12 ของ Python install manager)"):
            subprocess.run(["py", "install", "3.12"])
            base = _find_supported()
        if not base:
            print("  [x] ยังไม่เจอ Python 3.12 — ลงจาก python.org (Windows installer 64-bit ของ 3.12)")
            print("      ติ๊ก 'Add python.exe to PATH' แล้วรัน ติดตั้งเครื่องใหม่.bat อีกครั้ง")
            print("      Python รุ่นเดิมของเครื่องไม่ต้องลบ ลงคู่กันได้")
            return ""
    print(f"  เจอ Python ที่ใช้ได้: {base}")
    print("  สร้าง .venv ในโฟลเดอร์โค้ด ...")
    r = subprocess.run([base, "-m", "venv", VENV])
    if r.returncode != 0 or not os.path.exists(VENV_PY):
        print("  [x] สร้าง .venv ไม่สำเร็จ — อ่านข้อความด้านบน")
        return ""
    print("  [ok] สร้าง .venv แล้ว ปุ่ม .bat และ .vbs ทุกตัวจะใช้ Python ในนี้เอง")
    return VENV_PY


def install_packages(py: str) -> None:
    step(2, "ลงไลบรารี (requirements.txt)")
    if not ask("  ลง/อัปเดตไลบรารีตอนนี้ไหม (ใช้เน็ต ประมาณ 2-5 นาที)"):
        print("  ข้าม")
        return
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"])
    r = subprocess.run([py, "-m", "pip", "install", "-r",
                        os.path.join(HERE, "requirements.txt")])
    print("  [ok] ลงครบ" if r.returncode == 0 else "  [x] ลงไม่สำเร็จ — อ่านข้อความด้านบน")


def setup_data_folder() -> None:
    step(3, "หาโฟลเดอร์ข้อมูลฝ่าย (OneDrive)")
    sys.path.insert(0, HERE)
    import data_paths
    if os.path.isdir(data_paths.DEPT_DIR):
        print(f"  [ok] เจอแล้ว: {data_paths.DEPT_DIR}")
        return
    print(f"  [x] ไม่เจอที่ {data_paths.DEPT_DIR}")
    # แยกกรณี "ยังไม่ได้ล็อกอิน OneDrive บริษัทเลย" ออกมา — เจอจริงที่คอมห้องช่าง 20 พ.ย. 2569
    # เครื่องมีแค่ OneDrive - Personal คนกดตามคำแนะนำเรื่อง shortcut ก็ไม่มีวันเจอ
    import glob
    if not (os.environ.get("OneDriveCommercial")
            or glob.glob(os.path.join(os.path.expanduser("~"), "OneDrive - Modernform*"))):
        print("  เครื่องนี้ยังไม่ได้ล็อกอิน OneDrive ของบริษัท (มีแค่ OneDrive ส่วนตัวหรือไม่มีเลย)")
        print("  ไอคอนเมฆมุมขวาล่าง > Settings > Account > Add an account > ล็อกอินอีเมล @modernform.co.th")
    print("  วิธีแก้: ขอสิทธิ์โฟลเดอร์ ฝ่ายซ่อมบำรุงรักษา (หรือ Cue_IE_PD ทั้งโฟลเดอร์)")
    print("         แล้วใน OneDrive บนเว็บ > Shared > กด 'Add shortcut to My files'")
    print("         รอ sync เสร็จแล้วรันไฟล์นี้ใหม่ หรือวาง path โฟลเดอร์ 'ฝ่ายซ่อมบำรุงรักษา' ด้านล่าง")
    p = input("  path (เว้นว่าง = ข้าม): ").strip().strip('"')
    if not p:
        return
    if not os.path.isdir(p):
        print("  [x] ไม่มีโฟลเดอร์นี้ — ไม่บันทึก")
        return
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        f.write(p + "\n")
    print(f"  [ok] บันทึกลง {os.path.basename(DATA_FILE)} แล้ว")


def check_users(py: str) -> None:
    step(4, "ผู้ใช้สำหรับล็อกอินแดชบอร์ด")
    if os.path.exists(SECRETS):
        print("  [ok] มีไฟล์ผู้ใช้แล้ว (.streamlit/secrets.toml)")
        return
    print("  ยังไม่มีไฟล์ผู้ใช้ — ไฟล์นี้ไม่อยู่บน GitHub โดยตั้งใจ (เก็บค่าแฮชรหัสผ่าน)")
    print("  ทางเลือก: ขอไฟล์ secrets.toml จากคนดูแลเดิมมาวางที่โฟลเดอร์ .streamlit")
    print("           หรือสร้างผู้ใช้ใหม่ตอนนี้")
    if ask("  สร้างผู้ใช้ใหม่ตอนนี้ไหม"):
        # ต้องใช้ Python ตัวเดียวกับที่ลงไลบรารีไว้ (อาจเป็น .venv) — manage_users import streamlit
        # ผ่าน auth.py ถ้าใช้ Python ของเครื่องจะล้มด้วย No module named 'streamlit'
        subprocess.run([py, os.path.join(HERE, "manage_users.py")], cwd=HERE)


def make_startup_link() -> None:
    step(5, "ให้ระบบเปิดเองทุกครั้งที่ล็อกอิน Windows")
    if os.path.exists(LINK):
        print(f"  [ok] มีทางลัดแล้ว: {LINK}")
        return
    if not ask("  สร้างทางลัดในโฟลเดอร์ Startup ไหม"):
        print("  ข้าม — เปิดเองได้ด้วยการดับเบิลคลิก เปิดระบบทั้งหมด_เบื้องหลัง.vbs")
        return
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);"
          "$s.TargetPath=$env:VBS;$s.WorkingDirectory=$env:HERE;$s.Save()")
    env = dict(os.environ, LNK=LINK, VBS=VBS, HERE=HERE)
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env)
    print("  [ok] สร้างแล้ว" if r.returncode == 0 and os.path.exists(LINK)
          else "  [x] สร้างไม่สำเร็จ")


def start_now() -> None:
    step(6, "เปิดระบบตอนนี้")
    if ask("  เปิดแดชบอร์ดทั้ง 9 ระบบตอนนี้ไหม"):
        subprocess.Popen(["wscript.exe", VBS], cwd=HERE)
        print("  สั่งเปิดแล้ว รอ ~40 วินาที แล้วเข้า http://localhost:8507")


def main() -> None:
    print("=" * 60)
    print("  ติดตั้งระบบแดชบอร์ดฝ่ายซ่อมบำรุงบนเครื่องนี้")
    print(f"  โฟลเดอร์โค้ด: {HERE}")
    print("=" * 60)
    py = check_python()
    if not py:
        return
    install_packages(py)
    setup_data_folder()
    check_users(py)
    make_startup_link()
    start_now()
    print("\nขั้นต่อไป")
    print("  - ให้คนอื่นในวง LAN เข้าดูได้: คลิกขวา เปิด_firewall_dashboards.bat > Run as administrator")
    print("  - ตรวจว่าระบบปกติ: ดับเบิลคลิก ตรวจสุขภาพระบบ.bat")
    print("  - คู่มือเต็ม: คู่มือส่งมอบระบบ.md")


if __name__ == "__main__":
    main()
