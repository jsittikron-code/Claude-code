// engine.js — ฉาก 3D สำหรับโมเดลตัวแทนเครื่องจักร (three.js r128)
//
// หน้าที่: ตั้งกล้อง แสง พื้น เสาไฟสถานะ อนุภาค และแอนิเมชันเข้า/ออกเมื่อเปลี่ยนเครื่อง
// ตัวโมเดลแต่ละชนิดอยู่ใน models.js · การคุยกับ Streamlit อยู่ใน index.html
//
// ใช้ผ่าน  M3D.init(canvas, hud) → M3D.setTheme(theme) → M3D.show(args)
//   args = { code, name, kind, variant, group, status_text, beacon, motion, accent, brand, model }
//   beacon  = green | yellow | red | grey   (ไฟที่เสาสถานะ)
//   motion  = run | idle | stop             (ชิ้นส่วนขยับเร็ว / ช้า / หยุดนิ่ง)
window.M3D = (function () {
  const MODELS = window.M3D_MODELS;
  const PI = Math.PI;
  let canvas, wrap, hud, renderer, scene, camera;
  let hemi, key, fill, rim, spot, arcLight;
  let floor, grid, ring, pool, fogColor;
  let theme = { base: "dark", bg: "#0e1117", fg: "#fafafa" };
  const orbit = { theta: .8, phi: 1.05, radius: 9, radius0: 9, min: 3, max: 20, target: new THREE.Vector3(0, .8, 0),
                  auto: true, lastUser: -1e9, drag: false, px: 0, py: 0 };
  let cur = null;          // โมเดลที่แสดงอยู่ {root, m, M, args, t, intro, emitters, segs, glow, size}
  let pending = null;      // args ที่รอสร้างหลังโมเดลเดิมออกจากฉาก
  let outro = null;        // เวลาเริ่มแอนิเมชันออก
  let wire = false;
  let now = performance.now() / 1000;

  // ---------- สี / วัสดุ ----------
  function col(hex) { return new THREE.Color(hex).convertSRGBToLinear(); }
  function mat(hex, o) { return new THREE.MeshStandardMaterial(Object.assign({ color: col(hex), metalness: .45, roughness: .5 }, o || {})); }
  function glow(hex, i) { return new THREE.MeshStandardMaterial({ color: col(hex), emissive: col(hex), emissiveIntensity: i || 1.2, metalness: .1, roughness: .4 }); }
  function shade(hex, f) { const c = new THREE.Color(hex); c.multiplyScalar(f); return "#" + c.getHexString(); }
  function makeMats(accent) {
    return {
      steel: mat("#a7b0ba", { metalness: .75, roughness: .32 }),
      steelDark: mat("#5f6b78", { metalness: .7, roughness: .4 }),
      frame: mat("#2f353d", { metalness: .5, roughness: .62 }),
      dark: mat("#191c21", { metalness: .3, roughness: .8 }),
      accent: mat(accent, { metalness: .35, roughness: .42 }),
      accent2: mat(shade(accent, .62), { metalness: .4, roughness: .5 }),
      safety: mat("#f2b705", { metalness: .3, roughness: .5 }),
      rubber: mat("#141414", { metalness: .1, roughness: .95 }),
      wood: mat("#d4a76a", { metalness: 0, roughness: .85 }),
      wood2: mat("#9c7246", { metalness: 0, roughness: .85 }),
      edge: mat("#f5f1e6", { metalness: 0, roughness: .6 }),
      laminate: mat("#e8e3d8", { metalness: .05, roughness: .6 }),
      white: mat("#e9edf1", { metalness: .2, roughness: .45 }),
      cloth: mat("#c54b8c", { metalness: 0, roughness: .95 }),
      carton: mat("#c99a5b", { metalness: 0, roughness: .9 }),
      carton2: mat("#b3864a", { metalness: 0, roughness: .9 }),
      strap: mat("#1f6fd6", { metalness: .2, roughness: .5 }),
      blue: mat("#3b86d6", { metalness: .4, roughness: .4 }),
      glue: mat("#e8d9a0", { metalness: 0, roughness: .3 }),
      glass: new THREE.MeshPhysicalMaterial({ color: col("#8fc3ff"), transparent: true, opacity: .28, metalness: .1, roughness: .08, side: THREE.DoubleSide }),
      film: new THREE.MeshPhysicalMaterial({ color: col("#d8ecff"), transparent: true, opacity: .22, metalness: 0, roughness: .2, side: THREE.DoubleSide }),
      water: new THREE.MeshPhysicalMaterial({ color: col("#3b9bff"), transparent: true, opacity: .45, metalness: .2, roughness: .1 }),
      waterLine: glow("#bfe3ff", 1.0),
      screen: glow("#49a6ff", 1.3),
      lamp: glow("#fff1c2", 1.6),
      heat: glow("#ff7a3d", .9),
      ledG: glow("#2ee36a", 1.5),
      ledR: glow("#ff4d4d", 1.5),
      lampOff: new THREE.MeshStandardMaterial({ color: col("#3a3f47"), transparent: true, opacity: .75, metalness: .2, roughness: .3 }),
    };
  }
  const BEACON = { green: "#2ee36a", yellow: "#ffc43d", red: "#ff4d4d", grey: null };

  // ---------- เสาไฟสถานะ ----------
  function stackLight(root, M, pos, which) {
    const g = new THREE.Group(); g.position.set(pos[0], pos[1], pos[2]); root.add(g);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(.014, .014, .3, 10), M.steelDark); pole.position.y = .15; pole.castShadow = true; g.add(pole);
    const segs = {};
    [["red", .30], ["yellow", .36], ["green", .42]].forEach(([k, y]) => {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(.034, .034, .055, 20), M.lampOff);
      m.position.y = y + .0275; g.add(m); segs[k] = m;
    });
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(.036, .036, .014, 20), M.dark); cap.position.y = .485; g.add(cap);
    let sprite = null;
    const hex = BEACON[which];
    if (hex) {
      segs[which].material = glow(hex, 2.2);
      sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex(hex), transparent: true, opacity: .9, depthWrite: false, blending: THREE.AdditiveBlending }));
      sprite.position.y = segs[which].position.y; sprite.scale.set(.5, .5, 1); g.add(sprite);
    }
    return { g, segs, sprite, which };
  }
  const _tex = {};
  function glowTex(hex) {
    if (_tex[hex]) return _tex[hex];
    const c = document.createElement("canvas"); c.width = c.height = 128;
    const x = c.getContext("2d"); const gr = x.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, hex); gr.addColorStop(.35, hex + "aa"); gr.addColorStop(1, hex + "00");
    x.fillStyle = gr; x.fillRect(0, 0, 128, 128);
    return _tex[hex] = new THREE.CanvasTexture(c);
  }
  function dotTex() {
    if (_tex.dot) return _tex.dot;
    const c = document.createElement("canvas"); c.width = c.height = 32;
    const x = c.getContext("2d"); const gr = x.createRadialGradient(16, 16, 0, 16, 16, 16);
    gr.addColorStop(0, "#ffffff"); gr.addColorStop(.5, "#ffffffaa"); gr.addColorStop(1, "#ffffff00");
    x.fillStyle = gr; x.fillRect(0, 0, 32, 32);
    return _tex.dot = new THREE.CanvasTexture(c);
  }

  // ---------- อนุภาค (เศษไม้ / ประกายไฟ / ละอองสี / ฝุ่น) ----------
  const FX = {
    chips:  { n: 60, size: .045, color: 0xe2c48a, speed: 1.6, grav: -4.5, life: .7, spread: .7, blend: THREE.NormalBlending, dir: [0, 1, 0] },
    sparks: { n: 90, size: .03, color: 0xffb347, speed: 2.6, grav: -6, life: .45, spread: .9, blend: THREE.AdditiveBlending, dir: [0, .6, 0] },
    mist:   { n: 70, size: .09, color: 0x9fd0ff, speed: 1.1, grav: -.2, life: 1.1, spread: .35, blend: THREE.AdditiveBlending, dir: [0, 0, -1] },
    dust:   { n: 50, size: .04, color: 0xd9c08a, speed: .7, grav: -.6, life: 1.2, spread: .5, blend: THREE.NormalBlending, dir: [0, 1, 0] },
  };
  function makeEmitter(root, spec) {
    const base = FX[spec.type] || FX.dust;
    const n = base.n;
    const pos = new Float32Array(n * 3), vel = new Float32Array(n * 3), life = new Float32Array(n);
    for (let i = 0; i < n; i++) life[i] = -1;
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const m = new THREE.PointsMaterial({ color: col("#" + (spec.color || base.color).toString(16).padStart(6, "0")), size: base.size, map: dotTex(),
      transparent: true, opacity: .95, depthWrite: false, blending: base.blend, sizeAttenuation: true });
    const pts = new THREE.Points(geo, m); pts.frustumCulled = false; root.add(pts);
    const dir = spec.dir || base.dir;
    const tmp = new THREE.Vector3();
    return {
      spec, pts, acc: 0,
      update(dt, speed) {
        const active = !!spec.active && speed > 0;
        spec.obj.getWorldPosition(tmp); root.worldToLocal(tmp);
        const rate = (spec.rate || 1) * 40 * speed;
        this.acc += active ? rate * dt : 0;
        for (let i = 0; i < n; i++) {
          if (life[i] >= 0) {
            life[i] += dt;
            if (life[i] > base.life) { life[i] = -1; pos[i * 3 + 1] = -99; continue; }
            vel[i * 3 + 1] += base.grav * dt;
            pos[i * 3] += vel[i * 3] * dt; pos[i * 3 + 1] += vel[i * 3 + 1] * dt; pos[i * 3 + 2] += vel[i * 3 + 2] * dt;
            if (pos[i * 3 + 1] < .01) { pos[i * 3 + 1] = .01; vel[i * 3 + 1] *= -.2; vel[i * 3] *= .6; vel[i * 3 + 2] *= .6; }
          } else if (this.acc >= 1) {
            this.acc -= 1; life[i] = 0;
            pos[i * 3] = tmp.x; pos[i * 3 + 1] = tmp.y; pos[i * 3 + 2] = tmp.z;
            const s = base.speed * (.5 + Math.random());
            vel[i * 3] = (dir[0] + (Math.random() - .5) * base.spread) * s;
            vel[i * 3 + 1] = (dir[1] + (Math.random() - .5) * base.spread) * s;
            vel[i * 3 + 2] = (dir[2] + (Math.random() - .5) * base.spread) * s;
          }
        }
        geo.attributes.position.needsUpdate = true;
      },
      dispose() { root.remove(pts); geo.dispose(); m.dispose(); },
    };
  }

  // ---------- ฉาก ----------
  function init(c, w, h) {
    canvas = c; wrap = w; hud = h;
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.setClearColor(0x000000, 0);
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(36, 1, .05, 200);
    hemi = new THREE.HemisphereLight(0x9ec0ff, 0x1c1f24, .6); scene.add(hemi);
    key = new THREE.DirectionalLight(0xffffff, 1.15); key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -.0008; key.shadow.normalBias = .02; scene.add(key);
    fill = new THREE.DirectionalLight(0xa9c9ff, .35); scene.add(fill);
    rim = new THREE.PointLight(0xffffff, .9, 30, 2); scene.add(rim);
    spot = new THREE.SpotLight(0xffffff, .55, 0, .6, .6, 1); scene.add(spot); scene.add(spot.target);
    arcLight = new THREE.PointLight(0xffd27a, 0, 4, 2); scene.add(arcLight);
    applyTheme();
    bindInput();
    new ResizeObserver(resize).observe(wrap);
    resize();
    requestAnimationFrame(loop);
  }

  function resize() {
    const w = wrap.clientWidth || 300, h = wrap.clientHeight || 300;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    if (cur) fit(cur.size);
  }

  function setTheme(t) {
    if (!t) return;
    theme = { base: t.base || "dark", bg: t.backgroundColor || (t.base === "light" ? "#ffffff" : "#0e1117"), fg: t.textColor || (t.base === "light" ? "#31333f" : "#fafafa") };
    applyTheme();
  }
  function applyTheme() {
    const light = theme.base === "light";
    const bg2 = light ? "#f4f6fa" : shade(theme.bg, 1.9);
    wrap.style.setProperty("--bg", theme.bg); wrap.style.setProperty("--bg2", bg2); wrap.style.setProperty("--fg", theme.fg);
    wrap.style.setProperty("--muted", light ? "rgba(49,51,63,.62)" : "rgba(250,250,250,.62)");
    wrap.style.setProperty("--chip", light ? "rgba(0,0,0,.05)" : "rgba(255,255,255,.07)");
    wrap.style.setProperty("--line", light ? "rgba(0,0,0,.12)" : "rgba(255,255,255,.12)");
    fogColor = col(light ? "#dfe4ec" : shade(theme.bg, 1.25));
    scene.fog = new THREE.Fog(fogColor, 10, 40);
    hemi.intensity = light ? .9 : .6;
    if (floor) { floor.material.color = col(light ? "#dde2ea" : shade(theme.bg, 1.55)); }
    if (grid) { grid.material.opacity = light ? .25 : .35; }
  }

  function buildFloor(size, accent) {
    if (floor) { scene.remove(floor); scene.remove(grid); scene.remove(ring); scene.remove(pool); }
    const r = Math.max(size * .95, 2.2);
    floor = new THREE.Mesh(new THREE.CircleGeometry(r, 72), new THREE.MeshStandardMaterial({ color: col(theme.base === "light" ? "#dde2ea" : shade(theme.bg, 1.55)), metalness: .1, roughness: .9 }));
    floor.rotation.x = -PI / 2; floor.position.y = -.004; floor.receiveShadow = true; scene.add(floor);
    grid = new THREE.GridHelper(r * 2.3, 22, col(shade(accent, .9)), col(theme.base === "light" ? "#c3cad6" : "#2a3038"));
    grid.material.transparent = true; grid.material.opacity = theme.base === "light" ? .25 : .35; grid.position.y = .002; scene.add(grid);
    ring = new THREE.Mesh(new THREE.RingGeometry(r * .985, r * 1.0, 96), new THREE.MeshBasicMaterial({ color: col(accent), transparent: true, opacity: .7, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
    ring.rotation.x = -PI / 2; ring.position.y = .003; scene.add(ring);
    pool = new THREE.Mesh(new THREE.CircleGeometry(r * .8, 64), new THREE.MeshBasicMaterial({ map: glowTex(accent), transparent: true, opacity: theme.base === "light" ? .16 : .22, blending: THREE.AdditiveBlending, depthWrite: false }));
    pool.rotation.x = -PI / 2; pool.position.y = .001; scene.add(pool);
    scene.fog.near = r * 3.2; scene.fog.far = r * 9;
  }

  function fit(size) {
    // ระยะกล้องที่ทำให้เครื่องอยู่ในกรอบทุกมุมหมุน: ด้านกว้างใช้เส้นทแยงของฐาน (x,z)
    // เทียบกับมุมมองแนวนอนของกล้อง ด้านสูงเทียบกับมุมมองแนวตั้ง แล้วเอาค่าที่ไกลกว่า
    const vfov = camera.fov * PI / 180;
    const aspect = camera.aspect || 1.6;
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * aspect);
    const diag = Math.sqrt(size.x * size.x + size.z * size.z);
    const rH = (diag / 2) / Math.tan(hfov / 2) * 1.04;
    const rV = (size.y * 1.35 / 2) / Math.tan(vfov / 2) * 1.1 + diag * .25;
    const maxDim = Math.max(size.x, size.z, size.y);
    let r = Math.max(rH, rV, maxDim * 1.2);
    orbit.radius0 = r; orbit.min = r * .45; orbit.max = r * 2.4;
    orbit.radius = Math.min(Math.max(orbit.radius, orbit.min), orbit.max);
    orbit.target.set(0, size.y * .42, 0);
    camera.far = Math.max(60, r * 8);
    camera.updateProjectionMatrix();
    const d = Math.max(maxDim, 3);
    key.position.set(d * .9, d * 1.5, d * .8);
    key.shadow.camera.left = -d; key.shadow.camera.right = d; key.shadow.camera.top = d; key.shadow.camera.bottom = -d;
    key.shadow.camera.near = .5; key.shadow.camera.far = d * 5; key.shadow.camera.updateProjectionMatrix();
    fill.position.set(-d, d * .7, -d * .6);
    rim.position.set(0, d * .9, -d * .9); rim.distance = d * 4;
    spot.position.set(0, d * 2.2, d * .3); spot.target.position.set(0, size.y * .4, 0); spot.distance = d * 5;
  }

  // ---------- สร้าง / เปลี่ยนโมเดล ----------
  function show(args) {
    if (cur && cur.args && cur.args.code === args.code && cur.args.kind === args.kind && cur.args.beacon === args.beacon) {
      // เครื่องเดิม: อัปเดตเฉพาะข้อความและความเร็ว ไม่สร้างใหม่
      cur.args = args; setHud(args, cur.m); return;
    }
    if (cur) { pending = args; outro = outro || now; }
    else build(args);
  }
  function build(args) {
    disposeCurrent();
    const accent = args.accent || "#4f7fb6";
    const M = makeMats(accent);
    Object.values(M).forEach(m => { m.wireframe = wire; });
    const root = new THREE.Group(); scene.add(root);
    const builder = MODELS[args.kind] || MODELS.generic;
    let m;
    try { m = builder(root, M, args.variant || {}); }
    catch (e) { console.error("machine3d: build failed", args.kind, e); root.clear(); m = MODELS.generic(root, M, {}); }
    // จัดให้กึ่งกลางเครื่องอยู่ที่จุดกำเนิด และวางบนพื้น
    const box = new THREE.Box3().setFromObject(root);
    const size = new THREE.Vector3(); box.getSize(size);
    const center = new THREE.Vector3(); box.getCenter(center);
    root.children.forEach(c => { c.position.x -= center.x; c.position.z -= center.z; c.position.y -= box.min.y; });
    const bpos = m.beacon ? [m.beacon[0] - center.x, m.beacon[1] - box.min.y, m.beacon[2] - center.z] : [size.x / 2 + .2, 0, size.z / 2 + .2];
    const beacon = stackLight(root, M, bpos, args.beacon || "green");
    const emitters = (m.fx || []).map(s => makeEmitter(root, s));
    // แอนิเมชันเข้า: ชิ้นส่วนร่วงลงมาประกอบทีละชิ้น (เรียงจากต่ำไปสูง)
    const parts = root.children.filter(c => c !== beacon.g && !(c instanceof THREE.Points));
    parts.sort((a, b) => a.position.y - b.position.y);
    const drop = Math.max(size.y, 1.5) * .8;
    parts.forEach((c, i) => { c.userData.ty = c.position.y; c.userData.delay = Math.min(i * .035, .55); c.userData.drop = drop; });
    beacon.g.userData.ty = beacon.g.position.y; beacon.g.userData.delay = .6; beacon.g.userData.drop = drop;
    buildFloor(Math.max(size.x, size.z), accent);
    wrap.style.setProperty("--accent", accent);
    cur = { root, m, M, args, t: 0, t0: now, size, emitters, beacon, parts: parts.concat([beacon.g]), accent };
    orbit.radius = orbit.radius0 = 0; fit(size); orbit.radius = orbit.radius0;
    setHud(args, m);
    scanLine();
  }
  function disposeCurrent() {
    if (!cur) return;
    cur.emitters.forEach(e => e.dispose());
    cur.root.traverse(o => { if (o.geometry && !o.geometry.userData.shared) { /* geometry ใช้ร่วมกันผ่าน cache ใน models.js จึงไม่ dispose */ } });
    scene.remove(cur.root);
    cur = null;
  }

  // ---------- HUD ----------
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function hexToRgba(hex, a) { const c = new THREE.Color(hex); return "rgba(" + Math.round(c.r * 255) + "," + Math.round(c.g * 255) + "," + Math.round(c.b * 255) + "," + a + ")"; }
  function setHud(a, m) {
    if (!hud) return;
    const accent = a.accent || "#4f7fb6";
    const label = a.kind_label || (MODELS._labels || {})[a.kind] || a.kind;
    const dot = BEACON[a.beacon] || "#9aa4ae";
    const brand = [a.brand, a.model].filter(Boolean).join(" · ");
    hud.querySelector(".code").textContent = a.code || "";
    hud.querySelector(".name").textContent = a.name || "";
    hud.querySelector(".name").title = a.name || "";
    const chips = hud.querySelector(".chips"); chips.innerHTML = "";
    if (a.group) { const s = document.createElement("span"); s.className = "chip grp"; s.textContent = a.group; s.style.background = hexToRgba(accent, .28); s.style.borderColor = hexToRgba(accent, .55); chips.appendChild(s); }
    const k = document.createElement("span"); k.className = "chip"; k.textContent = "โมเดลตัวแทน · " + label; chips.appendChild(k);
    const st = hud.querySelector(".st"); st.style.setProperty("--dot", dot);
    st.querySelector("span").textContent = a.status_text || "";
    st.style.display = a.status_text ? "" : "none";
    hud.querySelector(".bl").textContent = brand;
    hud.querySelector(".btn-auto").classList.toggle("on", orbit.auto);
    hud.querySelector(".btn-wire").classList.toggle("on", wire);
  }
  function scanLine() {
    const s = hud && hud.querySelector(".scan"); if (!s) return;
    s.style.transition = "none"; s.style.top = "0%"; s.style.opacity = "0";
    requestAnimationFrame(() => { s.style.transition = "top .9s ease-in-out, opacity .3s"; s.style.opacity = ".9"; s.style.top = "100%"; setTimeout(() => s.style.opacity = "0", 800); });
  }
  function setWire(v) { wire = v; if (cur) Object.values(cur.M).forEach(m => m.wireframe = v); if (hud) hud.querySelector(".btn-wire").classList.toggle("on", v); }
  function setAuto(v) { orbit.auto = v; if (hud) hud.querySelector(".btn-auto").classList.toggle("on", v); }
  function resetView() { orbit.theta = .8; orbit.phi = 1.05; orbit.radius = orbit.radius0; orbit.lastUser = -1e9; }

  // ---------- เมาส์ / สัมผัส ----------
  function bindInput() {
    canvas.addEventListener("pointerdown", e => { orbit.drag = true; orbit.px = e.clientX; orbit.py = e.clientY; canvas.setPointerCapture(e.pointerId); canvas.classList.add("drag"); orbit.lastUser = now; });
    canvas.addEventListener("pointermove", e => {
      if (!orbit.drag) return;
      const dx = e.clientX - orbit.px, dy = e.clientY - orbit.py; orbit.px = e.clientX; orbit.py = e.clientY;
      orbit.theta -= dx * .0065; orbit.phi = Math.min(1.5, Math.max(.3, orbit.phi - dy * .0065)); orbit.lastUser = now;
    });
    const up = e => { orbit.drag = false; canvas.classList.remove("drag"); orbit.lastUser = now; };
    canvas.addEventListener("pointerup", up); canvas.addEventListener("pointercancel", up);
    canvas.addEventListener("wheel", e => { e.preventDefault(); orbit.radius = Math.min(orbit.max, Math.max(orbit.min, orbit.radius * (1 + e.deltaY * .0012))); orbit.lastUser = now; }, { passive: false });
    canvas.addEventListener("dblclick", resetView);
    if (hud) {
      hud.querySelector(".btn-auto").addEventListener("click", () => setAuto(!orbit.auto));
      hud.querySelector(".btn-wire").addEventListener("click", () => setWire(!wire));
      hud.querySelector(".btn-reset").addEventListener("click", resetView);
    }
  }

  // ---------- วนเฟรม ----------
  const easeOutCubic = p => 1 - Math.pow(1 - p, 3);
  const easeOutBack = p => 1 + 2.2 * Math.pow(p - 1, 3) + 1.2 * Math.pow(p - 1, 2);
  let prevNow = -1;
  function loop() {
    requestAnimationFrame(loop);
    // เวลาจริง (วินาที) ใช้กับแอนิเมชันเข้า/ออกและกล้อง เพื่อให้จบตรงเวลาแม้เฟรมเรตต่ำ
    now = performance.now() / 1000;
    const real = prevNow < 0 ? 0 : Math.min(now - prevNow, .5); prevNow = now;
    // dt สำหรับฟิสิกส์อนุภาคและชิ้นส่วนขยับ — จำกัดไว้ไม่ให้กระโดดเมื่อแท็บถูกพักแล้วกลับมา
    const dt = Math.min(real, .05);
    // แอนิเมชันออกของเครื่องเดิม แล้วสร้างเครื่องใหม่
    if (outro != null && cur) {
      const p = (now - outro) / .28;
      if (p >= 1) { outro = null; const a = pending; pending = null; build(a); }
      else { const s = 1 - easeOutCubic(p); cur.root.scale.set(s, s, s); cur.root.rotation.y += real * 5; }
    }
    if (cur) {
      const a = cur.args;
      const speed = a.motion === "stop" ? 0 : a.motion === "idle" ? .35 : 1;
      cur.t += dt * speed;
      // แอนิเมชันเข้า
      const age = now - cur.t0;
      if (age < 1.3) {
        cur.parts.forEach(c => {
          const p = Math.min(1, Math.max(0, (age - c.userData.delay) / .65));
          c.position.y = c.userData.ty + c.userData.drop * (1 - easeOutCubic(p));
        });
        const sp = Math.min(1, age / .9); const s = .82 + .18 * easeOutBack(sp); cur.root.scale.set(s, s, s);
      } else if (cur.root.scale.x !== 1 && outro == null) { cur.root.scale.set(1, 1, 1); cur.parts.forEach(c => c.position.y = c.userData.ty); }
      try { cur.m.tick(cur.t, speed); } catch (e) { /* อย่าให้โมเดลเดียวทำทั้งฉากล่ม */ }
      cur.emitters.forEach(e => e.update(dt, speed));
      // ไฟอาร์ค (เครื่องเชื่อม)
      if (cur.m.arc && speed > 0) { const tmp = new THREE.Vector3(); cur.m.arc.getWorldPosition(tmp); arcLight.position.copy(tmp); arcLight.intensity = 1.2 + Math.random() * 2.2; }
      else arcLight.intensity = 0;
      // เสาไฟสถานะกะพริบ
      if (cur.beacon.sprite) {
        const w = cur.beacon.which;
        const pulse = w === "red" ? (Math.sin(now * 9) > 0 ? 1 : .15) : w === "yellow" ? .55 + .45 * Math.sin(now * 3) : .7 + .3 * Math.sin(now * 2);
        cur.beacon.sprite.material.opacity = pulse;
        cur.beacon.segs[w].material.emissiveIntensity = .8 + 1.8 * pulse;
      }
      if (ring) ring.material.opacity = .45 + .3 * Math.sin(now * 1.4);
    }
    // กล้องหมุนเองเมื่อไม่มีใครลาก
    if (orbit.auto && !orbit.drag && now - orbit.lastUser > 2.5) orbit.theta += real * .22;
    const r = orbit.radius || 9;
    camera.position.set(orbit.target.x + r * Math.sin(orbit.phi) * Math.sin(orbit.theta), orbit.target.y + r * Math.cos(orbit.phi), orbit.target.z + r * Math.sin(orbit.phi) * Math.cos(orbit.theta));
    camera.lookAt(orbit.target);
    const t1 = performance.now();
    renderer.render(scene, camera);
    adapt(performance.now() - t1, real);
  }

  // ---------- ปรับคุณภาพอัตโนมัติ ----------
  // คอมบางเครื่องในออฟฟิศไม่มีการ์ดจอแยก ถ้าวาดเฟรมหนึ่งนานเกิน ~35 ms ติดต่อกัน
  // ให้ลดคุณภาพลงทีละขั้น (ขนาดเงา → ความละเอียด → ปิดเงา) และไม่ปรับกลับขึ้นเพื่อไม่ให้กระตุก
  const stats = { renderMs: 0, ema: 0, frames: 0, fps: 0, level: 2, _acc: 0, _n: 0 };
  function adapt(ms, real) {
    stats.renderMs = ms; stats.ema = stats.ema ? stats.ema * .9 + ms * .1 : ms; stats.frames++;
    stats._acc += real; stats._n++;
    if (stats._acc >= 1) { stats.fps = stats._n / stats._acc; stats._acc = 0; stats._n = 0; }
    if (stats.frames > 40 && stats.frames % 20 === 0 && stats.ema > 35 && stats.level > 0) {
      stats.level--;
      if (stats.level === 1) { key.shadow.mapSize.set(1024, 1024); key.shadow.map && key.shadow.map.dispose(); key.shadow.map = null; renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.25)); }
      if (stats.level === 0) { renderer.shadowMap.enabled = false; renderer.setPixelRatio(1); scene.traverse(o => { if (o.material) o.material.needsUpdate = true; }); }
      resize();
    }
  }

  return { init, setTheme, show, setWire, setAuto, resetView, stats: () => Object.assign({}, stats),
           kinds: () => Object.keys(MODELS).filter(k => k[0] !== "_"), labels: () => MODELS._labels };
})();
