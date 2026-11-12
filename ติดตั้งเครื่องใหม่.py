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


def check_python() -> bool:
    step(1, "ตรวจ Python")
    v = sys.version_info
    print(f"  Python {v.major}.{v.minor}.{v.micro}  ({sys.executable})")
    if (v.major, v.minor) < (3, 12):
        print("  [x] ต้องใช้ Python 3.12 ขึ้นไป — ลงจาก python.org แล้วติ๊ก 'Add python.exe to PATH'")
        return False
    print("  [ok] ใช้ได้")
    return True


def install_packages() -> None:
    step(2, "ลงไลบรารี (requirements.txt)")
    if not ask("  ลง/อัปเดตไลบรารีตอนนี้ไหม (ใช้เน็ต ประมาณ 2-5 นาที)"):
        print("  ข้าม")
        return
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-r",
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
    print("  วิธีแก้: ขอสิทธิ์โฟลเดอร์ Cue_IE_PD แล้วใน OneDrive บนเว็บกด 'Add shortcut to My files'")
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


def check_users() -> None:
    step(4, "ผู้ใช้สำหรับล็อกอินแดชบอร์ด")
    if os.path.exists(SECRETS):
        print("  [ok] มีไฟล์ผู้ใช้แล้ว (.streamlit/secrets.toml)")
        return
    print("  ยังไม่มีไฟล์ผู้ใช้ — ไฟล์นี้ไม่อยู่บน GitHub โดยตั้งใจ (เก็บค่าแฮชรหัสผ่าน)")
    print("  ทางเลือก: ขอไฟล์ secrets.toml จากคนดูแลเดิมมาวางที่โฟลเดอร์ .streamlit")
    print("           หรือสร้างผู้ใช้ใหม่ตอนนี้")
    if ask("  สร้างผู้ใช้ใหม่ตอนนี้ไหม"):
        subprocess.run([sys.executable, os.path.join(HERE, "manage_users.py")], cwd=HERE)


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
    if not check_python():
        return
    install_packages()
    setup_data_folder()
    check_users()
    make_startup_link()
    start_now()
    print("\nขั้นต่อไป")
    print("  - ให้คนอื่นในวง LAN เข้าดูได้: คลิกขวา เปิด_firewall_dashboards.bat > Run as administrator")
    print("  - ตรวจว่าระบบปกติ: ดับเบิลคลิก ตรวจสุขภาพระบบ.bat")
    print("  - คู่มือเต็ม: คู่มือส่งมอบระบบ.md")


if __name__ == "__main__":
    main()
