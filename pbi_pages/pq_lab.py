"""ฝึก Power Query — โจทย์สถานการณ์จริง ทั้งแบบเรียงลำดับขั้นตอนและแบบเลือกคำตอบ"""

import streamlit as st

from pbi import progress as pg, ui
from pbi.exercises import PQ_BY_ID, PQ_EXERCISES, PQ_GROUPS, TOTAL_PQ, grade_pq

d = ui.data()
solved = {k for k, v in d["pq"].items() if v.get("solved")}

st.title("ฝึก Power Query")
st.caption(f"ผ่านแล้ว {len(solved)}/{TOTAL_PQ} ข้อ · "
           "โจทย์ทั้งหมดมาจากสถานการณ์ที่เจอจริงกับไฟล์ Excel ในโรงงาน")

group = st.segmented_control(
    "ชุดแบบฝึกหัด", PQ_GROUPS, default=PQ_GROUPS[0],
    format_func=lambda g: f"{g}  ({sum(1 for e in PQ_EXERCISES if e['group'] == g and e['id'] in solved)}"
                          f"/{sum(1 for e in PQ_EXERCISES if e['group'] == g)})",
) or PQ_GROUPS[0]

in_group = [e for e in PQ_EXERCISES if e["group"] == group]
ex_id = st.selectbox(
    "ข้อที่", [e["id"] for e in in_group],
    format_func=lambda i: ("✓ " if i in solved else "") + PQ_BY_ID[i]["title"],
)
ex = PQ_BY_ID[ex_id]

st.divider()
st.subheader(ex["title"])
st.markdown(ex["scenario"])

result_key = f"pq_result_{ex_id}"

# ---------------------------------------------------------------------------
# แบบเรียงลำดับขั้นตอน
# ---------------------------------------------------------------------------
if ex["kind"] == "order":
    st.caption("คลิกเลือกขั้นตอนเรียงตามลำดับที่ควรทำ — ลำดับที่คลิกคือคำตอบของคุณ")
    # สลับตัวเลือกให้ไม่เรียงตามเฉลย แต่คงที่ทุกครั้งที่รีเฟรช (ไม่ใช้ค่าสุ่ม)
    order = sorted(range(len(ex["steps"])), key=lambda i: (i * 7 + 3) % len(ex["steps"]))
    labels = {i: ex["steps"][i] for i in order}

    picked = st.multiselect(
        "ลำดับขั้นตอน", order, format_func=lambda i: labels[i],
        key=f"pq_pick_{ex_id}",
    )
    for n, i in enumerate(picked, 1):
        st.caption(f"{n}. {labels[i]}")

    ready = len(picked) == len(ex["steps"])
    if not ready and picked:
        st.caption(f"เลือกครบทุกขั้นตอนก่อนตรวจ (เลือกแล้ว {len(picked)}/{len(ex['steps'])})")
    answer = picked

# ---------------------------------------------------------------------------
# แบบเลือกคำตอบ
# ---------------------------------------------------------------------------
else:
    answer = st.radio(
        "เลือกคำตอบที่ถูกที่สุด", range(len(ex["options"])),
        format_func=lambda i: ex["options"][i], index=None,
    )
    ready = answer is not None

if st.button("ตรวจคำตอบ", type="primary", disabled=not ready,
             icon=":material/play_arrow:"):
    ok = grade_pq(ex, answer)
    first = pg.record_pq(d, ex_id, ok)
    ui.save()
    st.session_state[result_key] = (ok, first)

if result_key in st.session_state:
    ok, first = st.session_state[result_key]
    if ok:
        msg = f"ถูกต้อง — ได้รับ {pg.XP_PQ_SOLVED} XP" if first else "ถูกต้อง"
        st.success(msg, icon=":material/check_circle:")
    else:
        st.error("ยังไม่ใช่ — ลองอ่านคำอธิบายด้านล่างแล้วลองใหม่", icon=":material/cancel:")

    with st.container(border=True):
        st.markdown("**คำอธิบาย**")
        st.markdown(ex["explain"])
        if ex["kind"] == "order":
            st.markdown("**ลำดับที่ถูกต้อง**")
            for n, i in enumerate(ex["answer"], 1):
                st.markdown(f"{n}. {ex['steps'][i]}")
        else:
            st.markdown(f"**คำตอบที่ถูก:** {ex['options'][ex['answer']]}")

st.divider()
st.caption(
    "โจทย์เหล่านี้ฝึกการ 'ตัดสินใจ' ซึ่งเป็นส่วนที่ยากจริงของ Power Query "
    "ส่วนการคลิกปุ่มเรียนรู้ได้ในไม่กี่นาที — ลองทำตามจริงในไฟล์งานของคุณควบคู่ไปด้วย"
)
