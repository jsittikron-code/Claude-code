"""ลูกโลก 3 มิติแสดงตำแหน่งเครื่องบินสด ๆ ทั่วโลก (ข้อมูล ADS-B จาก OpenSky Network)."""

from __future__ import annotations

import time

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Live flight globe",
    page_icon=":material/public:",
    layout="wide",
)

OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)

M_TO_FT = 3.28084
MS_TO_KT = 1.94384
MS_TO_FPM = 196.85
MERGE_THRESHOLD = 3_000

# แถบระดับความสูง = ordinal ramp สีน้ำเงินเฉดเดียว (บินสูง = สว่าง, บินต่ำ = เข้ม)
# ผ่าน validator ของสกิล dataviz บนพื้นหลังเข้ม #0d0d0d ครบทุกข้อ
ALT_BANDS: list[tuple[float, float, str, str]] = [
    (0, 10_000, "#184f95", "< 10,000 ft"),
    (10_000, 20_000, "#256abf", "10,000 – 20,000 ft"),
    (20_000, 30_000, "#3987e5", "20,000 – 30,000 ft"),
    (30_000, 38_000, "#6da7ec", "30,000 – 38,000 ft"),
    (38_000, float("inf"), "#b7d3f6", "> 38,000 ft"),
]
GROUND_COLOR = "#898781"  # muted ink — "อยู่บนพื้น" เป็นสถานะ ไม่ใช่ระดับความสูง
SERIES_1_DARK = "#3987e5"

GLOBE_TEXTURES = {
    "กลางคืน (ไฟเมือง)": "earth-night.jpg",
    "กลางวัน (blue marble)": "earth-blue-marble.jpg",
    "เรียบ เข้ม": "earth-dark.jpg",
}

# (ชื่อ, lat_min, lat_max, lon_min, lon_max) — ตรวจตามลำดับ กล่องแรกที่เข้าชนะ
REGIONS: list[tuple[str, float, float, float, float]] = [
    ("อเมริกาเหนือ", 15, 72, -170, -50),
    ("ลาตินอเมริกา / แคริบเบียน", -60, 15, -95, -30),
    ("แอตแลนติกเหนือ", 20, 72, -50, -10),
    ("ยุโรป", 30, 75, -10, 45),
    ("แอฟริกา", -40, 30, -20, 55),
    ("ตะวันออกกลาง", 10, 45, 30, 65),
    ("เอเชีย", -10, 75, 60, 150),
    ("โอเชียเนีย", -55, -10, 100, 180),
    ("แปซิฟิก", -55, 75, 150, 180),
]
OTHER_REGION = "อื่น ๆ / กลางมหาสมุทร"


# ------------------------------------------------------------------ ข้อมูล


class OpenSkyError(RuntimeError):
    """ดึงข้อมูลจาก OpenSky ไม่สำเร็จ."""


@st.cache_resource
def http_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = "mdf-flight-globe/1.0"
    return session


def credentials() -> tuple[str, str] | None:
    """อ่าน client credentials จาก .streamlit/secrets.toml ถ้ามี."""
    try:
        block = st.secrets["opensky"]
    except Exception:
        return None
    client_id = block.get("client_id")
    client_secret = block.get("client_secret")
    return (client_id, client_secret) if client_id and client_secret else None


