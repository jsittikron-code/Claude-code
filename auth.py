"""
ระบบล็อกอินกลาง — ใช้ร่วมกันทุกแดชบอร์ดในโฟลเดอร์นี้
-------------------------------------------------------
เก็บรหัสผ่านเป็นค่าแฮชแบบ PBKDF2-HMAC-SHA256 (มี salt สุ่มรายคน)
ไม่ได้เก็บรหัสจริง — เปิดไฟล์ secrets.toml อ่านก็ย้อนกลับเป็นรหัสไม่ได้

รูปแบบไฟล์ .streamlit/secrets.toml:

    [credentials]
    "Admin.IE" = "pbkdf2_sha256$200000$<salt hex>$<hash hex>"

เพิ่ม/เปลี่ยน/ลบผู้ใช้: รัน  python manage_users.py  (หรือดับเบิลคลิก จัดการผู้ใช้.bat)

วิธีใช้ในแอป — วางต่อจาก st.set_page_config():

    import auth
    auth.check_login("ชื่อแดชบอร์ด")

    with st.sidebar:
        auth.sidebar_user_box()
"""

import hashlib
import hmac
import os
import time

import streamlit as st

PBKDF2_ITERATIONS = 200_000
MAX_ATTEMPTS = 5          # ผิดเกินจำนวนนี้ → ล็อกชั่วคราว
LOCKOUT_SECONDS = 300     # ระยะเวลาล็อก (5 นาที)


# ---------------------------------------------------------------------------
# แฮชรหัสผ่าน
# ---------------------------------------------------------------------------
def hash_password(password: str, salt: bytes | None = None) -> str:
    """สร้างสตริงแฮชสำหรับเก็บใน secrets.toml"""
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                             PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """ตรวจรหัสผ่านกับค่าที่เก็บไว้ — รองรับทั้งแบบแฮชและแบบข้อความธรรมดา (ของเก่า)"""
    if not isinstance(stored, str):
        return False
    if not stored.startswith("pbkdf2_sha256$"):
        # ไฟล์รุ่นเก่าที่ยังเก็บรหัสเป็นข้อความธรรมดา — ยังเทียบได้ แต่ควรอัปเกรด
        return hmac.compare_digest(password, stored)
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# ---------------------------------------------------------------------------
# อ่านรายชื่อผู้ใช้จาก secrets.toml
# ---------------------------------------------------------------------------
def _load_credentials() -> tuple[dict, bool]:
    """คืน ({ชื่อผู้ใช้: ค่าที่เก็บไว้}, เป็นรูปแบบเก่าหรือไม่)"""
    try:
        creds = dict(st.secrets["credentials"])
        if creds:
            return creds, False
    except (FileNotFoundError, KeyError):
        pass
    # รองรับไฟล์รุ่นเก่าที่ใช้หัวข้อ [auth] username/password
    try:
        auth = st.secrets["auth"]
        return {auth["username"]: auth["password"]}, True
    except (FileNotFoundError, KeyError):
        return {}, False


def _locked_out() -> int:
    """คืนจำนวนวินาทีที่ยังต้องรอ ถ้าไม่ถูกล็อกคืน 0"""
    until = st.session_state.get("_auth_locked_until", 0)
    remaining = int(until - time.time())
    return max(0, remaining)


# ---------------------------------------------------------------------------
# ด่านล็อกอิน
# ---------------------------------------------------------------------------
def check_login(app_title: str = "") -> bool:
    """คืน True เมื่อล็อกอินแล้ว มิฉะนั้นแสดงฟอร์มแล้วหยุดหน้าไว้ตรงนั้น"""
    if st.session_state.get("_auth_ok"):
        return True

    creds, legacy = _load_credentials()
    if not creds:
        st.error(
            "ไม่พบข้อมูลผู้ใช้ในไฟล์ `.streamlit/secrets.toml`\n\n"
            "สร้างผู้ใช้ด้วยการรัน `python manage_users.py` "
            "(หรือดับเบิลคลิก `จัดการผู้ใช้.bat`)"
        )
        st.stop()

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("### 🔒 เข้าสู่ระบบ")
            if app_title:
                st.caption(app_title)

            wait = _locked_out()
            if wait:
                st.error(
                    f"ใส่รหัสผิดเกิน {MAX_ATTEMPTS} ครั้ง — "
                    f"กรุณารออีก {wait // 60} นาที {wait % 60} วินาที"
                )
                st.stop()

            with st.form("login_form"):
                user = st.text_input("ชื่อผู้ใช้", autocomplete="username")
                pw = st.text_input("รหัสผ่าน", type="password",
                                   autocomplete="current-password")
                ok = st.form_submit_button("เข้าสู่ระบบ", width="stretch")

            if ok:
                stored = creds.get(user.strip())
                # ถึงไม่มีชื่อผู้ใช้นี้ก็ยังคำนวณแฮชหลอกให้เสียเวลาเท่ากัน
                # ผู้บุกรุกจะแยกไม่ออกว่า "ไม่มีชื่อนี้" หรือ "รหัสผิด"
                valid = verify_password(pw, stored) if stored else (
                    verify_password(pw, hash_password("x")) and False
                )
                if valid:
                    st.session_state["_auth_ok"] = True
                    st.session_state["_auth_user"] = user.strip()
                    st.session_state.pop("_auth_attempts", None)
                    st.session_state.pop("_auth_locked_until", None)
                    st.rerun()
                else:
                    n = st.session_state.get("_auth_attempts", 0) + 1
                    st.session_state["_auth_attempts"] = n
                    if n >= MAX_ATTEMPTS:
                        st.session_state["_auth_locked_until"] = (
                            time.time() + LOCKOUT_SECONDS
                        )
                        st.error(
                            f"ใส่รหัสผิดครบ {MAX_ATTEMPTS} ครั้ง — "
                            f"ล็อกการเข้าใช้ {LOCKOUT_SECONDS // 60} นาที"
                        )
                    else:
                        time.sleep(1.5)   # หน่วงกันเดารหัสรัวๆ
                        st.error(
                            "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง "
                            f"(เหลืออีก {MAX_ATTEMPTS - n} ครั้ง)"
                        )
            if legacy:
                st.caption(
                    "⚠️ ไฟล์ secrets.toml ยังเก็บรหัสเป็นข้อความธรรมดา — "
                    "รัน `python manage_users.py` เพื่ออัปเกรดเป็นแบบเข้ารหัส"
                )
    st.stop()


def current_user() -> str:
    return st.session_state.get("_auth_user", "—")


def logout():
    for k in ("_auth_ok", "_auth_user", "_auth_attempts", "_auth_locked_until"):
        st.session_state.pop(k, None)


def sidebar_user_box():
    """กล่องแสดงผู้ใช้ปัจจุบัน + ปุ่มออกจากระบบ (เรียกภายใน with st.sidebar)"""
    st.caption(f"👤 เข้าใช้งานโดย **{current_user()}**")
    if st.button("🚪 ออกจากระบบ", width="stretch"):
        logout()
        st.rerun()
    st.markdown("---")
