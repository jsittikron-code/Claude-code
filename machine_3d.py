"""โมเดล 3D ตัวแทนเครื่องจักร — ใช้ร่วมกันในหน้าโปรไฟล์ของแดชบอร์ด 8503 และ 8505

ภาพที่แสดงเป็น "รูปแบบสัญลักษณ์" ของเครื่องแต่ละชนิด (เลื่อยคาน, CNC, ปิดขอบ, เพรส ฯลฯ)
ไม่ใช่รูปจริงของเครื่องนั้น ๆ — จุดประสงค์คือให้คนดูรู้ทันทีว่าเป็นเครื่องประเภทไหน
และเห็นสถานะ (เดิน / ว่าง / หยุดซ่อม) จากการเคลื่อนไหวและเสาไฟสถานะ

ส่วนแสดงผลเป็น custom component (โฟลเดอร์ machine3d/ : index.html + engine.js + models.js
+ three.min.js r128 ที่เก็บไว้ในเครื่อง ไม่โหลดจากอินเทอร์เน็ต) ไฟล์นี้ทำแค่สองอย่าง
  1. classify() เดาชนิดโมเดลจากรหัส/ชื่อเครื่องในทะเบียน
  2. machine_3d() ส่งค่าไปให้คอมโพเนนต์วาด

การเพิ่มชนิดใหม่: เพิ่มตัวสร้างใน models.js แล้วเพิ่มกฎใน RULES ที่นี่
"""
from __future__ import annotations

import os
import re

import streamlit.components.v1 as components

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "machine3d")
_component = components.declare_component("machine3d", path=_DIR)

# สีประจำตระกูลเครื่อง (ตัวอักษรนำหน้ารหัส) — ใช้เป็นสีเน้นของโมเดลและพื้น
FAMILY_ACCENT = {
    "CT": "#2AA7B5", "EG": "#3CB371", "DL": "#4F7FB6", "LA": "#b56fd6", "PR": "#d9534f",
    "CO": "#e0a030", "PO": "#c8a200", "MO": "#8e7cc3", "GD": "#6c8ebf", "AC": "#5fa8d3",
    "BL": "#9aa4ae", "SM": "#e377c2", "WD": "#ff7f0e", "PG": "#8c564b", "BD": "#d9534f",
    "SF": "#3CB371", "GL": "#3CB371", "RO": "#9aa4ae", "AL": "#7f9cc9", "AD": "#9aa4ae",
    "MS": "#c8a200", "MB": "#c8a200", "SKL": "#c8a200",
}
DEFAULT_ACCENT = "#4f7fb6"

# กฎเดาชนิดจากชื่อเครื่อง (ตรวจตามลำดับ — กฎเฉพาะอยู่ก่อนกฎกว้าง)
# แต่ละข้อ: (regex บนชื่อตัวพิมพ์เล็ก, ชนิดโมเดล, ตัวเลือกย่อย)
# ตระกูลที่ชื่อเครื่องหลอกกฎได้ง่าย (เช่น "INDUSTRIAL" มีคำว่า dust, เครื่องดูดฝุ่น "ของเครื่องขัดขอบ")
# ให้ตัดสินจากตระกูลก่อนเลย
FAMILY_FORCE: dict[str, tuple[str, dict]] = {
    "BL": ("dust_collector", {}),
    "SM": ("sewing", {}),
}

RULES: list[tuple[str, str, dict]] = [
    (r"chiller|หล่อเย็น", "chiller", {}),
    (r"kuka|robot", "robot_welder", {}),
    (r"เลเชอร์|laser", "welder", {"laser": True}),
    (r"เชื่อม|weld", "welder", {}),
    (r"ปั๊มลม|ปั้มลม|อัดอากาศ|compressor", "compressor", {}),
    (r"dryer|อากาศแห้ง|ลมแห้ง", "air_dryer", {}),
    (r"^\s*(เครื่อง|ระบบ)?(ไซโล|ดูดฝุ่น)", "dust_collector", {}),
    (r"dust collector|ห้องเก็บฝุ่น", "dust_collector", {}),
    (r"พ่นสีอัตโนมัติ|cefla", "spray_line", {}),
    (r"อบสี|oven", "oven", {}),
    (r"พ่นสี|spray|booth", "spray_booth", {}),
    (r"conveyor|แท่นฟิตท่อ|ลำเลียง", "conveyor", {}),
    (r"จักร|sewing", "sewing", {}),
    (r"พันพาเลท|wrapping|wrap", "pallet_wrapper", {}),
    (r"รัดกล่อง|strap", "strapping", {}),
    (r"ห่อฟิล์ม|อบฟิล์ม|shrink", "shrink_tunnel", {}),
    (r"copy lathe|กลึงไม้", "lathe", {"wood": True}),
    (r"กลึง|lathe", "lathe", {}),
    (r"มิลลิ่ง|มิงลิ่ง|milling", "milling", {}),
    (r"ลับคม|grind", "grinder", {}),
    (r"ปิดขอบโค้ง|orbiter|manual edge|wap ?2001", "edge_curve", {}),
    (r"ปิดขอบ|edge ?band|eddeband|edge bander", "edge_bander", {}),
    (r"ห่อโค้ง|postform", "postformer", {}),
    (r"ทากาว|glue", "glue_spreader", {}),
    (r"hot ?press|membrane", "panel_press", {"hot": True}),
    (r"อัดเย็น|อัดไฮดรอลิค|hydraulic press|hydraulic 3 plate", "panel_press", {}),
    (r"พับเหล็ก|press brake|บากพับ", "press_brake", {}),
    (r"ดัด|bending|bender", "tube_bender", {}),
    (r"ปั๊ม|ปั้ม|press|punch", "metal_press", {}),
    (r"ขัดเงา|polish", "polisher", {"wheels": 2}),
    (r"ขัด|sand|deburr", "sander", {}),
    (r"ไสไม้|ใส 4 หน้า|planer|moulder|กบไฟฟ้า|ripsaw|rip saw", "moulder", {}),
    (r"cnc router|rover|nesting|เจาะขึ้นรูป", "cnc_router", {}),
    (r"skipper|6[- ]sided|6 ด้าน|eko\s+902|bjk", "cnc_drill", {}),
    (r"สว่าน|column dril|upright|ibarmia|strands|ตั้งพื้น|drilling machine|หัวเจาะ|tapping", "drill_press", {}),
    (r"globo|three ranged|3 หัว|maggi|magazine|mzb|jono|ksd|king", "multi_drill", {}),
    (r"holzma|hpp|hpl|selco|seclo|panel cutter|twin pusher|double ends", "beam_saw", {}),
    (r"band ?saw|brand saw|สายพาน|ต่อใบเลื่อย", "band_saw", {}),
    (r"ตัดเหล็ก|ตัดโลหะ|cold saw|อลูมิเนียม|auto cutting|double head|45 ?องศา", "miter_saw", {"metal": True}),
    (r"arm saw|radial|ตัดองศา|chopper", "miter_saw", {}),
    (r"เพลาตั้ง|เล้าเตอร์|เราเตอร์|เราว์เตอร์|เลาเตอร์|shaper|เซาะร่อง|feeder", "spindle_moulder", {}),
    (r"altendorf|casadei|juno|เลื่อย|ตัดซอย|ซอย|arbor|ตัด", "table_saw", {}),
    (r"lifter|ยก|พลิก", "lifter", {}),
]

