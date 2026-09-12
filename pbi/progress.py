"""ระบบเก็บความก้าวหน้าของผู้เรียน — XP, บทเรียนที่จบ, สถิติแบบทดสอบ, การทบทวนแบบเว้นระยะ
============================================================================================

เก็บเป็นไฟล์ JSON หนึ่งไฟล์ต่อผู้เรียนหนึ่งคน ในโฟลเดอร์ pbi_progress/
ไม่ใช้ฐานข้อมูล เพราะแอปนี้รันบนเครื่องเดียวและต้องการให้ย้าย/สำรองไฟล์ได้ง่าย

การทบทวนแบบเว้นระยะ (spaced repetition) ใช้ระบบกล่อง Leitner 5 ระดับ
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
                            "pbi_progress")

LEITNER_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}

XP_LESSON = 20
XP_QUIZ_CORRECT = 10
XP_DAX_SOLVED = 40
XP_PQ_SOLVED = 30
XP_EXAM_PASS = 150

LEVELS = [
    (0, "ผู้เริ่มต้น"),
    (300, "ผู้ฝึกหัด"),
    (900, "นักวิเคราะห์"),
    (1800, "นักพัฒนารายงาน"),
    (3200, "ผู้เชี่ยวชาญ DAX"),
    (5000, "สถาปนิกข้อมูล"),
]

BADGES = {
    "first_lesson": ("ก้าวแรก", "จบบทเรียนแรก"),
    "ten_lessons": ("ติดลม", "จบครบ 10 บทเรียน"),
    "all_lessons": ("อ่านจบเล่ม", "จบทุกบทเรียนในหลักสูตร"),
    "first_dax": ("เขียน DAX ได้แล้ว", "ผ่านแบบฝึกหัด DAX ข้อแรก"),
    "dax_ten": ("มือ DAX", "ผ่านแบบฝึกหัด DAX 10 ข้อ"),
    "dax_all": ("เจ้าสำนัก DAX", "ผ่านแบบฝึกหัด DAX ครบทุกข้อ"),
    "no_hint": ("ไม่ง้อคำใบ้", "ผ่านแบบฝึกหัด DAX 5 ข้อติดโดยไม่เปิดคำใบ้"),
    "streak_3": ("สามวันติด", "เข้าเรียนติดต่อกัน 3 วัน"),
    "streak_7": ("เจ็ดวันติด", "เข้าเรียนติดต่อกัน 7 วัน"),
    "quiz_50": ("ตอบถูก 50", "ตอบคำถามถูกสะสม 50 ข้อ"),
    "exam_pass": ("ผ่านข้อสอบจำลอง", "ทำข้อสอบจำลอง PL-300 ได้ 70% ขึ้นไป"),
    "exam_ace": ("คะแนนเต็มแทบทุกข้อ", "ทำข้อสอบจำลองได้ 90% ขึ้นไป"),
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
        "dax": {},            # exercise_id -> {solved, attempts, hint_used, first_solved}
        "pq": {},             # exercise_id -> {solved, attempts}
        "quiz": {},           # question_id -> {box, due, right, wrong, last}
        "quiz_totals": {"right": 0, "wrong": 0},
        "exams": [],          # [{date, score, total, pct, by_domain}]
        "badges": {},         # badge_id -> วันที่ได้
        "notes": "",
        "streak_flawless": 0,   # จำนวนข้อ DAX ที่ผ่านติดกันโดยไม่เปิดคำใบ้
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
    # เขียนลงไฟล์ชั่วคราวก่อนแล้วค่อยสลับ กันไฟล์พังถ้าปิดแอปกลางคัน
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
# สถิติต่อเนื่องรายวัน
# ---------------------------------------------------------------------------
def touch(data: dict) -> dict:
    """เรียกทุกครั้งที่เปิดแอป — อัปเดตวันเข้าใช้และสถิติวันติดต่อกัน"""
    today = _today()
    last = data.get("last_seen") or ""
    if last == today:
        return data
    if last:
        gap = (date.fromisoformat(today) - date.fromisoformat(last)).days
        data["streak"] = data.get("streak", 0) + 1 if gap == 1 else 1
    else:
        data["streak"] = 1
    data["best_streak"] = max(data.get("best_streak", 0), data["streak"])
    data["last_seen"] = today
    _check_badges(data)
    return data


def level_of(xp: int) -> tuple[str, int, int]:
    """คืน (ชื่อระดับ, XP ที่เริ่มระดับนี้, XP ที่ต้องใช้ขึ้นระดับถัดไป)"""
    name, floor = LEVELS[0][1], 0
    nxt = LEVELS[1][0]
    for i, (need, label) in enumerate(LEVELS):
        if xp >= need:
            name, floor = label, need
            nxt = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else need
    return name, floor, nxt


def add_xp(data: dict, amount: int) -> None:
    data["xp"] = int(data.get("xp", 0)) + int(amount)


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
# แบบฝึกหัด DAX / Power Query
# ---------------------------------------------------------------------------
def record_dax(data: dict, ex_id: str, solved: bool, hint_used: bool) -> bool:
    rec = data["dax"].setdefault(ex_id, {"solved": False, "attempts": 0,
                                         "hint_used": False, "first_solved": ""})
    rec["attempts"] += 1
    rec["hint_used"] = rec["hint_used"] or hint_used
    first = False
    if solved and not rec["solved"]:
        rec["solved"] = True
        rec["first_solved"] = _today()
        add_xp(data, XP_DAX_SOLVED if not rec["hint_used"] else XP_DAX_SOLVED // 2)
        first = True
    if solved:
        data["streak_flawless"] = 0 if rec["hint_used"] else data.get("streak_flawless", 0) + 1
    _check_badges(data)
    return first


def record_pq(data: dict, ex_id: str, solved: bool) -> bool:
    rec = data["pq"].setdefault(ex_id, {"solved": False, "attempts": 0})
    rec["attempts"] += 1
    first = False
    if solved and not rec["solved"]:
        rec["solved"] = True
        add_xp(data, XP_PQ_SOLVED)
        first = True
    _check_badges(data)
    return first


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
    """รายการคำถามที่ถึงกำหนดทบทวนวันนี้ (เรียงจากที่ค้างนานสุด)"""
    today = _today()
    due = [(rec.get("due", today), qid) for qid, rec in data["quiz"].items()
           if qid in all_ids and rec.get("due", today) <= today]
    return [qid for _, qid in sorted(due)]


def record_exam(data: dict, score: int, total: int, by_domain: dict) -> None:
    pct = round(100 * score / total, 1) if total else 0.0
    data["exams"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": score, "total": total, "pct": pct, "by_domain": by_domain,
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


def _check_badges(data: dict, total_lessons: int | None = None,
                  total_dax: int | None = None) -> None:
    n_lesson = len(data.get("lessons", {}))
    n_dax = sum(1 for r in data.get("dax", {}).values() if r.get("solved"))
    if n_lesson >= 1:
        _award(data, "first_lesson")
    if n_lesson >= 10:
        _award(data, "ten_lessons")
    if n_dax >= 1:
        _award(data, "first_dax")
    if n_dax >= 10:
        _award(data, "dax_ten")
    if data.get("streak_flawless", 0) >= 5:
        _award(data, "no_hint")
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


def check_completion_badges(data: dict, total_lessons: int, total_dax: int) -> None:
    """ตรวจเหรียญที่ต้องรู้จำนวนรวมของหลักสูตร (เรียกจากหน้าแอปที่รู้ตัวเลขนี้)"""
    if total_lessons and len(data.get("lessons", {})) >= total_lessons:
        _award(data, "all_lessons")
    solved = sum(1 for r in data.get("dax", {}).values() if r.get("solved"))
    if total_dax and solved >= total_dax:
        _award(data, "dax_all")


def reset(user: str) -> dict:
    data = _blank()
    data["user"] = user
    save(data)
    return data