@st.cache_data(ttl=1500, show_spinner=False)
def opensky_token(client_id: str, client_secret: str) -> str:
    """แลก client credentials เป็น access token (อายุจริง 30 นาที)."""
    resp = http_session().post(
        OPENSKY_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@st.cache_data(ttl=900, max_entries=4, show_spinner=False)
def fetch_states(bucket: int, _token: str | None) -> tuple[pd.DataFrame, int]:
    """ดึง state vector ทั้งโลกหนึ่งช็อต.

    `bucket` เป็นแค่กุญแจแคชตามช่วงเวลา — เปลี่ยนค่าเมื่อไหร่ถึงจะยิง API ใหม่
    ทำให้หลายแท็บ/หลายเซสชันใช้ข้อมูลรอบเดียวกันโดยไม่เปลืองโควตา
    """
    headers = {"Authorization": f"Bearer {_token}"} if _token else {}
    try:
        resp = http_session().get(OPENSKY_STATES_URL, headers=headers, timeout=60)
    except requests.RequestException as exc:
        raise OpenSkyError(f"ต่อ OpenSky ไม่ได้: {exc}") from exc

    if resp.status_code == 429:
        raise OpenSkyError(
            "OpenSky ตอบ 429 — โควตาหมดชั่วคราว ลองยืดช่วงรีเฟรช "
            "หรือใส่ credentials ใน .streamlit/secrets.toml"
        )
    if resp.status_code >= 400:
        raise OpenSkyError(f"OpenSky ตอบ HTTP {resp.status_code}")

    payload = resp.json()
    frame = pd.DataFrame(
        payload.get("states") or [],
        columns=[
            "icao24", "callsign", "origin_country", "time_position", "last_contact",
            "lon", "lat", "baro_alt_m", "on_ground", "vel_ms", "track",
            "vert_rate_ms", "sensors", "geo_alt_m", "squawk", "spi", "position_source",
        ],
    )
    return shape_states(frame), int(payload.get("time", time.time()))


def region_of(lat: float, lon: float) -> str:
    for name, la_min, la_max, lo_min, lo_max in REGIONS:
        if la_min <= lat <= la_max and lo_min <= lon <= lo_max:
            return name
    return OTHER_REGION


def band_color(alt_ft: float) -> str:
    for low, high, color, _ in ALT_BANDS:
        if low <= alt_ft < high:
            return color
    return ALT_BANDS[-1][2]


def shape_states(frame: pd.DataFrame) -> pd.DataFrame:
    """ทำความสะอาด แปลงหน่วย ติดป้ายภูมิภาคและสี."""
    if frame.empty:
        return frame

    frame = frame.dropna(subset=["lat", "lon"]).copy()
    numeric = ("lat", "lon", "baro_alt_m", "geo_alt_m", "vel_ms", "track", "vert_rate_ms")
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame["callsign"] = frame["callsign"].fillna("").astype(str).str.strip()
    frame["squawk"] = frame["squawk"].fillna("").astype(str)
    frame["on_ground"] = frame["on_ground"].fillna(False).astype(bool)

    alt_m = frame["baro_alt_m"].fillna(frame["geo_alt_m"]).fillna(0.0).clip(lower=0)
    frame["alt_ft"] = (alt_m * M_TO_FT).round().astype("int64")
    frame.loc[frame["on_ground"], "alt_ft"] = 0
    frame["speed_kt"] = (frame["vel_ms"].fillna(0) * MS_TO_KT).round().astype("int64")
    frame["vs_fpm"] = (frame["vert_rate_ms"].fillna(0) * MS_TO_FPM).round().astype("int64")
    frame["heading"] = frame["track"].fillna(0).round().astype("int64")

    frame["region"] = [region_of(la, lo) for la, lo in zip(frame["lat"], frame["lon"])]
    frame["color"] = [
        GROUND_COLOR if grounded else band_color(alt)
        for grounded, alt in zip(frame["on_ground"], frame["alt_ft"])
    ]
    return frame.reset_index(drop=True)


# ------------------------------------------------------------- คอมโพเนนต์

GLOBE_HTML = """
<div id="fg-wrap">
  <div id="fg-host"></div>
  <div id="fg-status">กำลังโหลดลูกโลก 3 มิติ…</div>
  <div id="fg-legend" hidden>
    <span class="fg-legend-title">ระดับความสูง</span>
    <div id="fg-legend-items"></div>
  </div>
</div>
"""

GLOBE_CSS = """
#fg-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: #0d0d0d;
  border: 1px solid rgba(255, 255, 255, 0.10);
}
#fg-host { width: 100%; height: 100%; }
#fg-host canvas { display: block; }
#fg-status {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  text-align: center;
  font: 500 14px system-ui, -apple-system, "Segoe UI", sans-serif;
  color: #c3c2b7;
  pointer-events: none;
}
#fg-legend {
  position: absolute;
  left: 12px;
  bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(13, 13, 13, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.10);
  backdrop-filter: blur(4px);
  font: 400 11px system-ui, -apple-system, "Segoe UI", sans-serif;
  color: #c3c2b7;
  pointer-events: none;
}
.fg-legend-title {
  display: block;
  margin-bottom: 6px;
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #898781;
}
.fg-legend-row { display: flex; align-items: center; gap: 7px; line-height: 1.7; }
.fg-swatch { width: 10px; height: 10px; border-radius: 2px; flex: none; }
.fg-tip {
  font: 400 12px system-ui, -apple-system, "Segoe UI", sans-serif;
  color: #ffffff;
  line-height: 1.55;
}
.fg-tip b { font-size: 13px; }
.fg-tip span { color: #c3c2b7; }
"""

GLOBE_JS = """
const GLOBE_SRC = "https://esm.sh/globe.gl@2";
const TEX = "https://unpkg.com/three-globe/example/img/";
const instances = new WeakMap();

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const num = (v) => Number(v ?? 0).toLocaleString("en-US");

function tooltip(d) {
  const title = d.cs ? esc(d.cs) : esc(d.ic).toUpperCase();
  const state = d.g
    ? "อยู่บนพื้น"
    : `${num(d.ft)} ft · ${num(d.kt)} kt · หัว ${num(d.hd)}°`;
  const vs = d.g || !d.vr ? "" : `<br><span>ไต่/ลด ${num(d.vr)} ft/min</span>`;
  const sq = d.sq ? `<br><span>squawk ${esc(d.sq)}</span>` : "";
  return (
    `<div class="fg-tip"><b>${title}</b><br><span>${esc(d.co)}</span>` +
    `<br><span>${state}</span>${vs}${sq}` +
    `<br><span>${d.lat.toFixed(2)}, ${d.lng.toFixed(2)} · ${esc(d.ic)}</span></div>`
  );
}

function drawLegend(root, legend) {
  const box = root.querySelector("#fg-legend");
  const list = root.querySelector("#fg-legend-items");
  if (!box || !list || !legend) return;
  const row = (color, label) =>
    `<div class="fg-legend-row"><span class="fg-swatch" ` +
    `style="background:${esc(color)}"></span>${esc(label)}</div>`;
  const rows = legend.items.map((it) => row(it.color, it.label));
  if (legend.hasGround) rows.push(row(legend.groundColor, "อยู่บนพื้น"));
  list.innerHTML = rows.join("");
  box.hidden = false;
}

function resize(rec, host) {
  const g = rec.globe;
  if (!g) return;
  const w = host.clientWidth;
  const h = host.clientHeight;
  if (w > 0) g.width(w);
  if (h > 0) g.height(h);
}

function apply(rec, cfg, host) {
  const g = rec.globe;
  if (!g) return;
  g.globeImageUrl(TEX + cfg.texture)
    .pointsMerge(!!cfg.merge)
    .pointColor((d) => d.c)
    .pointAltitude((d) => d.a)
    .pointRadius(cfg.radius)
    .pointLabel(cfg.merge ? () => "" : tooltip)
    .pointsData(cfg.points);
  const controls = g.controls();
  controls.autoRotate = !!cfg.rotate;
  controls.autoRotateSpeed = 0.32;
  resize(rec, host);
}

export default function (component) {
  const { data, parentElement } = component;
  const root = parentElement.querySelector("#fg-wrap");
  const host = parentElement.querySelector("#fg-host");
  if (!root || !host) return;

  const cfg = data || {};
  let rec = instances.get(host);

  if (!rec) {
    rec = { globe: null, pending: cfg, observer: null };
    instances.set(host, rec);

    import(GLOBE_SRC)
      .then(({ default: Globe }) => {
        const globe = new Globe(host)
          .backgroundColor("#0d0d0d")
          .backgroundImageUrl(TEX + "night-sky.png")
          .bumpImageUrl(TEX + "earth-topology.png")
          .atmosphereColor("#86b6ef")
          .atmosphereAltitude(0.16)
          .pointsTransitionDuration(0)
          .width(host.clientWidth || 900)
          .height(host.clientHeight || 640);
        globe.pointOfView({ lat: 22, lng: -40, altitude: 2.3 });
        rec.globe = globe;

        const status = root.querySelector("#fg-status");
        if (status) status.remove();

        rec.observer = new ResizeObserver(() => resize(rec, host));
        rec.observer.observe(host);

        const next = rec.pending || cfg;
        apply(rec, next, host);
        drawLegend(root, next.legend);
      })
      .catch((err) => {
        const status = root.querySelector("#fg-status");
        if (status) {
          status.textContent =
            "โหลดไลบรารีลูกโลกจาก esm.sh ไม่สำเร็จ " +
            "(ตรวจอินเทอร์เน็ต/ไฟร์วอลล์): " + err;
        }
      });
  }

  if (rec.globe) {
    apply(rec, cfg, host);
    drawLegend(root, cfg.legend);
  } else {
    rec.pending = cfg;
  }

  return () => {
    if (rec.observer) rec.observer.disconnect();
  };
}
"""

flight_globe = st.components.v2.component(
    "flight_globe",
    html=GLOBE_HTML,
    css=GLOBE_CSS,
    js=GLOBE_JS,
    isolate_styles=False,
)

ALT_SPAN_FT = 45_000.0


def globe_points(frame: pd.DataFrame) -> list[dict]:
    """แปลง DataFrame เป็นเรคคอร์ดสั้น ๆ ให้ globe.gl (คุมขนาด payload)."""
    return [
        {
            "lat": round(float(row.lat), 4),
            "lng": round(float(row.lon), 4),
            "a": round(0.004 + min(row.alt_ft / ALT_SPAN_FT, 1.0) * 0.085, 4),
            "c": row.color,
            "cs": row.callsign,
            "ic": row.icao24,
            "co": row.origin_country,
            "ft": int(row.alt_ft),
            "kt": int(row.speed_kt),
            "hd": int(row.heading),
            "vr": int(row.vs_fpm),
            "sq": row.squawk,
            "g": bool(row.on_ground),
        }
        for row in frame.itertuples()
    ]


def legend_payload(frame: pd.DataFrame) -> dict:
    return {
        "items": [{"color": color, "label": label} for _, _, color, label in ALT_BANDS],
        "groundColor": GROUND_COLOR,
        "hasGround": bool(frame["on_ground"].any()),
    }


# --------------------------------------------------------------------- แอป

creds = credentials()

st.title(":material/public: ลูกโลกเที่ยวบินสด")
st.caption(
    "ตำแหน่งเครื่องบินเรียลไทม์จาก ADS-B ของ OpenSky Network — "
    "ลากเพื่อหมุน สกรอลล์เพื่อซูม ชี้ที่จุดเพื่อดูรายละเอียดเที่ยวบิน"
)

# จองพื้นที่ sidebar ไว้ตามลำดับที่อยากให้แสดง แล้วค่อยเติมทีหลัง
# (ตัวกรองประเทศต้องรอรายชื่อจากข้อมูลรอบแรก)
sb_filters = st.sidebar.container()
sb_globe = st.sidebar.container()
sb_update = st.sidebar.container()

with sb_update:
    st.subheader("การอัปเดต")
    st.select_slider(
        "รีเฟรชทุก",
        options=[30, 60, 120, 300, 600],
        value=60 if creds else 300,
        format_func=lambda s: f"{s} วินาที" if s < 60 else f"{s // 60} นาที",
        key="refresh_sec",
    )
    if creds:
        st.success("ใช้ OpenSky credentials — โควตา 4,000 เครดิต/วัน", icon=":material/key:")
    else:
        st.info(
            "โหมดไม่ล็อกอิน โควตาราว 100 ครั้ง/วัน — ใส่ `[opensky]` พร้อม "
            "`client_id` / `client_secret` ใน `.streamlit/secrets.toml` เพื่อเพิ่มโควตา",
            icon=":material/info:",
        )


def load_frame() -> tuple[pd.DataFrame, int]:
    interval = st.session_state.refresh_sec
    token = opensky_token(*creds) if creds else None
    return fetch_states(int(time.time()) // interval, token)


# โหลดรอบแรกเพื่อเอารายชื่อประเทศมาทำตัวกรอง — รอบถัดไปกินจากแคชเดิม
try:
    seed_frame, _ = load_frame()
    seed_error: str | None = None
except OpenSkyError as exc:
    seed_frame, seed_error = pd.DataFrame(), str(exc)

country_options = (
    sorted(seed_frame["origin_country"].dropna().unique().tolist())
    if not seed_frame.empty
    else []
)
default_countries = ["United States"] if "United States" in country_options else []

with sb_filters:
    st.subheader("ตัวกรอง")
    st.multiselect(
        "ประเทศที่จดทะเบียน",
        options=country_options,
        default=default_countries,
        key="countries",
        placeholder="ว่าง = ทุกประเทศ",
    )
    st.segmented_control(
        "สถานะ",
        options=["กำลังบิน", "ทั้งหมด"],
        default="กำลังบิน",
        key="airborne_mode",
    )
    st.slider(
        "ระดับความสูง (ft)",
        min_value=0,
        max_value=50_000,
        value=(0, 50_000),
        step=1_000,
        key="alt_range",
    )
    st.slider(
        "จำนวนจุดสูงสุดบนลูกโลก",
        min_value=500,
        max_value=8_000,
        value=3_000,
        step=500,
        key="max_points",
        help=(
            f"เกิน {MERGE_THRESHOLD:,} จุดจะรวมเป็นก้อนเดียวเพื่อความลื่น "
            "ซึ่งทำให้ tooltip รายลำหายไป"
        ),
    )

with sb_globe:
    st.subheader("ลูกโลก")
    st.selectbox("พื้นผิวโลก", list(GLOBE_TEXTURES), key="texture")
    st.slider("ความสูงภาพ (px)", 420, 900, 640, 20, key="globe_height")
    st.checkbox("หมุนอัตโนมัติ", value=True, key="auto_rotate")


def apply_filters(frame: pd.DataFrame) -> pd.DataFrame:
    low, high = st.session_state.alt_range
    view = frame
    if st.session_state.airborne_mode == "กำลังบิน":
        view = view[~view["on_ground"]]
    if st.session_state.countries:
        view = view[view["origin_country"].isin(st.session_state.countries)]
    return view[view["alt_ft"].between(low, high)]


@st.fragment(run_every=st.session_state.refresh_sec)
def live_view() -> None:
    try:
        frame, snapshot = load_frame()
    except OpenSkyError as exc:
        st.error(str(exc), icon=":material/error:")
        cached = st.session_state.get("last_good")
        if cached is None:
            return
        frame, snapshot = cached
        st.warning("กำลังแสดงข้อมูลชุดล่าสุดที่ดึงสำเร็จ", icon=":material/history:")
    else:
        st.session_state.last_good = (frame, snapshot)

    view = apply_filters(frame)
    airborne = view[~view["on_ground"]]
    age = max(0, int(time.time()) - snapshot)
    stamp = time.strftime("%H:%M:%S", time.localtime(snapshot))

    with st.container(horizontal=True):
        st.metric("ตรงเงื่อนไข", f"{len(view):,}", border=True)
        st.metric("กำลังบิน", f"{len(airborne):,}", border=True)
        st.metric("อยู่บนพื้น", f"{len(view) - len(airborne):,}", border=True)
        st.metric(
            "สูงเฉลี่ย",
            f"{int(airborne['alt_ft'].mean()):,} ft" if len(airborne) else "—",
            border=True,
        )
        st.metric(
            "เร็วสุด",
            f"{int(airborne['speed_kt'].max()):,} kt" if len(airborne) else "—",
            border=True,
        )
        st.metric(
            "อายุข้อมูล",
            f"{age} วิ",
            f"snapshot {stamp}",
            delta_color="off",
            border=True,
        )

    if view.empty:
        st.info("ไม่มีเครื่องบินที่ตรงเงื่อนไขในรอบนี้", icon=":material/search_off:")
        return

    cap = st.session_state.max_points
    shown = view.nlargest(cap, "alt_ft") if len(view) > cap else view
    merge = len(shown) > MERGE_THRESHOLD

    flight_globe(
        key="globe",
        data={
            "points": globe_points(shown),
            "legend": legend_payload(shown),
            "texture": GLOBE_TEXTURES[st.session_state.texture],
            "rotate": st.session_state.auto_rotate,
            "radius": 0.16 if len(shown) < 1_500 else 0.12,
            "merge": merge,
        },
        height=st.session_state.globe_height,
    )

    notes = []
    if len(view) > cap:
        notes.append(
            f"แสดง {len(shown):,} จาก {len(view):,} ลำ (เลือกลำที่บินสูงสุด) — "
            "ปรับ “จำนวนจุดสูงสุดบนลูกโลก” ในแถบด้านข้างเพื่อดูมากขึ้น"
        )
    if merge:
        notes.append(
            f"จุดเกิน {MERGE_THRESHOLD:,} จึงรวมเป็นก้อนเดียวเพื่อความลื่น — ไม่มี tooltip รายลำ"
        )
    if notes:
        st.caption(" · ".join(notes))

    left, right = st.columns([1, 1.4])
    with left:
        with st.container(border=True):
            st.subheader("กระจายตามภูมิภาค")
            by_region = (
                view["region"]
                .value_counts()
                .rename_axis("ภูมิภาค")
                .reset_index(name="ลำ")
            )
            st.bar_chart(
                by_region,
                x="ภูมิภาค",
                y="ลำ",
                horizontal=True,
                color=SERIES_1_DARK,
                height=320,
            )
    with right:
        with st.container(border=True):
            st.subheader("40 ลำที่บินสูงสุด")
            st.dataframe(
                view.nlargest(40, "alt_ft")[
                    ["callsign", "icao24", "origin_country", "region",
                     "alt_ft", "speed_kt", "heading", "lat", "lon"]
                ],
                hide_index=True,
                height=320,
                column_config={
                    "callsign": st.column_config.TextColumn("Callsign", width="small"),
                    "icao24": st.column_config.TextColumn("ICAO24", width="small"),
                    "origin_country": st.column_config.TextColumn("ประเทศ"),
                    "region": st.column_config.TextColumn("ภูมิภาค"),
                    "alt_ft": st.column_config.NumberColumn("สูง (ft)", format="localized"),
                    "speed_kt": st.column_config.NumberColumn("เร็ว (kt)", format="localized"),
                    "heading": st.column_config.NumberColumn("หัวเครื่อง", format="%d°"),
                    "lat": st.column_config.NumberColumn("Lat", format="%.2f"),
                    "lon": st.column_config.NumberColumn("Lon", format="%.2f"),
                },
            )

    with st.expander("ข้อมูลดิบรอบนี้"):
        st.download_button(
            "บันทึกเป็น CSV",
            view.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"flights_{stamp.replace(':', '')}.csv",
            mime="text/csv",
            icon=":material/download:",
        )


if seed_error and "last_good" not in st.session_state:
    st.error(seed_error, icon=":material/error:")
else:
    live_view()
