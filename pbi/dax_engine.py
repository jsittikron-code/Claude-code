"""เครื่องจำลอง DAX ขนาดย่อ (mini-DAX interpreter) — ใช้ฝึกเขียน DAX แล้วตรวจคำตอบได้ทันที
==============================================================================================

ทำไมต้องมี
----------
การฝึก DAX จากหนังสือหรือวิดีโอมีจุดอ่อนคือ "เขียนแล้วไม่รู้ว่าถูกไหม" ต้องเปิด Power BI
Desktop ทุกครั้ง ไฟล์นี้ทำหน้าที่เป็นเอนจินคำนวณสูตร DAX บนโมเดลตัวอย่าง (pandas)
ทำให้แอปตรวจคำตอบอัตโนมัติได้ โดยเทียบผลลัพธ์ของสูตรผู้เรียนกับสูตรเฉลย
ภายใต้ "หลาย filter context" — ถ้าเขียน CALCULATE/ALL ผิด ผลจะต่างทันที

สิ่งที่จำลองได้จริง
-------------------
  • filter context แยกตามคอลัมน์ (ALL / ALLEXCEPT / REMOVEFILTERS ถอดได้ตรงคอลัมน์)
  • CALCULATE + ตัวกรองแบบเงื่อนไข และแบบตาราง (FILTER, VALUES, KEEPFILTERS)
  • row context แบบเวกเตอร์ สำหรับตระกูล X (SUMX, AVERAGEX, MINX, MAXX, ...)
  • Time intelligence ระดับใช้งานจริง (DATESYTD, TOTALYTD, SAMEPERIODLASTYEAR, DATEADD, ...)
  • VAR ... RETURN

ข้อจำกัดที่ตั้งใจไว้ (บอกผู้เรียนตรง ๆ ในหน้าแอป)
-------------------------------------------------
  • ไม่มี context transition — เรียก SUM() ซ้อนใน SUMX() จะฟ้อง error พร้อมคำอธิบาย
  • โมเดลถูกแบนเป็นตารางกว้างตารางเดียว (ความสัมพันธ์ถูก join ไว้ล่วงหน้า)
    RELATED() จึงทำงานเป็นการอ้างคอลัมน์ตรง ๆ
  • ไม่รองรับ RANKX / TOPN / EARLIER / DAX Query (EVALUATE)

ตัวเลขที่ได้จากที่นี่ตรงกับ Power BI ในทุกแบบฝึกหัดที่ชุดนี้ใช้ แต่ "ไม่ใช่" ตัว Power BI จริง
— ให้ใช้เป็นสนามซ้อม แล้วไปยืนยันของจริงบน Power BI Desktop ด้วยชุดข้อมูลเดียวกัน
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MAX_EXPR_LEN = 8000      # กันสูตรยาวผิดปกติ
MAX_DEPTH = 40           # กัน measure อ้างวนกันเอง


class DaxError(Exception):
    """ข้อผิดพลาดจากการแปลหรือคำนวณสูตร DAX (ข้อความเป็นภาษาไทย ใช้แสดงให้ผู้เรียนอ่าน)"""


# ===========================================================================
# 1) ตัวตัดคำ (tokenizer)
# ===========================================================================
@dataclass
class Tok:
    kind: str          # num | str | col | tname | ident | op | punc
    val: object
    pos: int


_NUM_RE = re.compile(r"\d+(\.\d+)?([eE][+-]?\d+)?")
_IDENT_RE = re.compile(r"[^\W\d]\w*(\.\w+)*", re.UNICODE)
_TWO_CHAR_OPS = ("<>", ">=", "<=", "&&", "||")


def tokenize(src: str) -> list[Tok]:
    if len(src) > MAX_EXPR_LEN:
        raise DaxError(f"สูตรยาวเกิน {MAX_EXPR_LEN} ตัวอักษร")
    toks: list[Tok] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        # หมายเหตุ/คอมเมนต์
        if src.startswith("--", i) or src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        # ข้อความ "..."  (ใน DAX ใช้ "" แทนอัญประกาศซ้อน)
        if c == '"':
            j, buf = i + 1, []
            while j < n:
                if src[j] == '"':
                    if j + 1 < n and src[j + 1] == '"':
                        buf.append('"')
                        j += 2
                        continue
                    break
                buf.append(src[j])
                j += 1
            if j >= n:
                raise DaxError('เครื่องหมาย \" เปิดแล้วไม่ได้ปิด')
            toks.append(Tok("str", "".join(buf), i))
            i = j + 1
            continue
        # 'ชื่อตาราง'  หรือ  'ชื่อตาราง'[คอลัมน์]
        if c == "'":
            j = src.find("'", i + 1)
            if j < 0:
                raise DaxError("เครื่องหมาย ' เปิดแล้วไม่ได้ปิด")
            name = src[i + 1:j]
            i = j + 1
            if i < n and src[i] == "[":
                k = src.find("]", i)
                if k < 0:
                    raise DaxError("วงเล็บ [ ] ไม่ครบคู่")
                toks.append(Tok("col", (name, src[i + 1:k]), i))
                i = k + 1
            else:
                toks.append(Tok("tname", name, i))
            continue
        # [คอลัมน์] หรือ [ชื่อ measure] แบบไม่ระบุตาราง
        if c == "[":
            k = src.find("]", i)
            if k < 0:
                raise DaxError("วงเล็บ [ ] ไม่ครบคู่")
            toks.append(Tok("col", ("", src[i + 1:k]), i))
            i = k + 1
            continue
        # ตัวเลข
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            m = _NUM_RE.match(src, i)
            toks.append(Tok("num", float(m.group(0)), i))
            i = m.end()
            continue
        # ชื่อ (ฟังก์ชัน / ตาราง / ตัวแปร) — รองรับจุด เช่น STDEV.P
        if c.isalpha() or c == "_" or ord(c) > 127:
            m = _IDENT_RE.match(src, i)
            if not m:
                raise DaxError(f"อ่านสัญลักษณ์ไม่ออกที่ตำแหน่ง {i}")
            word, j = m.group(0), m.end()
            if j < n and src[j] == "[":
                k = src.find("]", j)
                if k < 0:
                    raise DaxError("วงเล็บ [ ] ไม่ครบคู่")
                toks.append(Tok("col", (word, src[j + 1:k]), i))
                i = k + 1
            else:
                toks.append(Tok("ident", word, i))
                i = j
            continue
        # ตัวดำเนินการ
        two = next((op for op in _TWO_CHAR_OPS if src.startswith(op, i)), None)
        if two:
            toks.append(Tok("op", two, i))
            i += 2
            continue
        if c in "=<>+-*/^&":
            toks.append(Tok("op", c, i))
            i += 1
            continue
        if c in "(),{}":
            toks.append(Tok("punc", c, i))
            i += 1
            continue
        raise DaxError(f"อักขระที่ไม่รู้จัก: {c!r}")
    return toks


# ===========================================================================
# 2) ตัวแปลไวยากรณ์ (parser) — คืน AST เป็น tuple
#
#    ('num', v) ('str', s) ('col', table, col) ('name', ident) ('tname', name)
#    ('func', NAME, [args]) ('bin', op, l, r) ('un', op, x)
#    ('set', [items]) ('var', [(name, expr)...], ret)
# ===========================================================================
class Parser:
    def __init__(self, toks: list[Tok]):
        self.toks = toks
        self.i = 0

    # -- เครื่องมือช่วย ----------------------------------------------------
    def peek(self, k: int = 0) -> Tok | None:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def at_op(self, *ops: str) -> bool:
        t = self.peek()
        return bool(t and t.kind == "op" and t.val in ops)

    def at_punc(self, ch: str) -> bool:
        t = self.peek()
        return bool(t and t.kind == "punc" and t.val == ch)

    def at_kw(self, *words: str) -> bool:
        t = self.peek()
        return bool(t and t.kind == "ident" and t.val.upper() in words)

    def take(self) -> Tok:
        t = self.peek()
        if t is None:
            raise DaxError("สูตรจบก่อนกำหนด — ตรวจวงเล็บหรืออาร์กิวเมนต์ที่ขาดไป")
        self.i += 1
        return t

    def expect_punc(self, ch: str) -> None:
        if not self.at_punc(ch):
            got = self.peek()
            raise DaxError(f"ต้องการ '{ch}' แต่เจอ {got.val if got else 'จุดจบสูตร'}")
        self.i += 1

    # -- ชั้นไวยากรณ์ ------------------------------------------------------
    def parse(self):
        node = self.expr()
        if self.i < len(self.toks):
            t = self.toks[self.i]
            raise DaxError(f"มีส่วนเกินหลังจบสูตร: {t.val!r}")
        return node

    def expr(self):
        # VAR name = expr [VAR ...] RETURN expr
        if self.at_kw("VAR"):
            decls = []
            while self.at_kw("VAR"):
                self.take()
                t = self.take()
                if t.kind != "ident":
                    raise DaxError("หลัง VAR ต้องตามด้วยชื่อตัวแปร")
                if not self.at_op("="):
                    raise DaxError(f"ตัวแปร {t.val} ต้องมีเครื่องหมาย = ตามหลัง")
                self.take()
                decls.append((t.val, self.or_expr()))
            if not self.at_kw("RETURN"):
                raise DaxError("บล็อก VAR ต้องปิดท้ายด้วย RETURN")
            self.take()
            return ("var", decls, self.expr())
        return self.or_expr()

    def or_expr(self):
        node = self.and_expr()
        while self.at_op("||") or self.at_kw("OR"):
            self.take()
            node = ("bin", "||", node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while self.at_op("&&") or self.at_kw("AND"):
            self.take()
            node = ("bin", "&&", node, self.not_expr())
        return node

    def not_expr(self):
        if self.at_kw("NOT"):
            self.take()
            return ("un", "NOT", self.not_expr())
        return self.compare()

    def compare(self):
        node = self.concat()
        while True:
            if self.at_op("=", "<>", "<", ">", "<=", ">="):
                op = self.take().val
                node = ("bin", op, node, self.concat())
            elif self.at_kw("IN"):
                self.take()
                node = ("bin", "IN", node, self.concat())
            else:
                return node

    def concat(self):
        node = self.additive()
        while self.at_op("&"):
            self.take()
            node = ("bin", "&", node, self.additive())
        return node

    def additive(self):
        node = self.multiplicative()
        while self.at_op("+", "-"):
            op = self.take().val
            node = ("bin", op, node, self.multiplicative())
        return node

    def multiplicative(self):
        node = self.unary()
        while self.at_op("*", "/"):
            op = self.take().val
            node = ("bin", op, node, self.unary())
        return node

    def unary(self):
        if self.at_op("-", "+"):
            op = self.take().val
            return ("un", op, self.unary())
        return self.power()

    def power(self):
        node = self.primary()
        if self.at_op("^"):
            self.take()
            return ("bin", "^", node, self.unary())
        return node

    def primary(self):
        t = self.take()
        if t.kind == "num":
            return ("num", t.val)
        if t.kind == "str":
            return ("str", t.val)
        if t.kind == "col":
            return ("col", t.val[0], t.val[1])
        if t.kind == "tname":
            return ("tname", t.val)
        if t.kind == "punc" and t.val == "(":
            node = self.expr()
            self.expect_punc(")")
            return node
        if t.kind == "punc" and t.val == "{":
            items = []
            if not self.at_punc("}"):
                items.append(self.expr())
                while self.at_punc(","):
                    self.take()
                    items.append(self.expr())
            self.expect_punc("}")
            return ("set", items)
        if t.kind == "ident":
            if self.at_punc("("):
                self.take()
                args = []
                if not self.at_punc(")"):
                    args.append(self.expr())
                    while self.at_punc(","):
                        self.take()
                        args.append(self.expr())
                self.expect_punc(")")
                return ("func", t.val.upper(), args)
            return ("name", t.val)
        raise DaxError(f"ไม่เข้าใจสัญลักษณ์ {t.val!r}")


def parse_dax(src: str):
    return Parser(tokenize(src)).parse()


# ===========================================================================
# 3) โมเดลข้อมูล — ตารางกว้างตารางเดียวที่ join ความสัมพันธ์ไว้แล้ว
# ===========================================================================
@dataclass
class TableVal:
    """ผลลัพธ์ชนิด 'ตาราง' — เก็บเป็น mask ของแถวในตารางกว้าง"""
    mask: np.ndarray
    table: str | None = None


@dataclass
class ValuesVal:
    """ผลลัพธ์ของ VALUES/DISTINCT — ชุดค่าที่ไม่ซ้ำของคอลัมน์หนึ่ง"""
    key: str
    mask: np.ndarray
    table: str | None = None


class Model:
    """โมเดลข้อมูลสำหรับเอนจิน

    base   : DataFrame กว้าง คอลัมน์ชื่อรูปแบบ "Table[Column]"
    tables : {ชื่อตาราง: [ชื่อคอลัมน์...]}
    keys   : {ชื่อตาราง: คอลัมน์ที่ใช้เป็นตัวระบุแถวของตารางนั้น}  (ตาราง fact ใส่ None)
    """

    def __init__(self, base: pd.DataFrame, tables: dict[str, list[str]],
                 keys: dict[str, str | None], fact: str, date_key: str,
                 measures: dict[str, str] | None = None):
        self.base = base.reset_index(drop=True)
        self.n = len(self.base)
        self.tables = tables
        self.keys = keys
        self.fact = fact
        self.date_key = date_key
        self.measures = measures or {}
        self.arr = {c: self.base[c].to_numpy() for c in self.base.columns}
        # แผนที่ค้นหาแบบไม่สนตัวพิมพ์
        self._tbl_lower = {t.lower(): t for t in tables}
        self._col_lower: dict[str, str] = {}
        self._bare: dict[str, list[str]] = {}
        for t, cols in tables.items():
            for c in cols:
                key = f"{t}[{c}]"
                self._col_lower[key.lower()] = key
                self._bare.setdefault(c.lower(), []).append(key)
        self._meas_lower = {m.lower(): m for m in self.measures}

    # -- การค้นหาชื่อ ------------------------------------------------------
    def table_name(self, name: str) -> str | None:
        return self._tbl_lower.get(name.lower())

    def col_key(self, table: str, col: str) -> str:
        if table:
            key = self._col_lower.get(f"{table}[{col}]".lower())
            if key:
                return key
            if self.table_name(table) is None:
                raise DaxError(f"ไม่พบตาราง '{table}' ในโมเดล")
            raise DaxError(f"ไม่พบคอลัมน์ {table}[{col}] — ตรวจชื่อคอลัมน์อีกครั้ง")
        hits = self._bare.get(col.lower(), [])
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise DaxError(f"ไม่พบคอลัมน์ [{col}] ในโมเดล")
        raise DaxError(f"[{col}] มีอยู่หลายตาราง ({', '.join(hits)}) — ระบุชื่อตารางด้วย")

    def measure_name(self, name: str) -> str | None:
        return self._meas_lower.get(name.lower())

    def table_of(self, key: str) -> str:
        return key.split("[", 1)[0]


# ===========================================================================
# 4) บริบทการคำนวณ
# ===========================================================================
_KEEP = object()      # ค่าสัญญาณ "ใช้ของเดิม" (ห้ามใช้สตริง เพราะ numpy จะเทียบทีละสมาชิก)


class Ctx:
    __slots__ = ("model", "filters", "row_idx", "vars", "depth", "_mask", "_anon")

    def __init__(self, model: Model, filters: dict[str, np.ndarray] | None = None,
                 row_idx: np.ndarray | None = None, variables: dict | None = None,
                 depth: int = 0, anon: list[int] | None = None):
        self.model = model
        self.filters = {} if filters is None else filters
        self.row_idx = row_idx
        self.vars = {} if variables is None else variables
        self.depth = depth
        self._mask: np.ndarray | None = None
        self._anon = anon if anon is not None else [0]

    def mask(self) -> np.ndarray:
        if self._mask is None:
            if not self.filters:
                self._mask = np.ones(self.model.n, dtype=bool)
            else:
                m = np.ones(self.model.n, dtype=bool)
                for f in self.filters.values():
                    m &= f
                self._mask = m
        return self._mask

    def next_anon(self) -> str:
        self._anon[0] += 1
        return f"__f{self._anon[0]}"

    def derive(self, filters=None, row_idx=_KEEP, variables=None) -> "Ctx":
        return Ctx(
            self.model,
            self.filters if filters is None else filters,
            self.row_idx if row_idx is _KEEP else row_idx,
            self.vars if variables is None else variables,
            self.depth + 1,
            self._anon,
        )


# ===========================================================================
# 5) ตัวช่วยคำนวณ
# ===========================================================================
def _is_vec(x) -> bool:
    return isinstance(x, np.ndarray)


def _num(x):
    """แปลงค่าว่าง (BLANK) เป็น 0 สำหรับการคำนวณเลข ตามพฤติกรรมของ DAX"""
    if x is None:
        return 0.0
    if _is_vec(x):
        if x.dtype == object:
            return np.array([0.0 if v is None else v for v in x], dtype=float)
        return x
    if isinstance(x, (bool, np.bool_)):
        return float(x)
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return x
    return x


def _blank_if_nan(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _py(v):
    """แปลงค่า numpy เป็นชนิดพื้นฐานของ Python เพื่อให้เปรียบเทียบ/แสดงผลได้สะดวก"""
    if v is None:
        return None
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _to_dt(v):
    if isinstance(v, pd.Timestamp):
        return v
    return pd.Timestamp(v)


# ===========================================================================
# 6) ตัวประมวลผล
# ===========================================================================
def ev(node, ctx: Ctx):
    if ctx.depth > MAX_DEPTH:
        raise DaxError("สูตรซ้อนลึกเกินไป (อาจมี measure อ้างวนกลับมาหาตัวเอง)")
    kind = node[0]

    if kind == "num":
        return node[1]
    if kind == "str":
        return node[1]
    if kind == "set":
        return [ev(x, ctx) for x in node[1]]

    if kind == "col":
        return _eval_col(node, ctx)

    if kind == "tname":
        t = ctx.model.table_name(node[1])
        if t is None:
            raise DaxError(f"ไม่พบตาราง '{node[1]}'")
        return TableVal(ctx.mask(), t)

    if kind == "name":
        word = node[1]
        up = word.upper()
        if up == "TRUE":
            return True
        if up == "FALSE":
            return False
        if up == "BLANK":
            return None
        if word in ctx.vars:
            return ctx.vars[word]
        for k, v in ctx.vars.items():          # ตัวแปรไม่สนตัวพิมพ์
            if k.lower() == word.lower():
                return v
        t = ctx.model.table_name(word)
        if t is not None:
            return TableVal(ctx.mask(), t)
        raise DaxError(
            f"ไม่รู้จัก '{word}' — ถ้าเป็นข้อความต้องใส่ \"เครื่องหมายคำพูด\" "
            f"ถ้าเป็นคอลัมน์ต้องเขียนแบบ Table[Column]"
        )

    if kind == "var":
        variables = dict(ctx.vars)
        sub = ctx.derive(variables=variables)
        for name, sub_node in node[1]:
            variables[name] = ev(sub_node, sub)
        return ev(node[2], sub)

    if kind == "un":
        op = node[1]
        v = ev(node[2], ctx)
        if op == "NOT":
            return np.logical_not(v) if _is_vec(v) else (not _truth(v))
        v = _num(v)
        return -v if op == "-" else +v

    if kind == "bin":
        return _eval_bin(node, ctx)

    if kind == "func":
        return _eval_func(node, ctx)

    raise DaxError(f"ไม่รู้จักโครงสร้าง {kind}")


def _eval_col(node, ctx: Ctx):
    _, table, col = node
    if not table:
        m = ctx.model.measure_name(col)
        if m is not None:
            if ctx.row_idx is not None:
                raise DaxError(
                    f"เรียก measure [{m}] ภายใน row context ไม่ได้ในเครื่องจำลองนี้ "
                    "(ของจริงคือ context transition ซึ่งยังไม่รองรับ)"
                )
            return ev(parse_dax(ctx.model.measures[m]), ctx.derive())
    key = ctx.model.col_key(table, col)
    if ctx.row_idx is None:
        raise DaxError(
            f"อ้างคอลัมน์ {key} ตรง ๆ ไม่ได้ เพราะยังไม่มี row context — "
            "ต้องครอบด้วยฟังก์ชันรวมยอด เช่น SUM(...) หรือใช้ในตระกูล X เช่น SUMX(...)"
        )
    return ctx.model.arr[key][ctx.row_idx]


def _truth(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v != ""
    return bool(v)


_CMP = {
    "=": lambda a, b: a == b,
    "<>": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
}


def _eval_bin(node, ctx: Ctx):
    _, op, ln, rn = node

    if op in ("&&", "||"):
        a = ev(ln, ctx)
        b = ev(rn, ctx)
        if _is_vec(a) or _is_vec(b):
            a = a if _is_vec(a) else np.full(1, _truth(a))
            b = b if _is_vec(b) else np.full(1, _truth(b))
            return np.logical_and(a, b) if op == "&&" else np.logical_or(a, b)
        return (_truth(a) and _truth(b)) if op == "&&" else (_truth(a) or _truth(b))

    a = ev(ln, ctx)
    b = ev(rn, ctx)

    if op == "IN":
        items = b if isinstance(b, list) else [b]
        if _is_vec(a):
            return np.isin(a, list(items))
        return a in items

    if op == "&":
        def s(x):
            if x is None:
                return ""
            if _is_vec(x):
                return np.array([("" if v is None else _fmt_default(v)) for v in x], dtype=object)
            return _fmt_default(x)
        sa, sb = s(a), s(b)
        if _is_vec(sa) or _is_vec(sb):
            return np.char.add(np.asarray(sa, dtype=str), np.asarray(sb, dtype=str))
        return sa + sb

    if op in _CMP:
        if a is None and b is None:
            return op in ("=", "<=", ">=")
        if isinstance(a, str) or isinstance(b, str):
            if _is_vec(a) or _is_vec(b):
                return _CMP[op](np.asarray(a, dtype=object), b)
            if a is None:
                a = ""
            if b is None:
                b = ""
        else:
            a, b = _num(a), _num(b)
        with np.errstate(invalid="ignore"):
            return _CMP[op](a, b)

    a, b = _num(a), _num(b)
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.divide(a, b) if (_is_vec(a) or _is_vec(b)) else (
                float("nan") if b == 0 else a / b)
        return r
    if op == "^":
        return a ** b
    raise DaxError(f"ไม่รู้จักตัวดำเนินการ {op}")


def _fmt_default(v) -> str:
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and float(v).is_integer():
        return str(int(v))
    return str(v)


# ---------------------------------------------------------------------------
# ตัวช่วยของฟังก์ชัน
# ---------------------------------------------------------------------------
def _need(args, lo, hi, name):
    if not (lo <= len(args) <= hi):
        want = f"{lo}" if lo == hi else f"{lo}-{hi}"
        raise DaxError(f"{name}() ต้องการอาร์กิวเมนต์ {want} ตัว แต่ได้ {len(args)} ตัว")


def _col_node_key(node, ctx: Ctx, fname: str) -> str:
    if node[0] != "col":
        raise DaxError(f"{fname}() ต้องรับ 'คอลัมน์' เช่น {fname}(Production[GoodQty])")
    if not node[1]:
        m = ctx.model.measure_name(node[2])
        if m is not None:
            raise DaxError(f"{fname}() รับคอลัมน์ ไม่ใช่ measure [{node[2]}]")
    return ctx.model.col_key(node[1], node[2])


def _agg_values(node, ctx: Ctx, fname: str) -> np.ndarray:
    if ctx.row_idx is not None:
        raise DaxError(
            f"เรียก {fname}() ซ้อนอยู่ใน row context (เช่นภายใน SUMX) ไม่ได้ — "
            "ของจริงต้องอาศัย context transition ซึ่งเครื่องจำลองนี้ยังไม่รองรับ "
            "ลองเขียนเป็นสูตรเดียวแบบ SUMX(ตาราง, คอลัมน์ก × คอลัมน์ข) แทน"
        )
    key = _col_node_key(node, ctx, fname)
    return ctx.model.arr[key][ctx.mask()]


def _numeric(vals: np.ndarray) -> np.ndarray:
    if vals.dtype == object:
        return pd.to_numeric(pd.Series(vals), errors="coerce").to_numpy()
    if np.issubdtype(vals.dtype, np.datetime64):
        return vals
    return vals.astype(float)


def _table_arg(node, ctx: Ctx, fname: str) -> TableVal:
    v = ev(node, ctx)
    if isinstance(v, TableVal):
        return v
    if isinstance(v, ValuesVal):
        raise DaxError(
            f"{fname}() วนบนผลของ VALUES() ไม่ได้ในเครื่องจำลองนี้ "
            "(ต้องใช้ context transition) — ลองวนบนตาราง fact โดยตรง"
        )
    raise DaxError(f"{fname}() ต้องรับ 'ตาราง' เป็นอาร์กิวเมนต์แรก")


def _iterate(tnode, expr_node, ctx: Ctx, fname: str):
    tv = ev(tnode, ctx)

    if isinstance(tv, ValuesVal):
        # วนบนค่าที่ไม่ซ้ำของคอลัมน์เดียว — ทำได้ก็ต่อเมื่อนิพจน์อ้างเฉพาะคอลัมน์นั้น
        used: set[str] = set()
        _collect_cols(expr_node, ctx, used)
        if not used <= {tv.key}:
            raise DaxError(
                f"{fname}() วนบน VALUES({tv.key}) ได้เฉพาะเมื่อนิพจน์อ้างคอลัมน์เดียวกัน "
                "— กรณีอื่นต้องใช้ context transition ซึ่งเครื่องจำลองนี้ยังไม่รองรับ"
            )
        pool = np.flatnonzero(tv.mask)
        if pool.size == 0:
            return np.array([]), pool
        _, first = np.unique(ctx.model.arr[tv.key][pool], return_index=True)
        idx = pool[np.sort(first)]
    elif isinstance(tv, TableVal):
        idx = np.flatnonzero(tv.mask)
    else:
        raise DaxError(f"{fname}() ต้องรับ 'ตาราง' เป็นอาร์กิวเมนต์แรก")

    if idx.size == 0:
        return np.array([]), idx
    vals = ev(expr_node, ctx.derive(row_idx=idx))
    if not _is_vec(vals):
        vals = np.full(idx.size, vals)
    return vals, idx


# ---------------------------------------------------------------------------
# ตัวกรองภายใน CALCULATE
# ---------------------------------------------------------------------------
def _collect_cols(node, ctx: Ctx, out: set) -> None:
    """เก็บรายชื่อคอลัมน์ทั้งหมดที่นิพจน์อ้างถึง (ใช้ตัดสินว่า CALCULATE ต้องถอดตัวกรองใด)"""
    if isinstance(node, tuple) and node and node[0] == "col":
        if node[1] or not ctx.model.measure_name(node[2]):
            try:
                out.add(ctx.model.col_key(node[1], node[2]))
            except DaxError:
                pass
        return
    if isinstance(node, (tuple, list)):
        for x in node:
            if isinstance(x, (tuple, list)):
                _collect_cols(x, ctx, out)


def _drop_table_filters(filters: dict, table: str) -> None:
    prefix = f"{table}["
    for k in [k for k in filters if k.startswith(prefix)]:
        del filters[k]


_PRED_OPS = {"=", "<>", "<", ">", "<=", ">=", "&&", "||", "IN"}


def _is_predicate(node) -> bool:
    """เงื่อนไขแบบ Table[Col] = ... ที่ต้องประเมินเป็นเวกเตอร์ทั้งตาราง"""
    if node[0] == "bin" and node[1] in _PRED_OPS:
        return True
    return node[0] == "un" and node[1] == "NOT"


def _predicate_mask(node, ctx: Ctx) -> np.ndarray:
    pred = ev(node, ctx.derive(row_idx=np.arange(ctx.model.n)))
    if not _is_vec(pred):
        pred = np.full(ctx.model.n, _truth(pred))
    return pred.astype(bool)


def _apply_filter_arg(node, ctx: Ctx, filters: dict, keep: bool = False) -> None:
    """นำอาร์กิวเมนต์ตัวกรองของ CALCULATE ไปปรับ filter context"""
    if node[0] == "func":
        fname = node[1]
        if fname in ("ALL", "REMOVEFILTERS"):
            _apply_all(node[2], ctx, filters)
            return
        if fname == "ALLEXCEPT":
            _apply_allexcept(node[2], ctx, filters)
            return
        if fname == "KEEPFILTERS":
            _need(node[2], 1, 1, "KEEPFILTERS")
            _apply_filter_arg(node[2][0], ctx, filters, keep=True)
            return

    if node[0] == "col":
        # เขียนชื่อคอลัมน์เปล่า ๆ เป็นตัวกรอง — Power BI ก็ไม่รับเช่นกัน แต่คนลองบ่อย
        ref = f"{node[1]}[{node[2]}]" if node[1] else f"[{node[2]}]"
        raise DaxError(
            f"ตัวกรองของ CALCULATE ต้องเป็นเงื่อนไข ไม่ใช่ชื่อคอลัมน์เปล่า ๆ — "
            f'เขียนเป็น {ref} = TRUE() หรือ {ref} = "ค่าที่ต้องการ" แทน'
        )

    if _is_predicate(node):
        # เงื่อนไขเชิงตรรกะ เช่น  Machine[Line] = "Line A"
        # ความหมายใน DAX คือ FILTER(ALL(Machine[Line]), Machine[Line] = "Line A")
        # → ตัวกรองเดิม "ของคอลัมน์นั้น" ถูกแทนที่ ไม่ใช่นำมา AND กัน
        cols: set[str] = set()
        _collect_cols(node, ctx, cols)
        if not cols:
            raise DaxError(
                "อาร์กิวเมนต์ตัวกรองของ CALCULATE ต้องอ้างถึงคอลัมน์อย่างน้อยหนึ่งคอลัมน์ "
                'เช่น CALCULATE(SUM(...), Machine[Line] = "Line A")'
            )
        pred = _predicate_mask(node, ctx)
        if keep:
            filters[ctx.next_anon()] = pred
        elif len(cols) == 1:
            filters[next(iter(cols))] = pred
        else:
            for c in cols:
                filters.pop(c, None)
            filters[ctx.next_anon()] = pred
        return

    val = ev(node, ctx)

    if isinstance(val, TableVal):
        if not keep and val.table:
            _drop_table_filters(filters, val.table)
        filters[ctx.next_anon()] = val.mask
        return
    if isinstance(val, ValuesVal):
        if not keep:
            filters.pop(val.key, None)
        filters[ctx.next_anon()] = val.mask
        return

    raise DaxError(
        "อาร์กิวเมนต์ตัวกรองของ CALCULATE ต้องเป็นเงื่อนไข (เช่น Machine[Line] = \"Line A\") "
        "หรือเป็นตาราง (เช่น FILTER(...), ALL(...)) — ค่าเดี่ยวใช้เป็นตัวกรองไม่ได้"
    )


def _apply_all(args, ctx: Ctx, filters: dict) -> None:
    if not args:
        filters.clear()
        return
    for a in args:
        if a[0] == "col":
            filters.pop(_col_node_key(a, ctx, "ALL"), None)
        elif a[0] in ("name", "tname"):
            t = ctx.model.table_name(a[1])
            if t is None:
                raise DaxError(f"ALL() ไม่รู้จักตาราง '{a[1]}'")
            _drop_table_filters(filters, t)
        else:
            raise DaxError("ALL() รับได้เฉพาะชื่อตารางหรือชื่อคอลัมน์")


def _apply_allexcept(args, ctx: Ctx, filters: dict) -> None:
    if len(args) < 2:
        raise DaxError("ALLEXCEPT() ต้องมีชื่อตาราง แล้วตามด้วยคอลัมน์ที่ต้องการคงไว้")
    t = ctx.model.table_name(args[0][1]) if args[0][0] in ("name", "tname") else None
    if t is None:
        raise DaxError("อาร์กิวเมนต์แรกของ ALLEXCEPT() ต้องเป็นชื่อตาราง")
    keep = {_col_node_key(a, ctx, "ALLEXCEPT") for a in args[1:]}
    prefix = f"{t}["
    for k in [k for k in filters if k.startswith(prefix) and k not in keep]:
        del filters[k]


# ---------------------------------------------------------------------------
# Time intelligence — คืนชุดวันที่เป็น TableVal ของตารางวันที่
# ---------------------------------------------------------------------------
def _date_key_from(node, ctx: Ctx, fname: str) -> str:
    key = _col_node_key(node, ctx, fname)
    if not np.issubdtype(ctx.model.arr[key].dtype, np.datetime64):
        raise DaxError(f"{fname}() ต้องรับคอลัมน์ชนิดวันที่ เช่น Date[Date]")
    return key


def _ctx_dates(ctx: Ctx, key: str) -> np.ndarray:
    d = ctx.model.arr[key][ctx.mask()]
    if d.size == 0:
        raise DaxError("ไม่มีวันที่อยู่ใน filter context ปัจจุบัน")
    return d


def _dates_mask(ctx: Ctx, key: str, wanted: np.ndarray) -> TableVal:
    m = np.isin(ctx.model.arr[key], wanted)
    return TableVal(m, ctx.model.table_of(key))


def _f_datesytd(args, ctx: Ctx):
    _need(args, 1, 1, "DATESYTD")
    key = _date_key_from(args[0], ctx, "DATESYTD")
    d = _ctx_dates(ctx, key)
    last = pd.Timestamp(d.max())
    start = pd.Timestamp(year=last.year, month=1, day=1)
    col = ctx.model.arr[key]
    return TableVal((col >= np.datetime64(start)) & (col <= np.datetime64(last)),
                    ctx.model.table_of(key))


def _shift(dates: np.ndarray, n: int, unit: str) -> np.ndarray:
    idx = pd.DatetimeIndex(pd.unique(dates))
    if unit == "YEAR":
        out = idx + pd.DateOffset(years=n)
    elif unit == "QUARTER":
        out = idx + pd.DateOffset(months=3 * n)
    elif unit == "MONTH":
        out = idx + pd.DateOffset(months=n)
    elif unit == "DAY":
        out = idx + pd.DateOffset(days=n)
    else:
        raise DaxError("หน่วยเวลาต้องเป็น DAY, MONTH, QUARTER หรือ YEAR")
    return out.to_numpy()


def _f_sameperiodlastyear(args, ctx: Ctx):
    _need(args, 1, 1, "SAMEPERIODLASTYEAR")
    key = _date_key_from(args[0], ctx, "SAMEPERIODLASTYEAR")
    return _dates_mask(ctx, key, _shift(_ctx_dates(ctx, key), -1, "YEAR"))


def _f_dateadd(args, ctx: Ctx):
    _need(args, 3, 3, "DATEADD")
    key = _date_key_from(args[0], ctx, "DATEADD")
    n = int(ev(args[1], ctx))
    unit = args[2][1].upper() if args[2][0] == "name" else str(ev(args[2], ctx)).upper()
    return _dates_mask(ctx, key, _shift(_ctx_dates(ctx, key), n, unit))


def _f_previousmonth(args, ctx: Ctx):
    _need(args, 1, 1, "PREVIOUSMONTH")
    key = _date_key_from(args[0], ctx, "PREVIOUSMONTH")
    first = pd.Timestamp(_ctx_dates(ctx, key).min())
    target = (first.replace(day=1) - pd.DateOffset(months=1))
    col = ctx.model.arr[key]
    ym = pd.DatetimeIndex(col)
    m = (ym.year == target.year) & (ym.month == target.month)
    return TableVal(np.asarray(m), ctx.model.table_of(key))


def _f_previousyear(args, ctx: Ctx):
    _need(args, 1, 1, "PREVIOUSYEAR")
    key = _date_key_from(args[0], ctx, "PREVIOUSYEAR")
    year = pd.Timestamp(_ctx_dates(ctx, key).max()).year - 1
    m = pd.DatetimeIndex(ctx.model.arr[key]).year == year
    return TableVal(np.asarray(m), ctx.model.table_of(key))


def _f_datesinperiod(args, ctx: Ctx):
    _need(args, 4, 4, "DATESINPERIOD")
    key = _date_key_from(args[0], ctx, "DATESINPERIOD")
    start = _to_dt(ev(args[1], ctx))
    n = int(ev(args[2], ctx))
    unit = args[3][1].upper() if args[3][0] == "name" else str(ev(args[3], ctx)).upper()
    other = _shift(np.array([start.to_datetime64()]), n, unit)[0]
    lo, hi = (start.to_datetime64(), other) if n >= 0 else (other, start.to_datetime64())
    col = ctx.model.arr[key]
    return TableVal((col >= lo) & (col <= hi), ctx.model.table_of(key))


def _f_totalytd(args, ctx: Ctx):
    _need(args, 2, 2, "TOTALYTD")
    filters = dict(ctx.filters)
    tv = _f_datesytd([args[1]], ctx)
    _drop_table_filters(filters, tv.table)
    filters[ctx.next_anon()] = tv.mask
    return ev(args[0], ctx.derive(filters=filters, row_idx=None))


# ---------------------------------------------------------------------------
# FORMAT — รองรับรูปแบบที่ใช้บ่อย
# ---------------------------------------------------------------------------
def _format(value, fmt: str) -> str:
    if value is None:
        return ""
    f = fmt.strip()
    fl = f.lower()
    if fl in ("percent", "0%", "0.0%", "0.00%", "#,##0%"):
        digits = 0 if fl in ("percent", "0%", "#,##0%") else fl.split(".")[1].count("0")
        return f"{float(value) * 100:,.{digits}f}%"
    if fl in ("yyyy-mm-dd", "short date"):
        return _to_dt(value).strftime("%Y-%m-%d")
    if fl == "mmm yyyy":
        return _to_dt(value).strftime("%b %Y")
    if fl in ("mmmm", "mmm"):
        return _to_dt(value).strftime("%B" if fl == "mmmm" else "%b")
    if fl == "yyyy":
        return _to_dt(value).strftime("%Y")
    if "0" in f or "#" in f:
        digits = len(f.split(".")[1].replace("#", "0").rstrip()) if "." in f else 0
        comma = "," if "," in f else ""
        return f"{float(value):{comma}.{digits}f}"
    return str(value)


# ---------------------------------------------------------------------------
# ตารางฟังก์ชัน
# ---------------------------------------------------------------------------
def _simple_agg(fn, name):
    def handler(args, ctx: Ctx):
        _need(args, 1, 1, name)
        vals = _numeric(_agg_values(args[0], ctx, name))
        vals = vals[~pd.isna(vals)]
        if vals.size == 0:
            return None
        return _py(fn(vals))
    return handler


def _simple_aggx(fn, name):
    def handler(args, ctx: Ctx):
        _need(args, 2, 2, name)
        vals, _ = _iterate(args[0], args[1], ctx, name)
        vals = _numeric(np.asarray(vals))
        vals = vals[~pd.isna(vals)]
        if vals.size == 0:
            return None
        return _py(fn(vals))
    return handler


def _f_calculate(args, ctx: Ctx):
    if not args:
        raise DaxError("CALCULATE() ต้องมีนิพจน์อย่างน้อยหนึ่งตัว")
    filters = dict(ctx.filters)
    for a in args[1:]:
        _apply_filter_arg(a, ctx, filters)
    return ev(args[0], ctx.derive(filters=filters, row_idx=None))


def _f_filter(args, ctx: Ctx):
    _need(args, 2, 2, "FILTER")
    tv = _table_arg(args[0], ctx, "FILTER")
    idx = np.flatnonzero(tv.mask)
    out = np.zeros(ctx.model.n, dtype=bool)
    if idx.size:
        pred = ev(args[1], ctx.derive(row_idx=idx))
        if not _is_vec(pred):
            pred = np.full(idx.size, _truth(pred))
        out[idx[pred.astype(bool)]] = True
    return TableVal(out, tv.table)


def _f_all(args, ctx: Ctx):
    """ALL() ที่ใช้เป็น 'ตาราง' (ไม่ได้อยู่ในตำแหน่งตัวกรองของ CALCULATE)"""
    if not args:
        return TableVal(np.ones(ctx.model.n, dtype=bool), ctx.model.fact)
    a = args[0]
    if a[0] in ("name", "tname"):
        t = ctx.model.table_name(a[1])
        if t is None:
            raise DaxError(f"ALL() ไม่รู้จักตาราง '{a[1]}'")
        return TableVal(np.ones(ctx.model.n, dtype=bool), t)
    if a[0] == "col":
        key = _col_node_key(a, ctx, "ALL")
        filters = {k: v for k, v in ctx.filters.items() if k != key}
        m = np.ones(ctx.model.n, dtype=bool)
        for f in filters.values():
            m &= f
        return ValuesVal(key, m, ctx.model.table_of(key))
    raise DaxError("ALL() รับได้เฉพาะชื่อตารางหรือชื่อคอลัมน์")


def _f_values(args, ctx: Ctx):
    _need(args, 1, 1, "VALUES")
    a = args[0]
    if a[0] in ("name", "tname"):
        t = ctx.model.table_name(a[1])
        return TableVal(ctx.mask(), t)
    key = _col_node_key(a, ctx, "VALUES")
    return ValuesVal(key, ctx.mask(), ctx.model.table_of(key))


def _f_countrows(args, ctx: Ctx):
    _need(args, 0, 1, "COUNTROWS")
    if not args:
        tv = TableVal(ctx.mask(), ctx.model.fact)
    else:
        v = ev(args[0], ctx)
        if isinstance(v, ValuesVal):
            vals = ctx.model.arr[v.key][v.mask]
            return int(pd.unique(vals).size)
        if not isinstance(v, TableVal):
            raise DaxError("COUNTROWS() ต้องรับตาราง")
        tv = v
    if tv.table and tv.table != ctx.model.fact:
        key = ctx.model.keys.get(tv.table)
        if key:
            return int(pd.unique(ctx.model.arr[key][tv.mask]).size)
    return int(tv.mask.sum())


def _f_distinctcount(args, ctx: Ctx):
    _need(args, 1, 1, "DISTINCTCOUNT")
    vals = _agg_values(args[0], ctx, "DISTINCTCOUNT")
    vals = vals[~pd.isna(vals)]
    return int(pd.unique(vals).size)


def _f_count(args, ctx: Ctx):
    _need(args, 1, 1, "COUNT")
    vals = _agg_values(args[0], ctx, "COUNT")
    return int((~pd.isna(vals)).sum())


def _f_countblank(args, ctx: Ctx):
    _need(args, 1, 1, "COUNTBLANK")
    vals = _agg_values(args[0], ctx, "COUNTBLANK")
    return int(pd.isna(vals).sum())


def _f_divide(args, ctx: Ctx):
    _need(args, 2, 3, "DIVIDE")
    a = _num(ev(args[0], ctx))
    b = _num(ev(args[1], ctx))
    alt = ev(args[2], ctx) if len(args) == 3 else None
    if _is_vec(a) or _is_vec(b):
        a_arr = np.asarray(a, dtype=float)
        b_arr = np.asarray(b, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            out = np.divide(a_arr, b_arr, out=np.full(np.broadcast(a_arr, b_arr).shape,
                                                      np.nan, dtype=float),
                            where=(b_arr != 0))
        if alt is not None:
            out = np.where(b_arr == 0, alt, out)
        return out
    if b == 0 or b is None:
        return alt
    return _py(a / b)


def _f_if(args, ctx: Ctx):
    _need(args, 2, 3, "IF")
    cond = ev(args[0], ctx)
    if _is_vec(cond):
        t = ev(args[1], ctx)
        f = ev(args[2], ctx) if len(args) == 3 else None
        t = np.full(cond.shape, t) if not _is_vec(t) else t
        f = np.full(cond.shape, np.nan if f is None else f) if not _is_vec(f) else f
        if t.dtype.kind in "US" or f.dtype.kind in "US":
            return np.where(cond.astype(bool), t.astype(object), f.astype(object))
        return np.where(cond.astype(bool), t, f)
    if _truth(cond):
        return ev(args[1], ctx)
    return ev(args[2], ctx) if len(args) == 3 else None


def _f_switch(args, ctx: Ctx):
    if len(args) < 3:
        raise DaxError("SWITCH() ต้องมีอย่างน้อย 3 อาร์กิวเมนต์")
    head = ev(args[0], ctx)
    if _is_vec(head):
        raise DaxError("SWITCH() ยังไม่รองรับการทำงานแบบเวกเตอร์ใน row context")
    pairs = args[1:]
    i = 0
    while i + 1 < len(pairs):
        cand = ev(pairs[i], ctx)
        hit = _truth(cand) if isinstance(head, bool) and head is True else (head == cand)
        if hit:
            return ev(pairs[i + 1], ctx)
        i += 2
    return ev(pairs[-1], ctx) if len(pairs) % 2 == 1 else None


def _f_iferror(args, ctx: Ctx):
    _need(args, 2, 2, "IFERROR")
    try:
        v = ev(args[0], ctx)
        if isinstance(v, float) and math.isnan(v):
            return ev(args[1], ctx)
        return v
    except DaxError:
        return ev(args[1], ctx)


def _f_related(args, ctx: Ctx):
    _need(args, 1, 1, "RELATED")
    return ev(args[0], ctx)


def _f_selectedvalue(args, ctx: Ctx):
    _need(args, 1, 2, "SELECTEDVALUE")
    key = _col_node_key(args[0], ctx, "SELECTEDVALUE")
    vals = pd.unique(ctx.model.arr[key][ctx.mask()])
    if vals.size == 1:
        return _py(vals[0])
    return ev(args[1], ctx) if len(args) == 2 else None


def _f_hasonevalue(args, ctx: Ctx):
    _need(args, 1, 1, "HASONEVALUE")
    key = _col_node_key(args[0], ctx, "HASONEVALUE")
    return bool(pd.unique(ctx.model.arr[key][ctx.mask()]).size == 1)


def _f_isblank(args, ctx: Ctx):
    _need(args, 1, 1, "ISBLANK")
    v = ev(args[0], ctx)
    if _is_vec(v):
        return pd.isna(v)
    return v is None or (isinstance(v, float) and math.isnan(v))


def _math1(fn, name, cast=float):
    def handler(args, ctx: Ctx):
        _need(args, 1, 1, name)
        v = _num(ev(args[0], ctx))
        if _is_vec(v):
            return fn(np.asarray(v, dtype=float))
        return _py(cast(fn(float(v))))
    return handler


def _f_round(args, ctx: Ctx):
    _need(args, 2, 2, "ROUND")
    v = _num(ev(args[0], ctx))
    d = int(ev(args[1], ctx))
    if _is_vec(v):
        return np.round(np.asarray(v, dtype=float), d)
    return _py(round(float(v), d))


def _text1(fn, name):
    def handler(args, ctx: Ctx):
        _need(args, 1, 1, name)
        v = ev(args[0], ctx)
        if _is_vec(v):
            return np.array([fn(str(x)) if x is not None else None for x in v], dtype=object)
        return fn("" if v is None else str(v))
    return handler


def _f_left(args, ctx: Ctx):
    _need(args, 1, 2, "LEFT")
    v = ev(args[0], ctx)
    n = int(ev(args[1], ctx)) if len(args) == 2 else 1
    if _is_vec(v):
        return np.array([str(x)[:n] for x in v], dtype=object)
    return str(v)[:n]


def _f_right(args, ctx: Ctx):
    _need(args, 1, 2, "RIGHT")
    v = ev(args[0], ctx)
    n = int(ev(args[1], ctx)) if len(args) == 2 else 1
    if _is_vec(v):
        return np.array([str(x)[-n:] for x in v], dtype=object)
    return str(v)[-n:]


def _f_concatenate(args, ctx: Ctx):
    _need(args, 2, 2, "CONCATENATE")
    return _eval_bin(("bin", "&", args[0], args[1]), ctx)


def _f_concatenatex(args, ctx: Ctx):
    _need(args, 2, 3, "CONCATENATEX")
    vals, _ = _iterate(args[0], args[1], ctx, "CONCATENATEX")
    sep = ev(args[2], ctx) if len(args) == 3 else ""
    return str(sep).join(_fmt_default(v) for v in vals if v is not None)


def _f_format(args, ctx: Ctx):
    _need(args, 2, 2, "FORMAT")
    return _format(ev(args[0], ctx), str(ev(args[1], ctx)))


def _f_blank(args, ctx: Ctx):
    _need(args, 0, 0, "BLANK")
    return None


def _f_year(args, ctx: Ctx):
    _need(args, 1, 1, "YEAR")
    v = ev(args[0], ctx)
    if _is_vec(v):
        return pd.DatetimeIndex(v).year.to_numpy()
    return _to_dt(v).year


def _f_month(args, ctx: Ctx):
    _need(args, 1, 1, "MONTH")
    v = ev(args[0], ctx)
    if _is_vec(v):
        return pd.DatetimeIndex(v).month.to_numpy()
    return _to_dt(v).month


def _f_day(args, ctx: Ctx):
    _need(args, 1, 1, "DAY")
    v = ev(args[0], ctx)
    if _is_vec(v):
        return pd.DatetimeIndex(v).day.to_numpy()
    return _to_dt(v).day


def _f_date(args, ctx: Ctx):
    _need(args, 3, 3, "DATE")
    return pd.Timestamp(int(ev(args[0], ctx)), int(ev(args[1], ctx)), int(ev(args[2], ctx)))


def _f_and(args, ctx: Ctx):
    _need(args, 2, 2, "AND")
    return _eval_bin(("bin", "&&", args[0], args[1]), ctx)


def _f_or(args, ctx: Ctx):
    _need(args, 2, 2, "OR")
    return _eval_bin(("bin", "||", args[0], args[1]), ctx)


def _f_not(args, ctx: Ctx):
    _need(args, 1, 1, "NOT")
    v = ev(args[0], ctx)
    return np.logical_not(v) if _is_vec(v) else (not _truth(v))


def _f_distinct(args, ctx: Ctx):
    return _f_values(args, ctx)


def _f_min_max(fn, name):
    """MIN/MAX รับได้ทั้งคอลัมน์เดียว และตัวเลขสองตัว (MIN(a, b))"""
    def handler(args, ctx: Ctx):
        if len(args) == 2:
            a, b = _num(ev(args[0], ctx)), _num(ev(args[1], ctx))
            if _is_vec(a) or _is_vec(b):
                return (np.minimum if name == "MIN" else np.maximum)(a, b)
            return _py(min(a, b) if name == "MIN" else max(a, b))
        _need(args, 1, 1, name)
        vals = _agg_values(args[0], ctx, name)
        vals = vals[~pd.isna(vals)]
        if vals.size == 0:
            return None
        raw = vals.min() if name == "MIN" else vals.max()
        if np.issubdtype(np.asarray(vals).dtype, np.datetime64):
            return pd.Timestamp(raw)
        return _py(raw)
    return handler


FUNCS = {
    # รวมยอด
    "SUM": _simple_agg(np.sum, "SUM"),
    "AVERAGE": _simple_agg(np.mean, "AVERAGE"),
    "MEDIAN": _simple_agg(np.median, "MEDIAN"),
    "MIN": _f_min_max(min, "MIN"),
    "MAX": _f_min_max(max, "MAX"),
    "STDEV.P": _simple_agg(lambda v: np.std(v), "STDEV.P"),
    "STDEV.S": _simple_agg(lambda v: np.std(v, ddof=1), "STDEV.S"),
    "COUNT": _f_count,
    "COUNTA": _f_count,
    "COUNTBLANK": _f_countblank,
    "COUNTROWS": _f_countrows,
    "DISTINCTCOUNT": _f_distinctcount,
    # ตระกูล X
    "SUMX": _simple_aggx(np.sum, "SUMX"),
    "AVERAGEX": _simple_aggx(np.mean, "AVERAGEX"),
    "MINX": _simple_aggx(np.min, "MINX"),
    "MAXX": _simple_aggx(np.max, "MAXX"),
    "MEDIANX": _simple_aggx(np.median, "MEDIANX"),
    "COUNTX": _simple_aggx(lambda v: v.size, "COUNTX"),
    "COUNTAX": _simple_aggx(lambda v: v.size, "COUNTAX"),
    "CONCATENATEX": _f_concatenatex,
    # บริบทตัวกรอง
    "CALCULATE": _f_calculate,
    "FILTER": _f_filter,
    "ALL": _f_all,
    "REMOVEFILTERS": _f_all,
    "ALLEXCEPT": lambda a, c: TableVal(np.ones(c.model.n, dtype=bool), None),
    "VALUES": _f_values,
    "DISTINCT": _f_distinct,
    "SELECTEDVALUE": _f_selectedvalue,
    "HASONEVALUE": _f_hasonevalue,
    "KEEPFILTERS": lambda a, c: ev(a[0], c),
    "RELATED": _f_related,
    # ตรรกะ
    "IF": _f_if,
    "SWITCH": _f_switch,
    "IFERROR": _f_iferror,
    "AND": _f_and,
    "OR": _f_or,
    "NOT": _f_not,
    "ISBLANK": _f_isblank,
    "BLANK": _f_blank,
    "TRUE": lambda a, c: True,
    "FALSE": lambda a, c: False,
    # คณิตศาสตร์
    "DIVIDE": _f_divide,
    "ROUND": _f_round,
    "ABS": _math1(np.abs, "ABS"),
    "INT": _math1(np.floor, "INT", int),
    "SQRT": _math1(np.sqrt, "SQRT"),
    "CEILING": _math1(np.ceil, "CEILING"),
    "FLOOR": _math1(np.floor, "FLOOR"),
    "POWER": lambda a, c: _num(ev(a[0], c)) ** _num(ev(a[1], c)),
    # ข้อความ
    "LEN": _text1(len, "LEN"),
    "UPPER": _text1(str.upper, "UPPER"),
    "LOWER": _text1(str.lower, "LOWER"),
    "TRIM": _text1(str.strip, "TRIM"),
    "LEFT": _f_left,
    "RIGHT": _f_right,
    "CONCATENATE": _f_concatenate,
    "FORMAT": _f_format,
    # วันที่
    "YEAR": _f_year,
    "MONTH": _f_month,
    "DAY": _f_day,
    "DATE": _f_date,
    # Time intelligence
    "DATESYTD": _f_datesytd,
    "TOTALYTD": _f_totalytd,
    "SAMEPERIODLASTYEAR": _f_sameperiodlastyear,
    "DATEADD": _f_dateadd,
    "PREVIOUSMONTH": _f_previousmonth,
    "PREVIOUSYEAR": _f_previousyear,
    "DATESINPERIOD": _f_datesinperiod,
}

# ฟังก์ชันยอดนิยมที่ยังไม่รองรับ — บอกผู้เรียนตรง ๆ ดีกว่าปล่อยให้งง
_UNSUPPORTED = {
    "RANKX": "จัดอันดับ — ต้องใช้ context transition",
    "TOPN": "คัดอันดับต้น ๆ — ต้องใช้ตารางเสมือน",
    "EARLIER": "อ้าง row context ชั้นนอก — เลิกใช้แล้วใน DAX สมัยใหม่ ให้ใช้ VAR แทน",
    "SUMMARIZE": "สร้างตารางสรุป — เป็นฟังก์ชันฝั่ง DAX Query",
    "ADDCOLUMNS": "เพิ่มคอลัมน์ให้ตารางเสมือน",
    "GENERATE": "รวมตารางเสมือน",
    "USERELATIONSHIP": "สลับความสัมพันธ์ — โมเดลจำลองนี้ join ไว้แล้ว",
    "CROSSFILTER": "สลับทิศทางตัวกรอง",
    "PATH": "ลำดับชั้นแบบพ่อ-ลูก",
    "LOOKUPVALUE": "ค้นค่าข้ามตาราง — ในโมเดลจำลองใช้อ้างคอลัมน์ตรง ๆ ได้เลย",
}


def _eval_func(node, ctx: Ctx):
    name = node[1]
    handler = FUNCS.get(name)
    if handler is None:
        why = _UNSUPPORTED.get(name)
        if why:
            raise DaxError(
                f"เครื่องจำลองนี้ยังไม่รองรับ {name}() ({why}) — "
                "ลองใช้ฟังก์ชันอื่น หรือไปทดสอบสูตรนี้บน Power BI Desktop จริง"
            )
        raise DaxError(f"ไม่รู้จักฟังก์ชัน {name}()")
    return handler(node[2], ctx)


# ===========================================================================
# 7) ประตูใช้งานหลัก
# ===========================================================================
def build_filters(model: Model, selections: dict[str, list] | None) -> dict[str, np.ndarray]:
    """แปลง {'Machine[Line]': ['A','B']} เป็น filter context"""
    filters: dict[str, np.ndarray] = {}
    for key, vals in (selections or {}).items():
        if not vals:
            continue
        real = model._col_lower.get(key.lower(), key)
        if real not in model.arr:
            raise DaxError(f"ไม่พบคอลัมน์ {key}")
        filters[real] = np.isin(model.arr[real], np.array(vals, dtype=object))
    return filters


def evaluate(dax: str, model: Model, selections: dict[str, list] | None = None):
    """คำนวณสูตร DAX หนึ่งบรรทัด คืนค่าสเกลาร์ (หรือ None เมื่อผลเป็น BLANK)"""
    if not dax or not dax.strip():
        raise DaxError("ยังไม่ได้เขียนสูตร")
    text = dax.strip()
    # อนุญาตให้พิมพ์แบบ  ชื่อ Measure = สูตร  แล้วตัดหัวทิ้งให้
    m = re.match(r"^\s*([^\W\d]\w*(?:\s+\w+)*)\s*=\s*(?![=<>])", text, re.UNICODE)
    if m and not text.upper().startswith("VAR "):
        head = m.group(1).strip().upper()
        if head not in FUNCS and head not in ("VAR", "RETURN"):
            text = text[m.end():]
    node = parse_dax(text)
    ctx = Ctx(model, build_filters(model, selections))
    val = ev(node, ctx)
    if isinstance(val, (TableVal, ValuesVal)):
        raise DaxError("สูตรนี้คืนค่าเป็น 'ตาราง' — measure ต้องคืนค่าเดี่ยว "
                       "ลองครอบด้วย COUNTROWS() หรือฟังก์ชันรวมยอด")
    if _is_vec(val):
        raise DaxError("สูตรนี้ยังอยู่ใน row context — ต้องครอบด้วยฟังก์ชันรวมยอด เช่น SUMX()")
    return _blank_if_nan(_py(val))


def values_of(model: Model, key: str) -> list:
    real = model._col_lower.get(key.lower(), key)
    return sorted(pd.unique(model.arr[real]).tolist())
