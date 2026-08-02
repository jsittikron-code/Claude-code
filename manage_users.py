"""
จัดการผู้ใช้ของแดชบอร์ด — เพิ่ม / เปลี่ยนรหัส / ลบ ผู้ใช้
----------------------------------------------------------
รันด้วย:  python manage_users.py       (หรือดับเบิลคลิก จัดการผู้ใช้.bat)

เขียนผลลงไฟล์ .streamlit/secrets.toml โดยเก็บรหัสเป็นค่าแฮช PBKDF2
ไม่เก็บรหัสจริง — ถึงมีคนเปิดไฟล์อ่านก็ย้อนกลับเป็นรหัสไม่ได้
"""

import getpass
import os
import re
import sys

from auth import hash_password

SECRETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            ".streamlit", "secrets.toml")

HEADER = """# ข้อมูลผู้ใช้ของแดชบอร์ด — ไฟล์นี้อยู่ใน .gitignore จะไม่ถูก push ขึ้น git
#
# รหัสผ่านเก็บเป็นค่าแฮช PBKDF2-HMAC-SHA256 (มี salt สุ่มรายคน) ไม่ใช่รหัสจริง
# แก้ไฟล์นี้ด้วยมือไม่ได้ — ให้รัน  python manage_users.py  แทน
"""


def read_users() -> dict:
    """อ่าน {ชื่อผู้ใช้: ค่าที่เก็บ} จากไฟล์ (รองรับรูปแบบเก่า [auth] ด้วย)"""
    if not os.path.exists(SECRETS_PATH):
        return {}
    with open(SECRETS_PATH, encoding="utf-8") as f:
        text = f.read()

    users, section = {}, None
    legacy = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            section = s.strip("[]").strip()
            continue
        m = re.match(r'^"?([^"=]+?)"?\s*=\s*"(.*)"\s*$', s)
        if not m:
            continue
        key, val = m.group(1).strip(), m.group(2)
        if section == "credentials":
            users[key] = val
        elif section == "auth":
            legacy[key] = val

    if not users and {"username", "password"} <= legacy.keys():
        print("พบไฟล์รูปแบบเก่า (รหัสเป็นข้อความธรรมดา) — จะอัปเกรดเป็นแบบเข้ารหัสให้")
        users[legacy["username"]] = hash_password(legacy["password"])
    return users


def write_users(users: dict):
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    lines = [HEADER, "[credentials]"]
    for name, val in sorted(users.items()):
        lines.append(f'"{name}" = "{val}"')
    with open(SECRETS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n✅ บันทึกแล้ว: {SECRETS_PATH}  (ผู้ใช้ทั้งหมด {len(users)} คน)")


def ask_password() -> str | None:
    while True:
        pw = getpass.getpass("  รหัสผ่านใหม่ (พิมพ์แล้วจะไม่ขึ้นบนจอ): ")
        if len(pw) < 4:
            print("  ⚠️ รหัสสั้นเกินไป ต้องอย่างน้อย 4 ตัวอักษร")
            continue
        pw2 = getpass.getpass("  พิมพ์รหัสอีกครั้งเพื่อยืนยัน: ")
        if pw != pw2:
            print("  ⚠️ รหัสไม่ตรงกัน ลองใหม่")
            continue
        return pw


def main():
    print("=" * 60)
    print("  จัดการผู้ใช้แดชบอร์ด — ฝ่ายซ่อมบำรุงรักษา")
    print("=" * 60)

    users = read_users()
    while True:
        print(f"\nผู้ใช้ปัจจุบัน ({len(users)} คน):")
        if users:
            for i, name in enumerate(sorted(users), 1):
                kind = "เข้ารหัสแล้ว" if users[name].startswith("pbkdf2") else "⚠️ ข้อความธรรมดา"
                print(f"  {i}. {name}   [{kind}]")
        else:
            print("  (ยังไม่มีผู้ใช้)")

        print("\nเลือกทำอะไร:")
        print("  1) เพิ่มผู้ใช้ใหม่ / เปลี่ยนรหัสผู้ใช้เดิม")
        print("  2) ลบผู้ใช้")
        print("  3) บันทึกแล้วออก")
        print("  4) ออกโดยไม่บันทึก")
        choice = input("พิมพ์เลข: ").strip()

        if choice == "1":
            name = input("  ชื่อผู้ใช้: ").strip()
            if not name:
                print("  ⚠️ ต้องใส่ชื่อผู้ใช้")
                continue
            if name in users:
                print(f"  (มีผู้ใช้ '{name}' อยู่แล้ว — จะเปลี่ยนรหัสให้)")
            pw = ask_password()
            users[name] = hash_password(pw)
            print(f"  ✅ ตั้งรหัสให้ '{name}' เรียบร้อย")

        elif choice == "2":
            name = input("  ชื่อผู้ใช้ที่จะลบ: ").strip()
            if name in users:
                if len(users) == 1:
                    print("  ⚠️ ลบไม่ได้ — ต้องเหลือผู้ใช้อย่างน้อย 1 คน")
                else:
                    del users[name]
                    print(f"  ✅ ลบ '{name}' แล้ว")
            else:
                print(f"  ⚠️ ไม่พบผู้ใช้ '{name}'")

        elif choice == "3":
            if not users:
                print("  ⚠️ ต้องมีผู้ใช้อย่างน้อย 1 คนก่อนบันทึก")
                continue
            write_users(users)
            print("รีสตาร์ทแดชบอร์ดเพื่อให้รหัสใหม่มีผล")
            return

        elif choice == "4":
            print("ออกโดยไม่บันทึก")
            return

        else:
            print("  ⚠️ เลือกได้เฉพาะ 1-4")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nยกเลิก")
        sys.exit(1)