# ถ้าชื่อไม่เข้ากฎไหน ใช้ตระกูล/รหัสนำหน้าตัดสิน (รวมหน่วยงานที่ไม่มีในทะเบียน)
FAMILY_DEFAULT: dict[str, tuple[str, dict]] = {
    "CT": ("table_saw", {}), "DL": ("drill_press", {}), "EG": ("edge_bander", {}),
    "AC": ("compressor", {}), "BL": ("dust_collector", {}), "CO": ("spray_booth", {}),
    "GD": ("lathe", {}), "LA": ("panel_press", {"hot": True}), "MO": ("spindle_moulder", {}),
    "PG": ("pallet_wrapper", {}), "PO": ("sander", {}), "PR": ("metal_press", {}),
    "SM": ("sewing", {}), "WD": ("welder", {}), "SF": ("postformer", {}), "GL": ("glue_spreader", {}),
    "RO": ("lifter", {}), "BD": ("tube_bender", {}),
    "AD": ("workbench", {"mode": "pallet"}), "AL": ("workbench", {"mode": "assemble"}),
    "MS": ("workbench", {"mode": "sand"}), "MB": ("workbench", {"mode": "sand"}),
    "SKL": ("workbench", {"mode": "assemble"}),
}


def family_of(code: str, family: str | None = None) -> str:
    """ตระกูลเครื่อง = คอลัมน์ 'ตระกูล' ในทะเบียน ถ้าไม่มีใช้ตัวอักษรนำหน้ารหัส"""
    fam = str(family or "").strip().upper()
    if fam and fam != "NAN":
        return fam
    m = re.match(r"^([A-Za-z]+)", str(code or ""))
    return m.group(1).upper() if m else ""


def classify(code: str, name: str = "", family: str | None = None) -> tuple[str, dict]:
    """เดาชนิดโมเดลจากชื่อเครื่อง → (kind, variant)"""
    text = str(name or "").lower()
    fam = family_of(code, family)
    if fam in FAMILY_FORCE:
        kind, variant = FAMILY_FORCE[fam]
        variant = dict(variant)
        if kind == "dust_collector" and "ไซโล" in text:
            variant["silo"] = True
        return kind, variant
    if text and text != "nan":
        for pat, kind, variant in RULES:
            if re.search(pat, text):
                return kind, dict(variant)
    if fam in FAMILY_DEFAULT:
        kind, variant = FAMILY_DEFAULT[fam]
        return kind, dict(variant)
    return "generic", {}


def accent_of(code: str, family: str | None = None) -> str:
    return FAMILY_ACCENT.get(family_of(code, family), DEFAULT_ACCENT)


def machine_3d(code: str, name: str = "", family: str | None = None, group: str = "",
               brand: str = "", model: str = "", status_text: str = "",
               beacon: str = "green", motion: str = "run", accent: str | None = None,
               height: int = 400, key: str = "machine_3d") -> None:
    """วาดโมเดล 3D ของเครื่อง

    beacon  green | yellow | red | grey  — สีไฟที่เสาสถานะ
    motion  run | idle | stop            — ชิ้นส่วนขยับปกติ / ช้า / หยุดนิ่ง
    key     ใช้ค่าเดิมตลอดในหน้าเดียวกัน เพื่อให้ iframe เดิมรับเครื่องใหม่แล้วเล่น
            แอนิเมชันเปลี่ยนเครื่อง แทนการสร้าง iframe ใหม่ (ภาพไม่กะพริบ)
    """
    kind, variant = classify(code, name, family)

    def _s(v) -> str:
        s = "" if v is None else str(v).strip()
        return "" if s.lower() in ("nan", "none", "—", "-") else s

    _component(
        code=_s(code), name=_s(name), kind=kind, variant=variant, group=_s(group),
        brand=_s(brand), model=_s(model), status_text=_s(status_text),
        beacon=beacon if beacon in ("green", "yellow", "red", "grey") else "grey",
        motion=motion if motion in ("run", "idle", "stop") else "stop",
        accent=accent or accent_of(code, family), height=int(height),
        key=key, default=None,
    )
