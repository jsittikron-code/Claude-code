"""ตัวรันโค้ด Python ของผู้เรียน — รันจริง ตรวจจริง ไล่ทีละบรรทัดได้
=====================================================================

ทำไมต้องรันจริงแทนที่จะเทียบข้อความโค้ด
--------------------------------------
ถ้าเทียบว่า "เขียนเหมือนเฉลยไหม" ผู้เรียนจะถูกบังคับให้เขียนแบบเดียวกับเฉลย
ทั้งที่ Python เขียนได้หลายแบบและถูกหมด ระบบนี้จึง **รันโค้ดของผู้เรียนจริง**
แล้วเทียบเฉพาะ "ผลลัพธ์" กับชุดทดสอบหลายเคส — เขียนแบบไหนก็ได้ถ้าผลถูก

ความปลอดภัย
-----------
โค้ดถูกรันใน **โปรเซสลูกแยก** (`python -I -X utf8`) ในโฟลเดอร์ชั่วคราวของตัวเอง
มีตัวจับเวลา ถ้าวนไม่รู้จบจะถูกฆ่าทิ้ง — โปรเซสหลักของแอปจึงไม่มีทางค้าง
แต่ต้องเข้าใจว่านี่ไม่ใช่ sandbox กันโค้ดร้าย: โค้ดที่รันมีสิทธิ์เท่ากับผู้ใช้ที่เปิดแอป
เท่ากับการพิมพ์ `python ไฟล์.py` เอง แอปนี้จึงออกแบบให้ใช้บนเครื่องตัวเอง/ในองค์กร
ไม่ควรเปิดให้คนนอกเข้ามารันโค้ด

สามอย่างที่โมดูลนี้ทำ
--------------------
    run()      รันโค้ดหนึ่งชุด คืน stdout / stderr / เวลาที่ใช้
    trace()    รันแบบไล่ทีละบรรทัด เก็บค่าตัวแปรทุกสเต็ปไว้ให้ย้อนดู
    grade()    ตรวจแบบฝึกหัดด้วยชุดทดสอบ + กติกาการเขียน (ต้องใช้ for, ห้ามใช้ sum ฯลฯ)
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time

MARKER = "<<<PYACAD-RESULT>>>"

DEFAULT_TIMEOUT = 8          # วินาที — พอสำหรับแบบฝึกหัด แต่ตัดลูปไม่รู้จบได้เร็ว
MAX_OUTPUT = 20_000          # ตัวอักษร — กัน print ในลูปยาวจนหน้าเว็บค้าง
MAX_TRACE_STEPS = 500


# ===========================================================================
# รันโค้ดหนึ่งชุด
# ===========================================================================
def _sandbox(files: dict[str, str] | None) -> tempfile.TemporaryDirectory:
    """สร้างโฟลเดอร์ชั่วคราว พร้อมวางไฟล์ประกอบโจทย์ (เช่น production.csv) ลงไป"""
    tmp = tempfile.TemporaryDirectory(prefix="pyacad_")
    for name, text in (files or {}).items():
        with open(os.path.join(tmp.name, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return tmp


def _spawn(workdir: str, script: str, stdin: str, timeout: float) -> dict:
    """เรียกโปรเซสลูกหนึ่งครั้ง คืนผลดิบ"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-B", script],
            cwd=workdir, input=stdin, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired as e:
        return {
            "stdout": _clip(e.stdout or ""), "stderr": "", "code": None,
            "timeout": True, "seconds": timeout,
        }
    except OSError as e:                       # หา python ไม่เจอ / เปิดโปรเซสไม่ได้
        return {"stdout": "", "stderr": f"เรียกตัวแปลภาษา Python ไม่สำเร็จ: {e}",
                "code": -1, "timeout": False, "seconds": 0.0}
    return {
        "stdout": _clip(proc.stdout), "stderr": _clip(proc.stderr),
        "code": proc.returncode, "timeout": False,
        "seconds": round(time.perf_counter() - started, 3),
    }


def _clip(text: str) -> str:
    if text and len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + f"\n... (ตัดข้อความส่วนที่เกิน {MAX_OUTPUT:,} ตัวอักษร)"
    return text or ""


