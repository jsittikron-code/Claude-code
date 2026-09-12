"""ความก้าวหน้าของผู้เรียน — XP, บทเรียนที่จบ, แบบฝึกหัดที่ผ่าน, การทบทวนแบบเว้นระยะ
======================================================================================

เก็บเป็นไฟล์ JSON หนึ่งไฟล์ต่อผู้เรียนหนึ่งคน ในโฟลเดอร์ py_progress/
(โครงเดียวกับ Power BI Academy เพื่อให้ย้าย/สำรอง/อ่านด้วยตาได้ง่าย ไม่ต้องมีฐานข้อมูล)

การทบทวนแบบเว้นระยะใช้ระบบกล่อง Leitner 5 ระดับ
  ตอบถูก → เลื่อนขึ้นกล่องถัดไป (ทบทวนห่างขึ้น)   ตอบผิด → กลับกล่อง 1 (ทบทวนพรุ่งนี้)
  ระยะห่างของกล่อง 1-5 = 1, 2, 4, 8, 16 วัน
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta

PROGRESS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "py_progress")

LEITNER_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}

XP_LESSON = 20
XP_QUIZ_CORRECT = 10
XP_CODE_SOLVED = 40          # แบบฝึกหัดเขียนโค้ด
XP_PROJECT_SOLVED = 80       # โจทย์งานจริง
XP_EXAM_PASS = 150

LEVELS = [
    (0, "ผู้เริ่มต้น"),
    (300, "เขียนสคริปต์สั้นได้"),
    (900, "เขียนโปรแกรมใช้งานเองได้"),
    (1800, "จัดการข้อมูลด้วย pandas ได้"),
    (3200, "ทำเครื่องมือให้ทีมใช้ได้"),
    (5000, "ผู้เชี่ยวชาญ Python สายงานโรงงาน"),
]

BADGES = {
    "first_lesson": ("ก้าวแรก", "จบบทเรียนแรก"),
    "ten_lessons": ("ติดลม", "จบครบ 10 บทเรียน"),
    "all_lessons": ("อ่านจบเล่ม", "จบทุกบทเรียนในหลักสูตร"),
    "first_code": ("รันผ่านแล้ว!", "ผ่านแบบฝึกหัดเขียนโค้ดข้อแรก"),
    "code_ten": ("มือเขียนโค้ด", "ผ่านแบบฝึกหัด 10 ข้อ"),
    "code_all": ("ผ่านครบทุกข้อ", "ผ่านแบบฝึกหัดเขียนโค้ดครบทุกข้อ"),
    "no_hint": ("ไม่ง้อคำใบ้", "ผ่านแบบฝึกหัด 5 ข้อติดโดยไม่เปิดคำใบ้"),
    "one_shot": ("ยิงทีเดียวเข้า", "ผ่านแบบฝึกหัดตั้งแต่ส่งครั้งแรก 5 ข้อ"),
    "debugger": ("นักไล่บั๊ก", "ใช้ตัวไล่โค้ดทีละบรรทัด 10 ครั้ง"),
    "streak_3": ("สามวันติด", "เข้าเรียนติดต่อกัน 3 วัน"),
    "streak_7": ("เจ็ดวันติด", "เข้าเรียนติดต่อกัน 7 วัน"),
    "quiz_50": ("ตอบถูก 50", "ตอบคำถามถูกสะสม 50 ข้อ"),
    "project": ("ทำของใช้จริง", "ทำโจทย์งานจริงสำเร็จข้อแรก"),
    "exam_pass": ("ผ่านข้อสอบรวม", "ทำข้อสอบรวมได้ 70% ขึ้นไป"),
    "exam_ace": ("เกือบเต็ม", "ทำข้อสอบรวมได้ 90% ขึ้นไป"),
}


def _today() -> str:
    return date.today().isoformat()


def _blank() -> dict:
    return {
        "user": "",
        "xp": 0,
        "created": _today(),
        "last_seen": "",
        "streak": 0,
        "best_streak": 0,
        "lessons": {},        # lesson_id -> วันที่จบ
        "code": {},           # exercise_id -> {solved, attempts, hint_used, first_solved, best_code}
        "quiz": {},           # question_id -> {box, due, right, wrong, last}
        "quiz_totals": {"right": 0, "wrong": 0},
        "exams": [],          # [{date, score, total, pct, by_topic}]
        "badges": {},         # badge_id -> วันที่ได้
        "traces": 0,          # จำนวนครั้งที่ใช้ตัวไล่โค้ด
        "streak_flawless": 0,  # ผ่านติดกันโดยไม่เปิดคำใบ้
        "one_shots": 0,       # ผ่านตั้งแต่ส่งครั้งแรก
        "notes": "",
    }


def _safe_name(user: str) -> str:
    """กันชื่อผู้ใช้ที่มีอักขระประหลาดไม่ให้หลุดออกนอกโฟลเดอร์ progress"""
    s = re.sub(r"[^\w\-. ]", "_", (user or "guest").strip(), flags=re.UNICODE)
    return (s or "guest")[:60]


def path_for(user: str) -> str:
    return os.path.join(PROGRESS_DIR, f"{_safe_name(user)}.json")


def load(user: str) -> dict:
    p = path_for(user)
    data = _blank()
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                saved = json.load(fh)
            if isinstance(saved, dict):
                data.update(saved)
                for k, v in _blank().items():          # เติมคีย์ที่เพิ่มมาทีหลัง
                    data.setdefault(k, v)
        except (json.JSONDecodeError, OSError):
            pass
    data["user"] = user
    return data


def save(data: dict) -> None:
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    p = path_for(data.get("user", "guest"))
    # เขียนไฟล์ชั่วคราวก่อนแล้วสลับ กันไฟล์พังถ้าปิดแอปกลางคัน
    fd, tmp = tempfile.mkstemp(dir=PROGRESS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ---------------------------------------------------------------------------
# สถิติรายวัน / ระดับ
# ---------------------------------------------------------------------------
def touch(data: dict) -> dict:
    """เรียกทุกครั้งที่เปิดแอป — อัปเดตวันเข้าใช้และจำนวนวันติดต่อกัน"""
    today = _today()
    last = data.get("last_seen") or ""
    if last == today:
        return data
    if last:
        try:
            gap = (date.fromisoformat(today) - date.fromisoformat(last)).days
        except ValueError:
            gap = 99
        data["streak"] = data.get("streak", 0) + 1 if gap == 1 else 1
    else:
        data["streak"] = 1
    data["best_streak"] = max(data.get("best_streak", 0), data["streak"])
    data["last_seen"] = today
    _check_badges(data)
    return data


def level_of(xp: int) -> tuple[str, int, int]:
    """คืน (ชื่อระดับ, XP ที่เริ่มระดับนี้, XP ที่ต้องถึงเพื่อขึ้นระดับถัดไป)"""
    name, floor = LEVELS[0][1], 0
    nxt = LEVELS[1][0]
    for i, (need, label) in enumerate(LEVELS):
        if xp >= need:
            name, floor = label, need
            nxt = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else need
    return name, floor, nxt


def add_xp(data: dict, amount: int) -> None:
    data["xp"] = max(0, int(data.get("xp", 0)) + int(amount))


# ---------------------------------------------------------------------------
# บทเรียน
# ---------------------------------------------------------------------------
def complete_lesson(data: dict, lesson_id: str) -> bool:
    """คืน True ถ้าเพิ่งจบครั้งแรก (จะได้ XP)"""
    if lesson_id in data["lessons"]:
        return False
    data["lessons"][lesson_id] = _today()
    add_xp(data, XP_LESSON)
    _check_badges(data)
    return True


def uncomplete_lesson(data: dict, lesson_id: str) -> None:
    if data["lessons"].pop(lesson_id, None) is not None:
        add_xp(data, -XP_LESSON)


# ---------------------------------------------------------------------------
# แบบฝึกหัดเขียนโค้ด
# ---------------------------------------------------------------------------
def record_code(data: dict, ex_id: str, solved: bool, hint_used: bool,
                code: str = "", project: bool = False) -> bool:
    """บันทึกการส่งคำตอบหนึ่งครั้ง คืน True ถ้านี่คือครั้งแรกที่ผ่าน"""
    rec = data["code"].setdefault(ex_id, {"solved": False, "attempts": 0,
                                          "hint_used": False, "first_solved": "",
                                          "best_code": ""})
    rec["attempts"] += 1
    rec["hint_used"] = rec["hint_used"] or hint_used
    first = False
    if solved and not rec["solved"]:
        rec["solved"] = True
        rec["first_solved"] = _today()
        base = XP_PROJECT_SOLVED if project else XP_CODE_SOLVED
        add_xp(data, base // 2 if rec["hint_used"] else base)
        first = True
        if rec["attempts"] == 1 and not rec["hint_used"]:
            data["one_shots"] = data.get("one_shots", 0) + 1
    if solved:
        rec["best_code"] = code
        data["streak_flawless"] = 0 if rec["hint_used"] else data.get("streak_flawless", 0) + 1
    _check_badges(data)
    return first


def record_trace(data: dict) -> None:
    data["traces"] = data.get("traces", 0) + 1
    _check_badges(data)


def solved_ids(data: dict) -> set[str]:
    return {k for k, v in data.get("code", {}).items() if v.get("solved")}


# ---------------------------------------------------------------------------
# แบบทดสอบ + การทบทวนแบบเว้นระยะ
# ---------------------------------------------------------------------------
def record_quiz(data: dict, qid: str, correct: bool) -> None:
    rec = data["quiz"].setdefault(qid, {"box": 1, "due": _today(), "right": 0,
                                        "wrong": 0, "last": ""})
    if correct:
        rec["right"] += 1
        rec["box"] = min(5, rec.get("box", 1) + 1)
        data["quiz_totals"]["right"] += 1
        add_xp(data, XP_QUIZ_CORRECT)
    else:
        rec["wrong"] += 1
        rec["box"] = 1
        data["quiz_totals"]["wrong"] += 1
    rec["last"] = _today()
    rec["due"] = (date.today() + timedelta(days=LEITNER_DAYS[rec["box"]])).isoformat()
    _check_badges(data)


def due_questions(data: dict, all_ids: list[str]) -> list[str]:
    """คำถามที่ถึงกำหนดทบทวนวันนี้ (เรียงจากที่ค้างนานสุด)"""
    today = _today()
    due = [(rec.get("due", today), qid) for qid, rec in data["quiz"].items()
           if qid in all_ids and rec.get("due", today) <= today]
    return [qid for _, qid in sorted(due)]


def record_exam(data: dict, score: int, total: int, by_topic: dict) -> None:
    pct = round(100 * score / total, 1) if total else 0.0
    data["exams"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": score, "total": total, "pct": pct, "by_topic": by_topic,
    })
    if pct >= 70:
        add_xp(data, XP_EXAM_PASS)
    _check_badges(data)


# ---------------------------------------------------------------------------
# เหรียญตรา
# ---------------------------------------------------------------------------
def _award(data: dict, badge: str) -> None:
    if badge in BADGES and badge not in data["badges"]:
        data["badges"][badge] = _today()


def _check_badges(data: dict) -> None:
    n_lesson = len(data.get("lessons", {}))
    n_code = len(solved_ids(data))
    if n_lesson >= 1:
        _award(data, "first_lesson")
    if n_lesson >= 10:
        _award(data, "ten_lessons")
    if n_code >= 1:
        _award(data, "first_code")
    if n_code >= 10:
        _award(data, "code_ten")
    if data.get("streak_flawless", 0) >= 5:
        _award(data, "no_hint")
    if data.get("one_shots", 0) >= 5:
        _award(data, "one_shot")
    if data.get("traces", 0) >= 10:
        _award(data, "debugger")
    if data.get("streak", 0) >= 3:
        _award(data, "streak_3")
    if data.get("streak", 0) >= 7:
        _award(data, "streak_7")
    if data.get("quiz_totals", {}).get("right", 0) >= 50:
        _award(data, "quiz_50")
    for e in data.get("exams", []):
        if e.get("pct", 0) >= 70:
            _award(data, "exam_pass")
        if e.get("pct", 0) >= 90:
            _award(data, "exam_ace")


def check_completion_badges(data: dict, total_lessons: int, total_code: int,
                            project_ids: set[str] | None = None) -> None:
    """เหรียญที่ต้องรู้จำนวนรวมของหลักสูตร (เรียกจากหน้าที่รู้ตัวเลขนี้)"""
    if total_lessons and len(data.get("lessons", {})) >= total_lessons:
        _award(data, "all_lessons")
    solved = solved_ids(data)
    if total_code and len(solved) >= total_code:
        _award(data, "code_all")
    if project_ids and solved & project_ids:
        _award(data, "project")


def reset(user: str) -> dict:
    data = _blank()
    data["user"] = user
    save(data)
    return data
