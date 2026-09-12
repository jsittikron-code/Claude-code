"""หลักสูตร Python — ประกอบโมดูลทั้งหมดและสร้างดัชนีที่หน้าเว็บใช้
==================================================================

ลำดับหลักสูตรเรียงตาม "ลำดับที่ใช้งานได้เร็วที่สุด" คือ
พื้นฐาน → ตัดสินใจ/วนซ้ำ → โครงสร้างข้อมูล → ฟังก์ชัน → ไฟล์ → ดีบัก → pandas → ส่งมอบ

โมดูล 1-4 คือแกนของภาษา (ต้องแน่นก่อน) · 5-6 คือทักษะทำงานกับของจริง ·
7-8 คือจุดที่เปลี่ยนจาก "เขียนโค้ดเป็น" เป็น "ทำเครื่องมือให้ทีมใช้ได้"
"""

from __future__ import annotations

from pyacad.lessons import mod1, mod2, mod3, mod4, mod5, mod6, mod7, mod8

MODULES: list[dict] = [m.MODULE for m in (mod1, mod2, mod3, mod4,
                                          mod5, mod6, mod7, mod8)]

MODULE_BY_ID = {m["id"]: m for m in MODULES}

# แนบ module_id เข้าไปในบทเรียนแต่ละบท เพื่อให้ปุ่ม "บทถัดไป" ข้ามโมดูลได้
ALL_LESSONS: list[dict] = []
for _m in MODULES:
    for _le in _m["lessons"]:
        _le["module_id"] = _m["id"]
        _le["module_title"] = _m["title"]
        ALL_LESSONS.append(_le)

LESSON_BY_ID = {le["id"]: le for le in ALL_LESSONS}

TOTAL_LESSONS = len(ALL_LESSONS)
TOTAL_MINUTES = sum(le["minutes"] for le in ALL_LESSONS)


def module_progress(module: dict, done: set[str]) -> tuple[int, int]:
    """คืน (จำนวนบทที่เรียนจบ, จำนวนบททั้งหมด) ของโมดูลนี้"""
    ids = [le["id"] for le in module["lessons"]]
    return sum(1 for i in ids if i in done), len(ids)


def next_lesson(done: set[str]) -> dict | None:
    """บทถัดไปที่ควรเรียน — บทแรกที่ยังไม่จบตามลำดับหลักสูตร"""
    for le in ALL_LESSONS:
        if le["id"] not in done:
            return le
    return None


def lesson_index(lesson_id: str) -> int:
    for i, le in enumerate(ALL_LESSONS):
        if le["id"] == lesson_id:
            return i
    return -1


def all_quiz_ids() -> list[str]:
    ids = []
    for le in ALL_LESSONS:
        ids.extend(le.get("quiz", []))
    return ids