def run(code: str, stdin: str = "", timeout: float = DEFAULT_TIMEOUT,
        files: dict[str, str] | None = None) -> dict:
    """รันโค้ดตรง ๆ เหมือนกด Run ในโปรแกรมแก้โค้ด

    คืน dict: stdout, stderr, code (exit code), timeout (bool), seconds
    """
    with _sandbox(files) as work:
        path = os.path.join(work, "main.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        res = _spawn(work, path, stdin, timeout)
    res["stderr"] = _clean_traceback(res["stderr"])
    return res


def _clean_traceback(err: str) -> str:
    """ตัดบรรทัดที่อ้างพาธชั่วคราวออก ให้เหลือข้อความที่ผู้เรียนอ่านรู้เรื่อง"""
    if not err:
        return ""
    lines = []
    for ln in err.splitlines():
        if "pyacad_" in ln and "File " in ln:
            # เหลือแค่เลขบรรทัด ซึ่งเป็นข้อมูลที่ผู้เรียนต้องใช้จริง
            part = ln.split(", line ", 1)
            if len(part) == 2:
                lines.append(f'  ที่บรรทัด {part[1].split(",")[0]} ของโค้ดคุณ')
                continue
        if ln.strip().startswith("File \"<"):
            continue
        lines.append(ln)
    return "\n".join(lines).strip()


# ===========================================================================
# ไล่โค้ดทีละบรรทัด
# ===========================================================================
_TRACE_HARNESS = r'''
import io, json, sys

CODE = open("learner_src.py", encoding="utf-8").read()
MAX_STEPS = __MAX__
MARKER = "__MARKER__"

buf = io.StringIO()
events = []
state = {"stop": False}


def _show(v):
    try:
        r = repr(v)
    except Exception:
        return "<แสดงค่าไม่ได้>"
    return r if len(r) <= 160 else r[:160] + " ..."


def _snap(frame):
    out = {}
    for k, v in frame.f_locals.items():
        if k.startswith("__") or callable(v) and getattr(v, "__module__", "") in ("builtins",):
            continue
        if type(v).__name__ in ("module", "function", "type"):
            continue
        out[k] = _show(v)
    return out


def _tracer(frame, event, arg):
    if state["stop"] or frame.f_code.co_filename != "<learner>":
        return None
    if event in ("line", "return"):
        if len(events) >= MAX_STEPS:
            state["stop"] = True
            sys.settrace(None)
            return None
        events.append({
            "line": frame.f_lineno,
            "func": frame.f_code.co_name,
            "event": event,
            "vars": _snap(frame),
            "ret": _show(arg) if event == "return" and arg is not None else None,
            "outlen": len(buf.getvalue()),
        })
    return _tracer


error = None
real_stdout = sys.stdout
sys.stdout = buf
try:
    obj = compile(CODE, "<learner>", "exec")
    sys.settrace(_tracer)
    exec(obj, {"__name__": "__main__"})
except BaseException as e:
    import traceback
    error = "".join(traceback.format_exception_only(type(e), e)).strip()
    tb = e.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == "<learner>":
            error += f"  (บรรทัด {tb.tb_lineno})"
            break
        tb = tb.tb_next
finally:
    sys.settrace(None)
    sys.stdout = real_stdout

print(MARKER + json.dumps({
    "events": events,
    "output": buf.getvalue()[:20000],
    "error": error,
    "truncated": state["stop"],
}, ensure_ascii=False))
'''


def trace(code: str, stdin: str = "", timeout: float = DEFAULT_TIMEOUT,
          max_steps: int = MAX_TRACE_STEPS) -> dict:
    """รันโค้ดแบบบันทึกทุกก้าว — ได้รายการเหตุการณ์ที่บอกว่าแต่ละบรรทัดทำให้ตัวแปรเปลี่ยนอย่างไร

    คืน dict: events[{line, func, event, vars, ret, outlen}], output, error, truncated
    """
    # โค้ดผู้เรียนถูกวางเป็น "ไฟล์แยก" ให้ harness อ่าน ไม่ฝังเป็นสตริงในตัว harness
    # เพราะโค้ดที่มี triple quote หรือลงท้ายด้วย backslash จะทำให้ harness พังทันที
    files = {"learner_src.py": code}
    harness = (_TRACE_HARNESS.replace("__MAX__", str(max_steps))
                             .replace("__MARKER__", MARKER))

    with _sandbox(files) as work:
        path = os.path.join(work, "_trace.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(harness)
        res = _spawn(work, path, stdin, timeout)

    if res["timeout"]:
        return {"events": [], "output": res["stdout"], "truncated": True,
                "error": f"โค้ดทำงานนานเกิน {timeout:.0f} วินาที — น่าจะมีลูปที่ไม่มีวันจบ"}
    payload = _extract(res["stdout"])
    if payload is None:
        return {"events": [], "output": res["stdout"], "truncated": False,
                "error": _clean_traceback(res["stderr"]) or "รันโค้ดไม่สำเร็จ"}
    return payload


def _extract(stdout: str):
    """ดึงก้อน JSON ที่ harness พิมพ์ต่อท้าย MARKER ออกมา"""
    idx = stdout.rfind(MARKER)
    if idx < 0:
        return None
    try:
        return json.loads(stdout[idx + len(MARKER):])
    except json.JSONDecodeError:
        return None


# ===========================================================================
# กติกาการเขียน — ตรวจจากโครงสร้างโค้ด (AST) ไม่ใช่ค้นข้อความ
# ===========================================================================
FEATURE_LABEL = {
    "for": "ลูป for", "while": "ลูป while", "if": "คำสั่ง if",
    "def": "การสร้างฟังก์ชันด้วย def", "return": "คำสั่ง return",
    "class": "การสร้างคลาส", "try": "การดักข้อผิดพลาดด้วย try",
    "comprehension": "comprehension แบบย่อ", "lambda": "lambda",
    "f-string": "f-string", "with": "คำสั่ง with",
    "dict": "dict", "list": "list", "set": "set", "tuple": "tuple",
    "unpack": "การแตกค่าหลายตัวพร้อมกัน",
}


def _label(tag: str) -> str:
    if tag.startswith("call:"):
        return f"ฟังก์ชัน {tag[5:]}()"
    if tag.startswith("method:"):
        return f"เมท็อด .{tag[7:]}()"
    if tag.startswith("import:"):
        return f"การ import {tag[7:]}"
    return FEATURE_LABEL.get(tag, tag)


def rule_text(tags: list[str]) -> str:
    """แปลงรายการกติกาเป็นข้อความภาษาคน สำหรับแสดงบนหน้าโจทย์"""
    return ", ".join(_label(t) for t in tags)


def features(code: str) -> set[str]:
    """สรุปว่าโค้ดชุดนี้ใช้โครงสร้างอะไรบ้าง (ใช้ตรวจกติกาของโจทย์)"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        t = type(node).__name__
        if t in ("For", "AsyncFor"):
            found.add("for")
        elif t == "While":
            found.add("while")
        elif t in ("If", "IfExp"):
            found.add("if")
        elif t in ("FunctionDef", "AsyncFunctionDef"):
            found.add("def")
        elif t == "Return":
            found.add("return")
        elif t == "ClassDef":
            found.add("class")
        elif t in ("Try", "TryStar"):
            found.add("try")
        elif t in ("ListComp", "SetComp", "DictComp", "GeneratorExp"):
            found.add("comprehension")
        elif t == "Lambda":
            found.add("lambda")
        elif t == "JoinedStr":
            found.add("f-string")
        elif t in ("With", "AsyncWith"):
            found.add("with")
        elif t == "Dict":
            found.add("dict")
        elif t == "List":
            found.add("list")
        elif t == "Set":
            found.add("set")
        elif t == "Tuple":
            found.add("tuple")
        elif t == "Starred":
            found.add("unpack")
        elif t == "Import":
            for a in node.names:                      # type: ignore[attr-defined]
                found.add("import:" + a.name.split(".")[0])
        elif t == "ImportFrom":
            found.add("import:" + (node.module or "").split(".")[0])  # type: ignore[attr-defined]
        elif t == "Call":
            fn = node.func                            # type: ignore[attr-defined]
            if isinstance(fn, ast.Name):
                found.add("call:" + fn.id)
            elif isinstance(fn, ast.Attribute):
                found.add("method:" + fn.attr)
    return found


def check_rules(code: str, must_use: list[str] | None,
                banned: list[str] | None) -> list[str]:
    """คืนรายการข้อความบอกว่าผิดกติกาข้อไหนบ้าง (ว่าง = ผ่าน)"""
    have = features(code)
    problems = []
    for tag in must_use or []:
        if tag not in have:
            problems.append(f"ข้อนี้กำหนดให้ใช้ {_label(tag)} แต่ยังไม่เห็นในโค้ด")
    for tag in banned or []:
        if tag in have:
            problems.append(f"ข้อนี้ห้ามใช้ {_label(tag)} — ลองเขียนวิธีอื่นดู")
    return problems


def syntax_error(code: str) -> str | None:
    """ตรวจไวยากรณ์ก่อนรัน เพื่อบอกตำแหน่งผิดได้ทันทีโดยไม่ต้องเปิดโปรเซส"""
    try:
        compile(code, "<learner>", "exec")
    except SyntaxError as e:
        where = f"บรรทัด {e.lineno}" + (f" ตำแหน่งที่ {e.offset}" if e.offset else "")
        return f"ไวยากรณ์ผิดที่{where}: {e.msg}"
    except ValueError as e:
        return f"โค้ดนี้แปลไม่ได้: {e}"
    return None


# ===========================================================================
# ตรวจแบบฝึกหัด
# ===========================================================================
_FUNC_HARNESS = r'''
import io, json, os, sys, traceback

sys.path.insert(0, os.getcwd())   # โหมด -I ไม่ใส่โฟลเดอร์ปัจจุบันให้ ต้องเติมเองก่อน import
MARKER = "__MARKER__"
CASES = json.loads(open("_cases.json", encoding="utf-8").read())
FUNC = "__FUNC__"

buf = io.StringIO()
real_stdout = sys.stdout
sys.stdout = buf
rows, load_error = [], None
try:
    import learner_src as sol
except BaseException as e:
    load_error = "".join(traceback.format_exception_only(type(e), e)).strip()
    sol = None
finally:
    sys.stdout = real_stdout

fn = getattr(sol, FUNC, None) if sol is not None else None
if sol is not None and fn is None:
    load_error = "ไม่พบฟังก์ชันชื่อ " + FUNC + "() ในโค้ดของคุณ (สะกดชื่อให้ตรงกับโจทย์)"
elif fn is not None and not callable(fn):
    load_error = FUNC + " ไม่ใช่ฟังก์ชัน — โจทย์ให้สร้างด้วย def " + FUNC + "(...)"

if fn is not None and callable(fn):
    for case in CASES:
        sys.stdout = buf
        try:
            value = fn(*case.get("args", []), **case.get("kwargs", {}))
            try:
                json.dumps(value)
                rows.append({"ok": True, "value": value, "repr": repr(value)})
            except (TypeError, ValueError):
                rows.append({"ok": True, "value": None, "repr": repr(value),
                             "unserializable": True})
        except BaseException as e:
            rows.append({"ok": False,
                         "error": "".join(traceback.format_exception_only(type(e), e)).strip()})
        finally:
            sys.stdout = real_stdout

print(MARKER + json.dumps({"rows": rows, "load_error": load_error,
                           "output": buf.getvalue()[:8000]}, ensure_ascii=False))
'''


def _same(got, expect, tol: float = 1e-6) -> bool:
    """เทียบผลลัพธ์แบบยอมรับความต่างของทศนิยม และมองทูเพิล/ลิสต์เป็นอย่างเดียวกัน

    (ผ่าน JSON แล้วทูเพิลจะกลายเป็นลิสต์เสมอ จึงต้องเทียบแบบนี้)
    """
    if isinstance(expect, bool) or isinstance(got, bool):
        return got is expect or got == expect and type(got) is type(expect)
    if isinstance(expect, (int, float)) and isinstance(got, (int, float)):
        if expect != expect or got != got:                # NaN
            return expect != expect and got != got
        return abs(got - expect) <= tol * max(1.0, abs(expect))
    if isinstance(expect, (list, tuple)) and isinstance(got, (list, tuple)):
        return len(got) == len(expect) and all(_same(g, e, tol) for g, e in zip(got, expect))
    if isinstance(expect, dict) and isinstance(got, dict):
        return set(got) == set(expect) and all(_same(got[k], expect[k], tol) for k in expect)
    if isinstance(expect, set):
        try:
            return set(got) == expect
        except TypeError:
            return False
    return got == expect


def _norm_out(text: str) -> str:
    """ผลลัพธ์ทางจอ: ตัดช่องว่างท้ายบรรทัดและบรรทัดว่างท้ายไฟล์ นอกนั้นต้องตรงเป๊ะ"""
    return "\n".join(ln.rstrip() for ln in (text or "").replace("\r\n", "\n").split("\n")).strip()


def _fmt(v) -> str:
    return repr(v)


def grade(ex: dict, code: str) -> dict:
    """ตรวจคำตอบหนึ่งข้อ

    คืน dict:
        ok      ผ่านครบทุกเคสและไม่ผิดกติกาหรือไม่
        error   ข้อความผิดพลาดระดับที่รันไม่ได้เลย (ถ้ามี)
        rules   รายการที่ผิดกติกาการเขียน
        rows    [{case, got, expect, pass}] ผลรายเคส
        stdout  สิ่งที่โค้ดพิมพ์ออกมาระหว่างตรวจ
    """
    out = {"ok": False, "error": "", "rules": [], "rows": [], "stdout": ""}

    if not code.strip():
        out["error"] = "ยังไม่ได้เขียนโค้ด"
        return out

    err = syntax_error(code)
    if err:
        out["error"] = err
        return out

    out["rules"] = check_rules(code, ex.get("must_use"), ex.get("banned"))

    if ex.get("kind", "func") == "func":
        _grade_func(ex, code, out)
    else:
        _grade_stdout(ex, code, out)

    if out["rules"] and out["ok"]:
        out["ok"] = False
    return out


def _grade_func(ex: dict, code: str, out: dict) -> None:
    cases = ex["cases"]
    harness = (_FUNC_HARNESS.replace("__MARKER__", MARKER)
                            .replace("__FUNC__", ex["func"]))
    payload_cases = [{"args": list(c.get("args", [])), "kwargs": c.get("kwargs", {})}
                     for c in cases]
    files = dict(ex.get("files", {}))
    files["learner_src.py"] = code
    files["_cases.json"] = json.dumps(payload_cases, ensure_ascii=False)

    with _sandbox(files) as work:
        path = os.path.join(work, "_check.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(harness)
        res = _spawn(work, path, "", ex.get("timeout", DEFAULT_TIMEOUT))

    if res["timeout"]:
        out["error"] = (f"โค้ดทำงานนานเกิน {ex.get('timeout', DEFAULT_TIMEOUT):.0f} วินาที "
                        "— มักเกิดจากลูปที่เงื่อนไขจบไม่เป็นจริงสักที")
        return
    payload = _extract(res["stdout"])
    if payload is None:
        out["error"] = _clean_traceback(res["stderr"]) or "รันโค้ดไม่สำเร็จ"
        return

    out["stdout"] = payload.get("output", "")
    if payload.get("load_error"):
        out["error"] = payload["load_error"]
        return

    rows = []
    for case, got in zip(cases, payload["rows"]):
        label = case.get("label") or f"{ex['func']}({', '.join(_fmt(a) for a in case.get('args', []))})"
        if not got.get("ok"):
            rows.append({"case": label, "got": "เกิดข้อผิดพลาด: " + got.get("error", ""),
                         "expect": _fmt(case["expect"]), "pass": False})
            continue
        if got.get("unserializable"):
            ok = got["repr"] == repr(case["expect"])
        else:
            ok = _same(got.get("value"), case["expect"], ex.get("tol", 1e-6))
        rows.append({"case": label, "got": got.get("repr", ""),
                     "expect": _fmt(case["expect"]), "pass": ok})
    out["rows"] = rows
    out["ok"] = bool(rows) and all(r["pass"] for r in rows)


def _grade_stdout(ex: dict, code: str, out: dict) -> None:
    rows, printed = [], []
    for case in ex["cases"]:
        res = run(code, stdin=case.get("stdin", ""),
                  timeout=ex.get("timeout", DEFAULT_TIMEOUT),
                  files=ex.get("files"))
        if res["timeout"]:
            out["error"] = (f"โค้ดทำงานนานเกิน {ex.get('timeout', DEFAULT_TIMEOUT):.0f} วินาที "
                            "— มักเกิดจากลูปที่ไม่มีวันจบ")
            return
        if res["stderr"]:
            out["error"] = res["stderr"]
            return
        got, expect = _norm_out(res["stdout"]), _norm_out(case["expect"])
        printed.append(res["stdout"])
        rows.append({
            "case": case.get("label") or (f"ป้อน: {case['stdin'].strip()}"
                                          if case.get("stdin") else "รันตรง ๆ"),
            "got": got or "(ไม่มีผลลัพธ์)", "expect": expect, "pass": got == expect,
        })
    out["rows"] = rows
    out["stdout"] = printed[0] if printed else ""
    out["ok"] = bool(rows) and all(r["pass"] for r in rows)
