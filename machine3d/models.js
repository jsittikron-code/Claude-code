// models.js — ตัวสร้างโมเดล 3D "ตัวแทน" ของเครื่องจักรแต่ละชนิด
//
// โมเดลพวกนี้ไม่ใช่รูปจริงของเครื่อง แต่เป็นรูปแบบสัญลักษณ์ (stylized) ที่สร้างจาก
// กล่อง/ทรงกระบอก ให้คนดูรู้ทันทีว่าเป็นเครื่องประเภทไหน และมีชิ้นส่วนที่ขยับได้
// (ใบเลื่อยหมุน แผ่นวิ่งผ่าน หัวเจาะกดลง ฯลฯ) ตาม motion ที่แดชบอร์ดส่งมา
//
// ทุกตัวสร้างรับ (R, M, V) = กลุ่มราก, ชุด material, ตัวเลือกย่อย (variant)
// และคืน { tick(t), fx, beacon, label }
//   tick(t)  เรียกทุกเฟรม t = วินาทีสะสมของแอนิเมชัน (หยุดเดินเมื่อ motion = stop)
//   fx       รายการจุดปล่อยอนุภาค [{obj, type:'chips'|'sparks'|'mist'|'dust', color, rate}]
//   beacon   ตำแหน่ง [x, y0, z] ของเสาไฟสถานะ (ไม่ระบุ = มุมเครื่อง)
//
// หน่วยเป็นเมตรโดยประมาณ พื้นอยู่ที่ y = 0 เสมอ
(function () {
  const MODELS = window.M3D_MODELS = {};
  const _geo = {};
  const PI = Math.PI;

  // ---------- ตัวช่วยสร้างรูปทรง ----------
  function gBox(w, h, d) { const k = "b" + w + "," + h + "," + d; return _geo[k] || (_geo[k] = new THREE.BoxGeometry(w, h, d)); }
  function gCyl(rt, rb, h, seg) { const k = "c" + rt + "," + rb + "," + h + "," + seg; return _geo[k] || (_geo[k] = new THREE.CylinderGeometry(rt, rb, h, seg)); }
  function shadow(o) { o.castShadow = true; o.receiveShadow = true; return o; }
  // กล่อง ระบุฐาน (y0 = ด้านล่างของกล่อง)
  function B(p, m, w, h, d, x, y0, z) { const o = new THREE.Mesh(gBox(w, h, d), m); o.position.set(x, y0 + h / 2, z); p.add(shadow(o)); return o; }
  // กล่อง ระบุจุดกึ่งกลาง
  function BC(p, m, w, h, d, x, y, z) { const o = new THREE.Mesh(gBox(w, h, d), m); o.position.set(x, y, z); p.add(shadow(o)); return o; }
  // ทรงกระบอก ระบุจุดกึ่งกลาง แกน "y" (ตั้ง) | "x" | "z"
  function C(p, m, r, h, x, y, z, axis, seg, rb) {
    const o = new THREE.Mesh(gCyl(r, rb == null ? r : rb, h, seg || 28), m);
    if (axis === "x") o.rotation.z = PI / 2; else if (axis === "z") o.rotation.x = PI / 2;
    o.position.set(x, y, z); p.add(shadow(o)); return o;
  }
  // ทรงกระบอกตั้ง ระบุฐาน
  function CB(p, m, r, h, x, y0, z, seg) { return C(p, m, r, h, x, y0 + h / 2, z, "y", seg); }
  // กรวย/ทรงกระบอกปลายต่างขนาด ระบุจุดกึ่งกลาง
  function K(p, m, rt, rb, h, x, y, z, axis) { return C(p, m, rt, h, x, y, z, axis, 32, rb); }
  function S(p, m, r, x, y, z) { const o = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 14), m); o.position.set(x, y, z); p.add(shadow(o)); return o; }
  function T(p, m, R, r, x, y, z, axis) {
    const o = new THREE.Mesh(new THREE.TorusGeometry(R, r, 10, 40), m);
    if (axis === "y") o.rotation.x = PI / 2; else if (axis === "x") o.rotation.y = PI / 2;
    o.position.set(x, y, z); p.add(shadow(o)); return o;
  }
  function G(p, x, y, z) { const g = new THREE.Group(); g.position.set(x || 0, y || 0, z || 0); p.add(g); return g; }
  // ชิ้นที่ต้องหมุนรอบแกนตัวเอง: ห่อด้วย group ที่เอียงไว้ แล้วหมุน mesh ด้านในรอบแกน y ของมัน
  function spinner(p, m, r, h, x, y, z, axis, seg, rb) {
    const g = G(p, x, y, z);
    if (axis === "x") g.rotation.z = PI / 2; else if (axis === "z") g.rotation.x = PI / 2;
    const mesh = C(g, m, r, h, 0, 0, 0, "y", seg, rb);
    return { g, mesh };
  }
  // ใบเลื่อยวงเดือน (จานบาง + ฟันเป็นวงแหวน)
  function sawBlade(p, M, r, x, y, z, axis) {
    const s = spinner(p, M.steel, r, .012, x, y, z, axis, 48);
    const teeth = T(s.g, M.steelDark, r, .012, 0, 0, 0, "y");
    teeth.rotation.x = PI / 2; // วางวงแหวนให้ขนานจาน (ในพิกัดของ group)
    s.mesh.add(teeth); teeth.position.set(0, 0, 0);
    return s;
  }
  // ขา 4 ขา ใต้โต๊ะ
  function legs(p, M, w, d, h, x, z, t) {
    t = t || .06;
    [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(([a, b]) => B(p, M.frame, t, h, t, x + a * (w / 2 - t), 0, z + b * (d / 2 - t)));
  }
  // แผงควบคุมบนเสา (จอ + ปุ่ม 3 ปุ่ม)
  function panelCtl(p, M, x, y0, z, ry, h) {
    const g = G(p, x, y0, z); g.rotation.y = ry || 0; h = h || .95;
    B(g, M.frame, .05, h, .05, 0, 0, 0);
    B(g, M.dark, .36, .28, .07, 0, h - .05, 0);
    B(g, M.screen, .28, .16, .012, 0, h + .04, .04);
    [M.ledG, M.ledR, M.safety].forEach((m, i) => C(g, m, .016, .014, -.09 + i * .09, h - .01, .04, "z", 12));
    return g;
  }
  // มอเตอร์ (ทรงกระบอก + กล่องต่อสาย)
  function motor(p, M, r, len, x, y, z, axis) {
    const g = G(p, x, y, z);
    if (axis === "x") g.rotation.z = PI / 2; else if (axis === "z") g.rotation.x = PI / 2;
    C(g, M.steelDark, r, len, 0, 0, 0, "y", 24);
    C(g, M.dark, r * .55, len * .18, 0, len / 2 + len * .09, 0, "y", 16);
    BC(g, M.dark, r * .9, len * .35, r * .5, 0, 0, r * .95);
    return g;
  }
  // แผ่นไม้/ชิ้นงาน
  function slab(p, M, w, d, x, y0, z, m) { return B(p, m || M.wood, w, .02, d, x, y0, z); }
  // ล้อหมุนบนรางโต๊ะ (ลูกกลิ้ง)
  function rollerRow(p, M, n, len, r, x0, dx, y, z, axis) {
    const out = [];
    for (let i = 0; i < n; i++) out.push(spinner(p, M.steel, r, len, x0 + i * dx, y, z, axis || "z", 16).mesh);
    return out;
  }
  function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
  function tri(p) { return p < .5 ? p * 2 : 2 - p * 2; } // 0→1→0
  function cycle(t, period) { return (t % period) / period; }

  // =====================================================================
  //  งานตัด (CT)
  // =====================================================================
  // เครื่องตัดแผ่นแบบคาน (Beam saw: HOLZMA / SELCO) — แผ่นถูกดันจากโต๊ะหลัง คานกด ใบเลื่อยวิ่งใต้โต๊ะ
  MODELS.beam_saw = function (R, M) {
    const W = 4.6;
    B(R, M.frame, W, .55, .95, 0, 0, 0);
    B(R, M.steel, W + .2, .08, 1.05, 0, .55, 0);
    B(R, M.dark, W - .4, .09, .05, 0, .56, 0);
    [-1, 1].forEach(s => B(R, M.frame, .5, 1.8, 1.05, s * (W / 2 + .25), 0, 0));
    B(R, M.accent2, W + 1.0, .35, 1.05, 0, 1.8, 0);
    const beam = G(R, 0, 1.3, 0);
    BC(beam, M.accent, W, .3, .5, 0, 0, 0);
    BC(beam, M.steelDark, W, .06, .4, 0, -.18, 0);
    [-1.5, 0, 1.5].forEach(x => { B(R, M.steelDark, 1.3, .07, 1.5, x, .56, 1.35); legs(R, M, 1.2, 1.3, .56, x, 1.35, .05); });
    B(R, M.steelDark, W - .3, .07, 2.7, 0, .56, -1.9); legs(R, M, W - .5, 2.5, .56, 0, -1.9, .05);
    [-1, 1].forEach(s => B(R, M.steel, .08, .1, 2.9, s * (W / 2 - .3), .63, -1.95));
    const pusher = G(R, 0, .63, -3.0);
    BC(pusher, M.accent, W - .6, .22, .18, 0, .11, 0);
    for (let i = -3; i <= 3; i++) BC(pusher, M.steelDark, .12, .18, .3, i * .55, .09, .2);
    const stack = G(pusher, 0, 0, 1.0);
    for (let i = 0; i < 3; i++) BC(stack, i % 2 ? M.wood : M.wood2, 2.6, .05, 1.3, 0, .03 + i * .05, 0);
    const saw = G(R, -W / 2 + .6, .1, 0);
    BC(saw, M.accent2, .55, .4, .5, 0, .2, 0);
    const blade = sawBlade(saw, M, .24, 0, .5, 0, "z");
    const score = sawBlade(saw, M, .1, -.28, .42, 0, "z");
    BC(R, M.wood, 1.1, .05, 1.2, -1.5, .66, 1.3); BC(R, M.wood2, .9, .05, .8, 1.5, .66, 1.2);
    panelCtl(R, M, W / 2 + .95, 0, 1.45, -.6);
    const fx = [{ obj: blade.mesh, type: "chips", rate: 1 }];
    return {
      beacon: [W / 2 + .5, 2.15, .35], fx,
      tick(t) {
        const p = cycle(t, 9);
        pusher.position.z = -3.0 + .9 * clamp01(p / .3);
        const press = p < .3 ? 0 : p < .4 ? (p - .3) / .1 : p < .85 ? 1 : 1 - (p - .85) / .15;
        beam.position.y = 1.3 - .24 * press;
        const cut = p < .4 ? 0 : p < .8 ? (p - .4) / .4 : 1 - (p - .8) / .2;
        saw.position.x = -W / 2 + .6 + (W - 1.2) * cut;
        blade.mesh.rotation.y = t * 30; score.mesh.rotation.y = -t * 40;
        fx[0].active = p > .4 && p < .8;
      },
    };
  };

  // เครื่องเลื่อยโต๊ะเลื่อน (Sliding table saw: Altendorf / Casadei)
  MODELS.table_saw = function (R, M) {
    B(R, M.frame, .95, .8, .95, 0, 0, 0);
    B(R, M.steel, 1.25, .06, 1.05, .1, .8, 0);
    B(R, M.dark, .5, .07, .03, .3, .8, 0);
    const blade = sawBlade(R, M, .18, .3, .86, 0, "x");
    B(R, M.steel, .02, .14, .06, .3, .86, .2); // มีดแยกชิ้นงาน
    B(R, M.accent, 1.2, .08, .05, .2, .86, -.42); // รั้ว
    B(R, M.frame, .22, .35, 2.7, -.75, .45, 0);
    const slide = G(R, -.75, .8, 0);
    BC(slide, M.steelDark, .5, .05, 2.5, 0, .025, 0);
    BC(slide, M.accent, 1.5, .08, .06, .4, .09, -.95);
    const work = slab(slide, M, .9, .7, .3, .05, -.55);
    motor(R, M, .1, .3, -.2, .45, .4, "x");
    panelCtl(R, M, .9, 0, .75, -.4, .7);
    B(R, M.safety, .3, .12, .18, .35, 1.0, 0); // ฝาครอบใบเลื่อย
    const fx = [{ obj: blade.mesh, type: "chips", rate: .8 }];
    return {
      beacon: [-1.1, 0, -.9], fx,
      tick(t) {
        const p = cycle(t, 5);
        slide.position.z = -.9 + 1.8 * (p < .55 ? p / .55 : 1 - (p - .55) / .45);
        blade.mesh.rotation.y = t * 32;
        fx[0].active = p < .55;
      },
    };
  };

  // เลื่อยแขน / เลื่อยตัดองศา / เลื่อยตัดเหล็ก (ใบเลื่อยเหนือโต๊ะ เลื่อนตัดเข้าหาชิ้นงาน)
  MODELS.miter_saw = function (R, M, V) {
    const metal = !!V.metal;
    B(R, M.frame, .9, .75, .8, 0, 0, 0); B(R, M.frame, .9, .75, .8, 1.6, 0, 0); B(R, M.frame, .9, .75, .8, -1.6, 0, 0);
    B(R, M.steelDark, 4.2, .07, .8, 0, .75, 0);
    B(R, M.accent, 4.2, .12, .05, 0, .82, -.3); // รั้วหลัง
    C(R, M.steel, .07, 1.5, 0, 1.5, -.55, "y");
    B(R, M.accent2, .18, .14, 1.3, 0, 2.2, -.1); // แขน
    const head = G(R, 0, 2.2, -.3);
    BC(head, M.steelDark, .12, .22, .12, 0, -.11, 0);
    BC(head, M.accent, .26, .34, .3, 0, -.4, 0);
    motor(head, M, .09, .28, .22, -.4, 0, "x");
    const blade = sawBlade(head, M, .2, 0, -.62, 0, "x");
    BC(head, M.safety, .08, .22, .42, 0, -.55, 0);
    const work = metal ? C(R, M.steel, .04, 3.2, -.2, .86, .05, "x", 12) : B(R, M.wood, 3.4, .06, .16, -.2, .82, .05);
    const fx = [{ obj: blade.mesh, type: metal ? "sparks" : "chips", rate: 1 }];
    return {
      beacon: [2.3, 0, .6], fx,
      tick(t) {
        const p = cycle(t, 4);
        head.position.z = -.3 + .55 * (p < .45 ? p / .45 : 1 - (p - .45) / .55);
        blade.mesh.rotation.y = t * 28;
        fx[0].active = p > .15 && p < .45;
      },
    };
  };

  // เลื่อยสายพาน (Band saw)
  MODELS.band_saw = function (R, M) {
    B(R, M.frame, .7, .9, .7, 0, 0, 0);
    B(R, M.steel, .8, .05, .8, 0, .9, .05);
    B(R, M.frame, .22, 2.5, .36, -.1, 0, -.4);
    B(R, M.accent, .5, .6, .32, 0, 1.75, -.25); B(R, M.accent, .5, .55, .32, 0, .32, -.25);
    const up = spinner(R, M.steelDark, .22, .05, 0, 2.0, -.06, "z", 32);
    const lo = spinner(R, M.steelDark, .22, .05, 0, .55, -.06, "z", 32);
    B(R, M.steel, .012, 1.45, .035, .22, .55, -.06); B(R, M.steel, .012, 1.45, .035, -.22, .55, -.06);
    B(R, M.safety, .1, .3, .12, .22, 1.0, -.06); // ตัวนำใบ
    const work = slab(R, M, .6, .35, .05, .95, .3);
    panelCtl(R, M, .55, 0, .55, -.6, .7);
    const fx = [{ obj: work, type: "chips", rate: .4 }];
    return {
      beacon: [-.55, 0, .55], fx,
      tick(t) {
        up.mesh.rotation.y = t * 9; lo.mesh.rotation.y = t * 9;
        const p = cycle(t, 6);
        work.position.z = .3 - .25 * (p < .6 ? p / .6 : 1 - (p - .6) / .4);
        fx[0].active = p < .6;
      },
    };
  };

  // =====================================================================
  //  งานเจาะ / CNC (DL)
  // =====================================================================
  // CNC Router / Point-to-point (Biesse Rover, NANXING nesting) — สะพานวิ่งแกน X หัวสปินเดิลวิ่ง Z กดลง
  MODELS.cnc_router = function (R, M) {
    const L = 4.0, D = 2.0;
    B(R, M.frame, L, .6, D, 0, 0, 0);
    B(R, M.steelDark, L - .2, .08, D - .2, 0, .6, 0);
    for (let i = -2; i <= 2; i++) for (let j = -1; j <= 1; j++) B(R, M.rubber, .32, .07, .32, i * .7, .68, j * .55);
    const work = slab(R, M, 2.4, 1.3, -.3, .75, 0);
    [-1, 1].forEach(s => B(R, M.steel, L + .3, .12, .12, 0, .7, s * (D / 2 + .08)));
    const gantry = G(R, 0, 0, 0);
    [-1, 1].forEach(s => BC(gantry, M.accent, .3, 1.0, .3, 0, 1.25, s * (D / 2 + .08)));
    BC(gantry, M.accent, .36, .36, D + .6, 0, 1.78, 0);
    BC(gantry, M.steel, .1, .1, D + .3, .22, 1.62, 0);
    const head = G(gantry, 0, 1.55, 0);
    BC(head, M.steelDark, .32, .55, .36, .32, 0, 0);
    const spindle = G(head, .32, -.25, 0);
    C(spindle, M.dark, .07, .32, 0, -.1, 0, "y", 20);
    const bit = spinner(spindle, M.steel, .012, .12, 0, -.32, 0, "y", 10);
    BC(R, M.frame, .5, .2, .5, L / 2 + .4, .95, D / 2 + .3);
    panelCtl(R, M, L / 2 + .6, 0, D / 2 + .5, -.7);
    const fx = [{ obj: bit.mesh, type: "chips", rate: .9 }];
    return {
      beacon: [-L / 2 - .3, 0, D / 2 + .3], fx,
      tick(t) {
        gantry.position.x = Math.sin(t * .55) * 1.3;
        head.position.z = Math.sin(t * .9 + 1.3) * .6;
        const plunge = Math.max(0, Math.sin(t * 2.2)) ;
        spindle.position.y = -.25 - .22 * plunge;
        bit.mesh.rotation.y = t * 60;
        fx[0].active = plunge > .6;
      },
    };
  };

  // เครื่องเจาะ CNC แบบป้อนผ่าน (SKIPPER / 6-sided) — แผ่นวิ่งเข้าช่องเครื่อง หัวเจาะบน-ล่างกดเมื่อแผ่นอยู่กลาง
  MODELS.cnc_drill = function (R, M) {
    const L = 2.6;
    B(R, M.frame, L, 1.9, 1.4, 0, 0, 0);
    B(R, M.accent, L + .04, .5, 1.44, 0, 1.25, 0);
    B(R, M.glass, 1.7, .55, .02, 0, 1.0, .72);
    B(R, M.dark, L + .1, .32, .95, 0, .78, 0); // ช่องแผ่นผ่าน
    B(R, M.steelDark, 1.5, .07, .8, -L / 2 - .7, .85, 0); legs(R, M, 1.4, .7, .85, -L / 2 - .7, 0, .05);
    B(R, M.steelDark, 1.5, .07, .8, L / 2 + .7, .85, 0); legs(R, M, 1.4, .7, .85, L / 2 + .7, 0, .05);
    rollerRow(R, M, 4, .7, .03, -L / 2 - 1.2, .3, .9, 0); rollerRow(R, M, 4, .7, .03, L / 2 + .3, .3, .9, 0);
    const work = slab(R, M, 1.0, .6, -2.6, .92, 0);
    const head = G(R, 0, 1.2, 0);
    BC(head, M.steelDark, .5, .3, .5, 0, 0, 0);
    const bits = [];
    for (let i = -1; i <= 1; i++) bits.push(spinner(head, M.steel, .012, .18, i * .12, -.22, 0, "y", 8).mesh);
    const headLo = G(R, 0, .5, 0);
    BC(headLo, M.steelDark, .5, .3, .5, 0, 0, 0);
    panelCtl(R, M, L / 2 + .3, 0, 1.0, -.4);
    const fx = [{ obj: bits[1], type: "chips", rate: .7 }];
    return {
      beacon: [-L / 2 - .2, 1.9, .5], fx,
      tick(t) {
        const p = cycle(t, 7);
        // 0-.35 วิ่งเข้า, .35-.65 เจาะ, .65-1 วิ่งออก
        const x = p < .35 ? -2.6 + 2.6 * (p / .35) : p < .65 ? 0 : 2.6 * ((p - .65) / .35);
        work.position.x = x;
        const d = p < .35 || p > .65 ? 0 : Math.max(0, Math.sin((p - .35) / .3 * PI * 3));
        head.position.y = 1.2 - .2 * d; headLo.position.y = .5 + .2 * d;
        bits.forEach(b => b.rotation.y = t * 50);
        fx[0].active = d > .5;
      },
    };
  };

  // เครื่องเจาะหลายหัว / 3 หัว (GLOBO, Three Ranged, Maggi) — บล็อกหัวเจาะกดลงบนแผ่น
  MODELS.multi_drill = function (R, M) {
    [-1, 1].forEach(s => B(R, M.frame, .3, 1.7, .7, s * 1.05, 0, 0));
    B(R, M.steel, 2.4, .08, .75, 0, .78, 0);
    B(R, M.accent, 2.6, .32, .6, 0, 1.7, 0);
    B(R, M.accent2, .9, .15, .06, 0, .86, -.32); // รั้วหลัง
    const head = G(R, 0, 1.4, 0);
    [-.3, .3].forEach(x => C(head, M.steel, .035, .5, x, .3, 0, "y", 12));
    BC(head, M.steelDark, 1.0, .3, .4, 0, 0, 0);
    const bits = [];
    for (let i = -4; i <= 4; i++) bits.push(spinner(head, M.steel, .01, .14, i * .1, -.22, 0, "y", 8).mesh);
    const work = slab(R, M, 1.2, .5, 0, .86, .05);
    motor(R, M, .09, .3, 0, 2.0, 0, "y");
    panelCtl(R, M, 1.5, 0, .5, -.5, .8);
    const fx = [{ obj: bits[4], type: "chips", rate: .6 }];
    return {
      beacon: [-1.4, 0, .5], fx,
      tick(t) {
        const p = cycle(t, 4);
        const d = p < .5 ? tri(p / .5) : 0;
        head.position.y = 1.4 - .3 * d;
        bits.forEach(b => b.rotation.y = t * 45);
        if (p >= .5) work.position.x = -.4 + .8 * ((p - .5) / .5); else work.position.x = -.4;
        fx[0].active = d > .7;
      },
    };
  };

  // สว่านแท่น / เครื่องเจาะตั้งพื้น (Drill press)
  MODELS.drill_press = function (R, M) {
    B(R, M.frame, .55, .1, .8, 0, 0, -.1);
    C(R, M.steel, .055, 2.0, 0, 1.1, -.3, "y");
    B(R, M.steelDark, .45, .06, .45, 0, .85, 0);
    BC(R, M.steelDark, .12, .14, .28, 0, .84, -.2);
    const head = G(R, 0, 1.75, -.1);
    BC(head, M.accent, .32, .36, .62, 0, 0, .05);
    motor(head, M, .09, .3, 0, .1, -.4, "y");
    const quill = G(head, 0, -.18, .18);
    C(quill, M.steel, .03, .3, 0, -.1, 0, "y", 12);
    C(quill, M.dark, .045, .08, 0, -.29, 0, "y", 16);
    const bit = spinner(quill, M.steel, .01, .14, 0, -.4, 0, "y", 8);
    const wheel = G(head, .22, 0, .18);
    for (let i = 0; i < 3; i++) { const s = C(wheel, M.dark, .012, .2, 0, 0, 0, "y", 8); s.rotation.z = i * 2 * PI / 3; s.rotation.x = PI / 2; }
    BC(R, M.wood2, .2, .06, .2, 0, .91, 0);
    const fx = [{ obj: bit.mesh, type: "chips", rate: .5 }];
    return {
      beacon: [-.5, 0, .3], fx,
      tick(t) {
        const p = cycle(t, 3.5), d = tri(p);
        quill.position.y = -.18 - .25 * d;
        wheel.rotation.x = d * 1.2;
        bit.mesh.rotation.y = t * 40;
        fx[0].active = d > .8;
      },
    };
  };

  // =====================================================================
  //  งานปิดขอบ (EG) และงานผิว
  // =====================================================================
  function edgeBander(R, M, V) {
    const L = V.len || 5.2, post = !!V.postform;
    B(R, M.frame, L, .72, .95, 0, 0, 0);
    B(R, M.steelDark, L, .04, 1.0, 0, .72, 0);
    if (post) {
      B(R, M.accent, L - 1.2, .5, .5, .3, 1.1, -.2);
      [-1, 1].forEach(s => B(R, M.steel, .08, .5, .08, s * (L / 2 - .7), .76, .25));
      B(R, M.heat, L - 1.6, .1, .1, 0, 1.2, .25); // แท่งความร้อน
    } else {
      B(R, M.accent, L - 1.0, .62, .9, .2, .76, -.05);
      B(R, M.glass, L - 1.4, .22, .02, .2, 1.05, .41);
      B(R, M.accent2, L - 1.0, .06, .92, .2, 1.38, -.05);
      for (let i = 0; i < 4; i++) C(R, M.steel, .05, .25, -1.2 + i * .9, 1.55, -.2, "y", 14); // ท่อดูดฝุ่น
    }
    B(R, M.steel, L, .06, .14, 0, .76, .5); // รางกดแผ่น
    // โต๊ะรับแผ่นหัว-ท้าย (ให้แผ่นที่วิ่งเข้า-ออกมีอะไรรองรับ)
    [-1, 1].forEach(s => { B(R, M.steelDark, 2.2, .05, .9, s * (L / 2 + 1.1), .71, .1); legs(R, M, 2.1, .8, .71, s * (L / 2 + 1.1), .1, .05); });
    const feed = G(R, -L / 2 - 1.0, 0, 0);
    const workA = slab(feed, M, 1.2, .62, 0, .76, .15);
    const workB = slab(feed, M, 1.0, .5, -1.9, .76, .15, M.wood2);
    const strip = B(feed, M.edge, 1.2, .024, .01, 0, .758, .465); // ขอบที่ติดแล้ว
    const roll = spinner(R, M.white, .32, .04, -L / 2 + .55, 1.28 + (post ? 0 : .1), -.25, "y", 40);
    C(R, M.steelDark, .03, .25, -L / 2 + .55, 1.2, -.25, "y", 10);
    panelCtl(R, M, L / 2 + .3, 0, .6, -.5);
    return {
      beacon: [L / 2 + .2, 1.4 + (post ? -.2 : 0), -.4],
      tick(t) {
        const p = cycle(t, 8);
        feed.position.x = -L / 2 - 1.0 + (L + 2.6) * p;
        roll.mesh.rotation.y = -t * 1.4;
        strip.visible = feed.position.x > 0.2;
      },
    };
  }
  MODELS.edge_bander = (R, M, V) => edgeBander(R, M, V);
  MODELS.postformer = (R, M, V) => edgeBander(R, M, Object.assign({ postform: true, len: 4.2 }, V));

  // เครื่องปิดขอบโค้ง (WAP / Orbiter / manual) — แผ่นโค้งหมุนรอบหัวทากาว
  MODELS.edge_curve = function (R, M) {
    B(R, M.frame, .7, .85, .7, 0, 0, 0);
    B(R, M.steel, 1.4, .05, 1.2, 0, .85, 0);
    C(R, M.accent, .09, .32, 0, 1.06, 0, "y");
    C(R, M.steelDark, .05, .1, 0, 1.25, 0, "y");
    const roll = spinner(R, M.white, .18, .035, -.45, 1.0, -.4, "y", 36);
    C(R, M.steelDark, .025, .2, -.45, 1.0, -.4, "y", 10);
    const orbit = G(R, 0, .9, 0);
    const work = G(orbit, .3, 0, 0);
    BC(work, M.wood, .5, .02, .34, 0, .01, 0);
    C(work, M.wood, .17, .02, .25, .01, 0, "y", 24); C(work, M.wood, .17, .02, -.25, .01, 0, "y", 24);
    panelCtl(R, M, .9, 0, .5, -.5, .75);
    return {
      beacon: [-.85, 0, .5],
      tick(t) { orbit.rotation.y = t * .6; roll.mesh.rotation.y = -t * 1.5; },
    };
  };

  // เครื่องทากาว (ลูกกลิ้ง 2 ตัว)
  MODELS.glue_spreader = function (R, M) {
    B(R, M.frame, 1.6, .8, .9, 0, 0, 0);
    [-1, 1].forEach(s => B(R, M.accent, .18, .55, .9, s * .75, .8, 0));
    const r1 = spinner(R, M.rubber, .12, 1.3, 0, 1.0, .0, "x", 24);
    const r2 = spinner(R, M.steel, .1, 1.3, 0, 1.24, .0, "x", 24);
    B(R, M.steelDark, 1.2, .05, .6, 0, .85, .75); B(R, M.steelDark, 1.2, .05, .6, 0, .85, -.75);
    const work = slab(R, M, 1.0, .6, 0, .9, 1.0);
    B(R, M.glue, 1.3, .06, .2, 0, 1.3, .14); // รางกาว
    panelCtl(R, M, 1.05, 0, .55, -.4, .7);
    return {
      beacon: [-1.05, 0, .55],
      tick(t) {
        const p = cycle(t, 6);
        work.position.z = 1.0 - 2.0 * p;
        r1.mesh.rotation.y = t * 2; r2.mesh.rotation.y = -t * 2;
      },
    };
  };

  // เครื่องอัด/เพรส แผ่น (Hot press, Cold press, Membrane) — แท่นบนกดลง
  MODELS.panel_press = function (R, M, V) {
    const hot = !!V.hot;
    B(R, M.frame, 2.9, .45, 1.7, 0, 0, 0);
    B(R, hot ? M.heat : M.steelDark, 2.6, .22, 1.5, 0, .45, 0);
    [-1, 1].forEach(a => [-1, 1].forEach(b => C(R, M.steel, .07, 1.9, a * 1.25, 1.4, b * .72, "y", 16)));
    B(R, M.accent, 2.95, .36, 1.75, 0, 2.3, 0);
    [-1, 1].forEach(a => C(R, M.steelDark, .13, .3, a * .6, 2.15, 0, "y", 20));
    const platen = G(R, 0, 1.85, 0);
    BC(platen, hot ? M.heat : M.steelDark, 2.6, .22, 1.5, 0, 0, 0);
    [-1, 1].forEach(a => C(platen, M.steel, .07, .5, a * .6, .3, 0, "y", 12));
    const stack = G(R, 0, .56, 0);
    for (let i = 0; i < 3; i++) BC(stack, i % 2 ? M.wood2 : M.wood, 2.2, .04, 1.2, 0, .02 + i * .04, 0);
    B(R, M.steelDark, 1.4, .06, 1.2, -2.3, .5, 0); legs(R, M, 1.3, 1.1, .5, -2.3, 0, .05);
    panelCtl(R, M, 1.9, 0, 1.2, -.5);
    const fx = hot ? [{ obj: stack, type: "mist", rate: .5, color: 0xffffff }] : [];
    return {
      beacon: [-1.9, 0, 1.2], fx,
      tick(t) {
        const p = cycle(t, 8);
        const d = p < .25 ? p / .25 : p < .7 ? 1 : 1 - (p - .7) / .3;
        platen.position.y = 1.85 - 1.05 * d;
        if (fx[0]) fx[0].active = d > .95;
      },
    };
  };

  // เครื่องปั๊ม / เพรสโลหะ (แท่นแบบ C-frame) — แรมกระแทกลง ล้อตุนกำลังหมุน
  MODELS.metal_press = function (R, M) {
    B(R, M.frame, 1.3, .55, 1.0, 0, 0, 0);
    B(R, M.frame, .7, 2.0, .8, 0, .55, -.2);
    B(R, M.accent, 1.1, .7, .95, 0, 2.2, .05);
    B(R, M.steel, .9, .18, .6, 0, .55, .25);
    B(R, M.steelDark, .5, .1, .4, 0, .73, .25);
    const ram = G(R, 0, 1.55, .25);
    BC(ram, M.steelDark, .35, .5, .35, 0, 0, 0);
    BC(ram, M.steel, .5, .1, .4, 0, -.3, 0);
    const fly = spinner(R, M.steelDark, .4, .09, .72, 2.35, -.15, "x", 36);
    T(R, M.steel, .4, .04, .78, 2.35, -.15, "x");
    motor(R, M, .1, .3, -.6, 2.35, -.15, "x");
    B(R, M.safety, 1.0, .05, .05, 0, 1.15, .6);
    panelCtl(R, M, 1.0, 0, .7, -.5);
    return {
      beacon: [-.95, 0, .7],
      tick(t) {
        const p = cycle(t, 2.2);
        const d = p < .4 ? Math.pow(p / .4, 2) : 1 - (p - .4) / .6;
        ram.position.y = 1.55 - .55 * d;
        fly.mesh.rotation.y = t * 2.9;
      },
    };
  };

  // เครื่องพับเหล็ก (Press brake) — คานกดยาวลงบนแม่พิมพ์ตัว V
  MODELS.press_brake = function (R, M) {
    B(R, M.frame, 2.8, .5, 1.0, 0, 0, 0);
    [-1, 1].forEach(s => B(R, M.frame, .4, 2.2, .9, s * 1.3, .5, -.1));
    B(R, M.accent, 3.0, .45, .9, 0, 2.5, -.1);
    B(R, M.steel, 2.4, .25, .2, 0, .5, .2);
    B(R, M.dark, 2.4, .08, .08, 0, .75, .2);
    const ram = G(R, 0, 1.75, .2);
    BC(ram, M.steelDark, 2.4, .5, .12, 0, 0, 0);
    BC(ram, M.steel, 2.4, .12, .06, 0, -.31, 0);
    [-1, 1].forEach(s => C(ram, M.steel, .09, .5, s * 1.0, .45, 0, "y", 14));
    const sheet = B(R, M.steel, 2.0, .012, .7, 0, .83, .4);
    panelCtl(R, M, 1.9, 0, .8, -.5);
    return {
      beacon: [-1.9, 0, .7],
      tick(t) {
        const p = cycle(t, 4);
        const d = p < .35 ? p / .35 : p < .55 ? 1 : 1 - (p - .55) / .45;
        ram.position.y = 1.75 - .85 * d;
        sheet.rotation.x = -.5 * clamp01((d - .8) / .2);
      },
    };
  };

  // เครื่องดัดท่อ (Tube bender) — แขนหมุนพาท่อโค้งรอบแม่พิมพ์
  MODELS.tube_bender = function (R, M) {
    B(R, M.frame, 1.6, .8, .9, 0, 0, 0);
    B(R, M.accent, 1.2, .25, .8, -.2, .8, 0);
    const die = C(R, M.steelDark, .28, .2, .4, 1.15, 0, "y", 32);
    C(R, M.steel, .05, .5, .4, 1.3, 0, "y", 12);
    BC(R, M.steelDark, .3, .2, .25, .05, 1.15, .32); // ตัวหนีบ
    C(R, M.steel, .035, 2.4, -.9, 1.15, .3, "x", 14); // ท่อตรง
    const arm = G(R, .4, 1.15, 0);
    BC(arm, M.steelDark, .9, .1, .12, .35, .12, .3);
    const seg = C(arm, M.steel, .035, .9, .45, .0, .3, "x", 14); // ท่อช่วงที่ถูกดัด
    panelCtl(R, M, 1.1, 0, .6, -.5, .75);
    return {
      beacon: [-1.0, 0, .6],
      tick(t) { const p = cycle(t, 5); arm.rotation.y = -PI / 2 * (p < .5 ? p / .5 : 1 - (p - .5) / .5); },
    };
  };

  // =====================================================================
  //  เครื่องป้อนผ่าน: ไสไม้ / ใส 4 หน้า / ขัดสายพาน
  // =====================================================================
  function throughFeed(R, M, V) {
    const sander = V.mode === "sander", L = sander ? 2.4 : 2.8;
    B(R, M.frame, L, .8, 1.3, 0, 0, 0);
    B(R, M.accent, L - .1, .9, 1.25, 0, .8, 0);
    B(R, M.accent2, L - .3, .1, 1.1, 0, 1.7, 0);
    if (sander) { B(R, M.glass, L - .6, .3, .02, 0, 1.1, .64); }
    for (let i = 0; i < 3; i++) C(R, M.steel, .07, .35, -.7 + i * .7, 1.95, -.2, "y", 14);
    B(R, M.steelDark, 1.3, .07, .8, -L / 2 - .6, .85, 0); legs(R, M, 1.2, .7, .85, -L / 2 - .6, 0, .05);
    B(R, M.steelDark, 1.3, .07, .8, L / 2 + .6, .85, 0); legs(R, M, 1.2, .7, .85, L / 2 + .6, 0, .05);
    const rolls = [].concat(rollerRow(R, M, 3, sander ? .9 : .5, .05, -L / 2 - 1.0, .35, .93, 0),
                             rollerRow(R, M, 3, sander ? .9 : .5, .05, L / 2 + .3, .35, .93, 0));
    const work = sander ? slab(R, M, 1.0, .7, -2.0, .97, 0) : B(R, M.wood, 1.4, .09, .14, -2.0, .93, 0);
    panelCtl(R, M, L / 2 + .3, 0, .95, -.5);
    const fx = [{ obj: work, type: "dust", rate: .6, color: 0xd9c08a }];
    const span = L / 2 + .7;
    return {
      beacon: [-L / 2 - .2, 1.75, .5], fx,
      tick(t) {
        const p = cycle(t, 6);
        const x = -span + 2 * span * p;
        work.position.x = x;
        rolls.forEach(r => r.rotation.y = t * 3);
        fx[0].active = Math.abs(x) < L / 2;
      },
    };
  }
  MODELS.moulder = (R, M, V) => throughFeed(R, M, V);
  MODELS.sander = (R, M, V) => throughFeed(R, M, Object.assign({ mode: "sander" }, V));

  // เครื่องเพลาตั้ง / เร้าเตอร์โต๊ะ (Spindle moulder) + ชุดป้อนอัตโนมัติ
  MODELS.spindle_moulder = function (R, M, V) {
    B(R, M.frame, .95, .85, .85, 0, 0, 0);
    B(R, M.steel, 1.2, .06, 1.0, 0, .85, 0);
    const cutter = spinner(R, M.steelDark, .07, .14, 0, 1.03, 0, "y", 16);
    C(R, M.steel, .025, .25, 0, 1.1, 0, "y", 10);
    [-1, 1].forEach(s => B(R, M.accent, .45, .16, .05, s * .32, .91, -.14));
    const work = B(R, M.wood, 1.1, .08, .1, -.7, .91, -.07);
    let feed = null;
    if (V.feeder !== false) {
      C(R, M.steelDark, .04, .7, .45, 1.2, .35, "y", 12);
      feed = G(R, .1, 1.3, .12); BC(feed, M.safety, .5, .16, .22, 0, 0, 0);
      feed.rotation.y = 0;
      var fw = [-.17, 0, .17].map(x => spinner(feed, M.rubber, .07, .05, x, -.12, 0, "y", 16).mesh);
    }
    panelCtl(R, M, .9, 0, .6, -.5, .7);
    const fx = [{ obj: cutter.mesh, type: "chips", rate: .7 }];
    return {
      beacon: [-.85, 0, .6], fx,
      tick(t) {
        const p = cycle(t, 5);
        work.position.x = -.7 + 1.4 * p;
        cutter.mesh.rotation.y = t * 60;
        if (fw) fw.forEach(w => w.rotation.y = -t * 4);
        fx[0].active = Math.abs(work.position.x) < .6;
      },
    };
  };

  // เครื่องขัดเงา (ล้อผ้าหมุน)
  MODELS.polisher = function (R, M, V) {
    const n = V.wheels || 2, L = n > 2 ? 2.2 : 1.2;
    B(R, M.frame, .5, .1, .5, 0, 0, 0);
    C(R, M.frame, .09, .85, 0, .5, 0, "y", 16);
    B(R, M.accent, L * .5, .35, .35, 0, .92, 0);
    const shaft = spinner(R, M.steel, .022, L, 0, 1.1, 0, "x", 10);
    const wheels = [];
    for (let i = 0; i < n; i++) { const x = (i - (n - 1) / 2) * (L / n); wheels.push(spinner(R, M.cloth, .2, .09, x, 1.1, 0, "x", 32).mesh); }
    B(R, M.safety, L, .04, .3, 0, 1.3, -.1); // ฝาครอบบน
    const fx = [{ obj: wheels[0], type: "dust", rate: .5, color: 0xffffff }];
    return {
      beacon: [-L / 2 - .3, 0, .4], fx,
      tick(t) { wheels.forEach(w => w.rotation.y = t * 14); shaft.mesh.rotation.y = t * 14; fx[0].active = true; },
    };
  };

  // =====================================================================
  //  งานกลึง / มิลลิ่ง / ลับคม (GD)
  // =====================================================================
  MODELS.lathe = function (R, M, V) {
    const wood = !!V.wood;
    [-1, 1].forEach(s => B(R, M.frame, .55, .78, .55, s * .95, 0, 0));
    B(R, M.frame, 2.6, .3, .55, 0, .78, 0);
    B(R, M.steel, 2.6, .05, .12, 0, 1.08, .15); B(R, M.steel, 2.6, .05, .12, 0, 1.08, -.15);
    B(R, M.accent, .65, .55, .6, -1.0, 1.08, 0);
    const chuck = spinner(R, M.steelDark, .15, .14, -.6, 1.38, 0, "x", 24);
    for (let i = 0; i < 3; i++) { const j = BC(chuck.mesh, M.steel, .04, .05, .09, 0, .02, 0); j.position.set(Math.cos(i * 2.094) * .1, .0, Math.sin(i * 2.094) * .1); j.rotation.y = -i * 2.094; }
    const work = spinner(R, wood ? M.wood2 : M.steel, .05, 1.3, .12, 1.38, 0, "x", 20);
    B(R, M.steelDark, .32, .3, .3, 1.0, 1.08, 0); C(R, M.steel, .03, .35, .78, 1.38, 0, "x", 10);
    const carriage = G(R, -.2, 1.1, 0);
    BC(carriage, M.steelDark, .4, .14, .62, 0, .07, 0);
    BC(carriage, M.steel, .25, .12, .3, 0, .2, .12);
    BC(carriage, M.dark, .12, .16, .12, 0, .32, .1);
    const hw = spinner(carriage, M.dark, .09, .02, 0, .1, .4, "z", 20);
    motor(R, M, .11, .35, -1.0, .45, .4, "z");
    panelCtl(R, M, -1.55, 0, .55, .6, .8);
    const fx = [{ obj: carriage, type: wood ? "chips" : "sparks", rate: .6 }];
    return {
      beacon: [1.6, 0, .5], fx,
      tick(t) {
        chuck.mesh.rotation.y = t * 12; work.mesh.rotation.y = t * 12;
        const p = cycle(t, 7);
        carriage.position.x = -.3 + 1.0 * (p < .7 ? p / .7 : 1 - (p - .7) / .3);
        hw.mesh.rotation.y = t * 3;
        fx[0].active = p < .7;
      },
    };
  };

  MODELS.milling = function (R, M) {
    B(R, M.frame, .7, .35, .8, 0, 0, -.1);
    B(R, M.frame, .55, 1.9, .6, 0, .35, -.35);
    B(R, M.steelDark, .65, .4, .55, 0, .55, .1);
    const table = G(R, 0, 1.0, .28);
    BC(table, M.steel, 1.5, .1, .35, 0, .05, 0);
    BC(table, M.steelDark, .25, .15, .25, 0, .17, 0); BC(table, M.wood2, .16, .08, .14, 0, .28, 0);
    const hwL = spinner(table, M.dark, .08, .02, -.8, .05, 0, "x", 20), hwR = spinner(table, M.dark, .08, .02, .8, .05, 0, "x", 20);
    B(R, M.accent, .45, .55, .55, 0, 1.95, .05);
    motor(R, M, .11, .35, 0, 2.7, -.05, "y");
    const quill = G(R, 0, 1.9, .18);
    C(quill, M.steel, .04, .3, 0, -.1, 0, "y", 14);
    const bit = spinner(quill, M.steel, .015, .14, 0, -.32, 0, "y", 8);
    B(R, M.steelDark, .8, .08, .08, 0, 1.6, .5); // แขนคันโยก
    panelCtl(R, M, .7, 0, .5, -.5, .7);
    const fx = [{ obj: bit.mesh, type: "sparks", rate: .5 }];
    return {
      beacon: [-.65, 0, .5], fx,
      tick(t) {
        const p = cycle(t, 6);
        table.position.x = -.3 + .6 * tri(p);
        hwL.mesh.rotation.y = t * 4; hwR.mesh.rotation.y = t * 4;
        bit.mesh.rotation.y = t * 50;
        quill.position.y = 1.9 - .08 * Math.max(0, Math.sin(t * 1.5));
        fx[0].active = true;
      },
    };
  };

  // เครื่องลับคมใบเลื่อย (จานใบเลื่อยวางราบ หินเจียรหมุน)
  MODELS.grinder = function (R, M) {
    B(R, M.frame, .95, .8, .75, 0, 0, 0);
    B(R, M.steel, 1.1, .05, .85, 0, .8, 0);
    const blade = sawBlade(R, M, .3, -.1, .88, .05, "y");
    C(R, M.dark, .04, .1, -.1, .9, .05, "y", 12);
    const arm = G(R, .35, 1.0, -.1);
    BC(arm, M.accent, .3, .3, .25, 0, .2, 0);
    motor(arm, M, .07, .25, 0, .45, 0, "y");
    const wheel = spinner(arm, M.white, .07, .035, -.14, .04, .12, "z", 24);
    panelCtl(R, M, .8, 0, .6, -.5, .7);
    const fx = [{ obj: wheel.mesh, type: "sparks", rate: .7 }];
    return {
      beacon: [-.8, 0, .55], fx,
      tick(t) {
        const p = cycle(t, 1.6);
        blade.mesh.rotation.y = Math.floor(t / 1.6) * (2 * PI / 24) + (p < .25 ? 0 : 0);
        arm.position.x = .35 + .06 * tri(cycle(t, 1.6));
        wheel.mesh.rotation.y = t * 50;
        fx[0].active = tri(p) > .5;
      },
    };
  };

  // =====================================================================
  //  ระบบลม / ฝุ่น / ความเย็น (AC, BL, LA-chiller)
  // =====================================================================
  MODELS.compressor = function (R, M) {
    B(R, M.accent, 1.5, 1.35, .95, -.3, 0, -.3);
    B(R, M.accent2, 1.5, .08, .95, -.3, 1.35, -.3);
    for (let i = 0; i < 7; i++) B(R, M.dark, .55, .025, .02, -.65, .3 + i * .1, .18);
    B(R, M.dark, .32, .22, .02, .1, .95, .18); B(R, M.screen, .24, .1, .01, .1, 1.0, .19);
    const fanHole = C(R, M.dark, .3, .02, .46, .7, -.3, "x", 32);
    const fan = G(R, .47, .7, -.3);
    for (let i = 0; i < 6; i++) { const b = BC(fan, M.steel, .02, .22, .07, 0, 0, 0); b.position.set(0, Math.cos(i * PI / 3) * .12, Math.sin(i * PI / 3) * .12); b.rotation.x = i * PI / 3; }
    const tank = C(R, M.steel, .33, 1.7, .4, .45, .55, "x", 32);
    S(R, M.steel, .33, -.45, .45, .55); S(R, M.steel, .33, 1.25, .45, .55);
    [-.5, .5].forEach(x => B(R, M.frame, .12, .25, .5, .4 + x, 0, .55));
    C(R, M.steel, .035, .5, -.1, 1.05, .2, "z", 10); C(R, M.steel, .035, .4, -.1, 1.25, 0, "y", 10);
    C(R, M.white, .06, .03, .9, .85, .55, "y", 20); // เกจ
    return {
      beacon: [1.3, 0, -.2],
      tick(t) { fan.rotation.x = t * 10; },
    };
  };

  // ตู้ + พัดลมระบายความร้อน (Air dryer / Chiller)
  function cabinetFan(R, M, V) {
    B(R, M.accent, .9, 1.25, .7, 0, 0, 0);
    B(R, M.accent2, .95, .06, .75, 0, 1.25, 0);
    for (let i = 0; i < 8; i++) B(R, M.dark, .6, .025, .02, 0, .2 + i * .08, .36);
    B(R, M.dark, .28, .18, .02, 0, 1.0, .36); B(R, M.screen, .2, .08, .01, 0, 1.04, .37);
    const fan = G(R, 0, 1.31, 0);
    C(R, M.dark, .28, .02, 0, 1.3, 0, "y", 32);
    for (let i = 0; i < 5; i++) { const b = BC(fan, M.steel, .2, .02, .06, 0, 0, 0); b.position.set(Math.cos(i * 2 * PI / 5) * .11, 0, Math.sin(i * 2 * PI / 5) * .11); b.rotation.y = -i * 2 * PI / 5; }
    C(R, M.steel, .035, .5, -.6, .4, 0, "x", 10); C(R, M.steel, .035, .5, .6, .4, 0, "x", 10);
    if (V.cold) { C(R, M.blue, .035, .5, .6, .7, 0, "x", 10); }
    return { beacon: [.7, 0, .5], tick(t) { fan.rotation.y = t * 9; } };
  }
  MODELS.air_dryer = (R, M, V) => cabinetFan(R, M, V);
  MODELS.chiller = (R, M, V) => cabinetFan(R, M, Object.assign({ cold: true }, V));

  // เครื่องดูดฝุ่น / ไซโล (ไซโคลน + ท่อดูด + พัดลม)
  MODELS.dust_collector = function (R, M, V) {
    const silo = !!V.silo;
    const H = silo ? 3.4 : 2.6;
    [-1, 1].forEach(a => [-1, 1].forEach(b => C(R, M.frame, .04, 1.6, a * .5, .8, b * .5, "y", 10)));
    K(R, M.steel, .62, .18, 1.1, 0, 1.75, 0, "y");
    C(R, M.steel, .62, silo ? 1.6 : .9, 0, 2.3 + (silo ? .35 : 0), 0, "y", 36);
    C(R, M.accent, .64, .08, 0, 2.3 + (silo ? 1.15 : .45), 0, "y", 36);
    B(R, M.frame, .55, .5, .55, 0, 0, 0); B(R, M.dark, .4, .4, .4, 0, .5, 0);
    const duct = C(R, M.steel, .14, 2.2, 1.6, 2.5 + (silo ? .6 : 0), 0, "x", 20);
    C(R, M.steel, .14, .8, 2.7, 2.1 + (silo ? .6 : 0), 0, "y", 20);
    B(R, M.accent, .9, .6, .6, 1.4, 0, -.9);
    const fan = spinner(R, M.steelDark, .22, .06, 1.4, .3, -.6, "z", 24);
    motor(R, M, .09, .3, 1.0, .3, -.9, "x");
    C(R, M.steel, .12, 1.4, 1.1, 1.5, -.9, "y", 16);
    if (!silo) for (let i = 0; i < 3; i++) C(R, M.white, .11, .9, (i - 1) * .32, 3.2, 0, "y", 16); // ถุงผ้า
    const inlet = G(R, 2.7, 1.72 + (silo ? .6 : 0), 0);
    const fx = [{ obj: inlet, type: "dust", rate: 1, color: 0xc9b58a, dir: [0, 1, 0] }];
    return {
      beacon: [-.9, 0, .9], fx,
      tick(t) { fan.mesh.rotation.y = t * 12; fx[0].active = true; },
    };
  };

  // =====================================================================
  //  งานสี / อบ / ลำเลียง (CO)
  // =====================================================================
  MODELS.spray_booth = function (R, M) {
    const W = 3.0, H = 2.3, D = 1.6;
    B(R, M.frame, W, .06, D, 0, 0, 0);
    B(R, M.frame, W, H, .1, 0, 0, -D / 2);
    [-1, 1].forEach(s => B(R, M.frame, .1, H, D, s * (W / 2 - .05), 0, 0));
    B(R, M.frame, W, .1, D, 0, H, 0);
    B(R, M.water, W - .4, H - .6, .03, 0, .3, -D / 2 + .08);
    const flow = [];
    for (let i = 0; i < 6; i++) flow.push(B(R, M.waterLine, W - .6, .03, .01, 0, .4 + i * .3, -D / 2 + .11));
    [-1, 1].forEach(s => B(R, M.lamp, 1.0, .03, .12, s * .8, H - .04, .2));
    B(R, M.dark, W - .4, .05, .7, 0, .06, .1); // ตะแกรงพื้น
    const trolley = G(R, .3, 0, .4);
    BC(trolley, M.steelDark, .7, .04, .5, 0, .5, 0); [[-.3, -.2], [.3, -.2], [-.3, .2], [.3, .2]].forEach(([x, z]) => C(trolley, M.dark, .05, .04, x, .05, z, "x", 10));
    B(trolley, M.wood, .9, .7, .03, 0, .55, 0);
    const gun = G(R, -.6, 1.4, .9);
    BC(gun, M.dark, .05, .12, .12, 0, 0, 0); C(gun, M.steel, .015, .1, 0, .02, -.1, "z", 8);
    const fx = [{ obj: gun, type: "mist", rate: 1.2, color: 0x9fd0ff, dir: [0, 0, -1] }];
    return {
      beacon: [W / 2 + .3, 0, .5], fx,
      tick(t) {
        flow.forEach((f, i) => f.position.y = .4 + (((i * .3) + (-t * .5) % 1.8 + 1.8) % 1.8));
        gun.position.x = -.6 + 1.2 * tri(cycle(t, 3)); gun.position.y = 1.0 + .5 * tri(cycle(t, 1.3));
        fx[0].active = true;
      },
    };
  };

  // อุโมงค์ (เตาอบสี / อบฟิล์มหด) มีลำเลียงผ่าน
  function tunnel(R, M, V) {
    const L = V.len || 2.4;
    B(R, M.frame, L, .6, .9, 0, 0, 0);
    B(R, M.accent, L, 1.0, 1.1, 0, .6, 0);
    B(R, M.heat, L + .02, .55, .7, 0, .72, 0);
    [-1, 1].forEach(s => { B(R, M.steelDark, 1.4, .06, .8, s * (L / 2 + .7), .62, 0); legs(R, M, 1.3, .7, .62, s * (L / 2 + .7), 0, .05); });
    const rolls = [].concat(rollerRow(R, M, 5, .7, .035, -L / 2 - 1.3, .3, .72, 0), rollerRow(R, M, 5, .7, .035, L / 2 + .1, .3, .72, 0));
    const span = L / 2 + 1.2, step = span * 2 / 3;
    const items = [0, 1, 2].map(i => V.film ? B(R, M.carton, .5, .4, .45, -span + i * step, .76, 0) : slab(R, M, .8, .55, -span + i * step, .76, 0));
    for (let i = 0; i < 2; i++) C(R, M.steel, .07, .35, -.5 + i * 1.0, 1.75, 0, "y", 14);
    panelCtl(R, M, L / 2 + .3, 0, .75, -.5, .85);
    return {
      beacon: [-L / 2 - .3, 1.6, .6],
      tick(t) {
        const p = cycle(t, 8);
        items.forEach((it, i) => it.position.x = -span + ((p * span * 2 + i * step) % (span * 2)));
        rolls.forEach(r => r.rotation.y = t * 3);
      },
    };
  }
  MODELS.oven = (R, M, V) => tunnel(R, M, V);
  MODELS.shrink_tunnel = (R, M, V) => tunnel(R, M, Object.assign({ film: true, len: 1.8 }, V));

  // ไลน์พ่นสีอัตโนมัติ (สะพานพ่นวิ่งข้ามสายพาน)
  MODELS.spray_line = function (R, M) {
    const L = 4.2;
    B(R, M.frame, L, .6, 1.5, 0, 0, 0);
    B(R, M.dark, L - .1, .04, 1.3, 0, .6, 0);
    [-1, 1].forEach(s => B(R, M.accent, .35, 1.6, .35, 0, .6, s * .95));
    B(R, M.accent, .4, .3, 2.3, 0, 2.2, 0);
    const car = G(R, 0, 1.9, 0);
    BC(car, M.steelDark, .3, .3, .3, 0, 0, 0);
    [-.1, .1].forEach(x => C(car, M.dark, .02, .25, x, -.25, 0, "y", 8));
    const span = L / 2 - .5, step = span * 2 / 3;
    const items = [0, 1, 2].map(i => slab(R, M, 1.0, .9, -span + i * step, .64, 0));
    B(R, M.glass, L - .9, .9, .02, 0, 1.0, .76);
    panelCtl(R, M, L / 2 + .3, 0, .9, -.5);
    const fx = [{ obj: car, type: "mist", rate: 1.2, color: 0x9fd0ff, dir: [0, -1, 0] }];
    return {
      beacon: [-L / 2 - .3, 0, .9], fx,
      tick(t) {
        const p = cycle(t, 7);
        items.forEach((it, i) => it.position.x = -span + ((p * span * 2 + i * step) % (span * 2)));
        car.position.z = -.75 + 1.5 * tri(cycle(t, 1.6));
        fx[0].active = true;
      },
    };
  };

  MODELS.conveyor = function (R, M) {
    const L = 3.2;
    B(R, M.frame, L, .08, .85, 0, .62, 0); [-1, 1].forEach(s => B(R, M.accent, L, .12, .05, 0, .7, s * .42));
    legs(R, M, L - .3, .8, .62, 0, 0, .05);
    const rolls = rollerRow(R, M, 12, .78, .045, -L / 2 + .2, .25, .72, 0);
    const items = [B(R, M.carton, .6, .45, .5, -1.5, .77, 0), slab(R, M, .9, .6, 0, .77, 0), B(R, M.carton, .45, .35, .4, 1.4, .77, 0)];
    return {
      beacon: [L / 2 + .2, 0, .5],
      tick(t) { const p = cycle(t, 6); items.forEach((it, i) => it.position.x = -1.9 + ((p * 3.8 + i * 1.3) % 3.8)); rolls.forEach(r => r.rotation.y = t * 3); },
    };
  };

  // =====================================================================
  //  จักรเย็บ (SM)
  // =====================================================================
  MODELS.sewing = function (R, M) {
    B(R, M.laminate, 1.2, .04, .6, 0, .76, 0);
    legs(R, M, 1.1, .5, .76, 0, 0, .035);
    B(R, M.dark, .28, .22, .22, .2, .3, 0); // มอเตอร์ใต้โต๊ะ
    B(R, M.white, .5, .07, .22, 0, .8, 0);
    B(R, M.white, .13, .3, .15, .18, .87, 0);
    B(R, M.white, .5, .13, .15, -.0, 1.12, 0);
    const wheel = spinner(R, M.dark, .07, .035, .28, 1.18, 0, "x", 24);
    C(R, M.steel, .012, .12, -.2, 1.0, 0, "y", 8);
    const needle = G(R, -.2, 1.04, 0); C(needle, M.steel, .005, .12, 0, 0, 0, "y", 6);
    BC(R, M.steel, .035, .01, .06, -.2, .845, 0);
    C(R, M.accent, .02, .07, .15, 1.22, -.03, "y", 12); C(R, M.white, .035, .005, .15, 1.19, -.03, "y", 12);
    const cloth = B(R, M.cloth, .45, .006, .35, -.3, .84, .05);
    B(R, M.dark, .35, .03, .22, -.2, .6, .15); // แป้นเหยียบ
    panelCtl(R, M, .72, 0, .25, -.5, .55);
    return {
      beacon: [-.75, 0, .35],
      tick(t) {
        needle.position.y = 1.04 - .05 * (Math.sin(t * 18) * .5 + .5);
        wheel.mesh.rotation.y = t * 18;
        cloth.position.z = .05 + .12 * tri(cycle(t, 6));
      },
    };
  };

  // =====================================================================
  //  แพ็กกิ้ง (PG)
  // =====================================================================
  MODELS.pallet_wrapper = function (R, M) {
    B(R, M.frame, 1.9, .1, 1.9, 0, 0, 0);
    const table = G(R, 0, .1, 0);
    C(table, M.steelDark, .85, .08, 0, .04, 0, "y", 48);
    BC(table, M.wood2, 1.0, .1, .8, 0, .13, 0);
    [[-.25, -.2], [.25, -.2], [-.25, .2], [.25, .2]].forEach(([x, z]) => BC(table, M.carton, .48, .5, .38, x, .43, z));
    [[-.25, -.2], [.25, -.2], [-.25, .2], [.25, .2]].forEach(([x, z]) => BC(table, M.carton2, .48, .5, .38, x, .93, z));
    const film = new THREE.Mesh(gCyl(.72, .72, 1, 40), M.film); film.position.set(0, .18, 0); film.scale.y = 0.001; table.add(film);
    B(R, M.accent, .32, 2.5, .32, -1.25, 0, -.5);
    const car = G(R, -1.0, .4, -.5);
    BC(car, M.steelDark, .25, .5, .3, 0, 0, 0);
    const roll = spinner(car, M.white, .07, .45, .2, 0, 0, "y", 20).mesh;
    panelCtl(R, M, -1.25, 0, .2, .4, .85);
    B(R, M.dark, .2, .3, .32, -1.25, 2.5, -.5);
    return {
      beacon: [1.0, 0, .9],
      tick(t) {
        const p = cycle(t, 9);
        table.rotation.y = t * 1.2;
        const h = p < .8 ? tri(p / .8) : 0;
        car.position.y = .4 + 1.1 * h;
        film.scale.y = Math.max(.001, (p < .8 ? Math.min(p / .4, 1) : 1 - (p - .8) / .2) * 1.15);
        film.position.y = .18 + film.scale.y / 2;
        roll.rotation.y = t * 3;
      },
    };
  };

  // เครื่องรัดกล่อง (ซุ้มรัดสาย)
  MODELS.strapping = function (R, M) {
    B(R, M.frame, 1.2, .8, .7, 0, 0, 0);
    B(R, M.steel, 1.25, .05, .75, 0, .8, 0);
    [-1, 1].forEach(s => B(R, M.accent, .1, .75, .1, s * .45, .85, 0));
    B(R, M.accent, 1.0, .1, .1, 0, 1.6, 0);
    const box = B(R, M.carton, .5, .32, .4, 0, .85, 0);
    const strap = G(R, 0, 1.0, 0);
    const s1 = BC(strap, M.strap, .02, .7, .012, -.45, 0, 0), s2 = BC(strap, M.strap, .02, .7, .012, .45, 0, 0), s3 = BC(strap, M.strap, .92, .02, .012, 0, .35, 0), s4 = BC(strap, M.strap, .92, .02, .012, 0, -.35, 0);
    B(R, M.dark, .3, .25, .3, -.3, .3, -.5);
    panelCtl(R, M, .8, 0, .5, -.5, .7);
    return {
      beacon: [-.8, 0, .5],
      tick(t) {
        const p = cycle(t, 4);
        const k = p < .4 ? 1 - .72 * (p / .4) : p < .7 ? .28 : 1;
        strap.scale.set(k, k * .5 + .5, 1);
        strap.position.y = 1.0 - (1 - k) * .0;
        strap.visible = p < .7;
        box.position.x = p < .7 ? 0 : 1.2 * ((p - .7) / .3);
      },
    };
  };

  // =====================================================================
  //  งานเชื่อม (WD)
  // =====================================================================
  MODELS.welder = function (R, M, V) {
    B(R, M.accent, .6, .85, .9, -1.0, .12, -.2);
    [[-1.25, .2], [-.75, .2], [-1.25, -.6], [-.75, -.6]].forEach(([x, z]) => C(R, M.dark, .06, .05, x, .06, z, "x", 12));
    B(R, M.dark, .5, .22, .02, -1.0, .72, .26); B(R, M.screen, .2, .1, .01, -1.1, .78, .27);
    C(R, M.steelDark, .13, 1.3, -1.0, .7, -.7, "y", 20); S(R, M.steelDark, .13, -1.0, 1.35, -.7);
    B(R, M.steel, 1.4, .06, .8, .5, .85, 0); legs(R, M, 1.3, .7, .85, .5, 0, .05);
    B(R, M.steel, .9, .06, .25, .5, .91, 0); B(R, M.steel, .06, .3, .25, .5, .97, 0);
    const torch = G(R, .5, 1.3, .25);
    torch.rotation.x = .6;
    C(torch, M.dark, .03, .3, 0, 0, 0, "y", 10); C(torch, M.steel, .012, .12, 0, -.2, 0, "y", 8);
    const tip = G(torch, 0, -.28, 0);
    const fx = [{ obj: tip, type: V.laser ? "mist" : "sparks", rate: 1.3, color: V.laser ? 0x7fd1ff : 0xffb347 }];
    return {
      beacon: [1.3, 0, .5], fx, arc: tip,
      tick(t) {
        const p = cycle(t, 5);
        torch.position.x = .1 + .8 * p; torch.position.y = 1.3;
        fx[0].active = true;
      },
    };
  };

  // หุ่นยนต์เชื่อม (KUKA)
  MODELS.robot_welder = function (R, M) {
    B(R, M.frame, .9, .25, .9, 0, 0, 0);
    const j1 = G(R, 0, .25, 0); C(j1, M.accent, .32, .3, 0, .15, 0, "y", 24);
    const j2 = G(j1, 0, .3, .0); C(j2, M.accent2, .2, .3, 0, 0, 0, "x", 20);
    const arm1 = G(j2, 0, 0, 0); BC(arm1, M.accent, .22, 1.0, .3, 0, .5, 0);
    const j3 = G(arm1, 0, 1.0, 0); C(j3, M.accent2, .16, .34, 0, 0, 0, "x", 20);
    const arm2 = G(j3, 0, 0, 0); BC(arm2, M.accent, .18, .2, .85, 0, 0, .42);
    const wrist = G(arm2, 0, 0, .85); C(wrist, M.steelDark, .07, .22, 0, 0, 0, "z", 14);
    const torch = G(wrist, 0, -.05, .14); torch.rotation.x = .9; C(torch, M.dark, .025, .3, 0, -.12, 0, "y", 10); C(torch, M.steel, .01, .1, 0, -.3, 0, "y", 8);
    const tip = G(torch, 0, -.36, 0);
    B(R, M.steel, 1.2, .06, .7, 0, .72, 1.2); legs(R, M, 1.1, .6, .72, 0, 1.2, .05);
    C(R, M.steel, .04, 1.0, 0, .83, 1.2, "x", 10); B(R, M.steel, .3, .05, .5, 0, .78, 1.2);
    B(R, M.safety, 2.6, .04, .04, 0, 1.0, -1.1); [-1, 1].forEach(s => C(R, M.safety, .02, 1.0, s * 1.3, .5, -1.1, "y", 8));
    panelCtl(R, M, 1.3, 0, .3, -.6, .85);
    const fx = [{ obj: tip, type: "sparks", rate: 1.4, color: 0xffc46b }];
    return {
      beacon: [-1.3, 0, .6], fx, arc: tip,
      tick(t) {
        j1.rotation.y = Math.sin(t * .5) * .35;
        j2.rotation.x = -.55 + Math.sin(t * .7) * .2;
        j3.rotation.x = 1.25 + Math.sin(t * .9 + 1) * .25;
        wrist.rotation.z = Math.sin(t * 1.3) * .4;
        fx[0].active = true;
      },
    };
  };

  // แขนยกบาลานซ์ลม
  MODELS.lifter = function (R, M) {
    B(R, M.frame, .7, .08, .7, 0, 0, 0);
    C(R, M.steel, .07, 2.2, 0, 1.18, 0, "y", 16);
    const arm = G(R, 0, 2.2, 0);
    BC(arm, M.accent, 1.5, .12, .12, .65, 0, 0);
    const cyl = G(arm, 1.25, 0, 0);
    C(cyl, M.steelDark, .06, .5, 0, -.3, 0, "y", 14);
    const hook = G(cyl, 0, -.55, 0); C(hook, M.steel, .015, .4, 0, -.2, 0, "y", 8); BC(hook, M.wood, .7, .02, .5, 0, -.42, 0);
    return {
      beacon: [-.5, 0, .5],
      tick(t) { arm.rotation.y = Math.sin(t * .4) * .8; hook.position.y = -.55 - .5 * tri(cycle(t, 5)); },
    };
  };

  // โต๊ะงาน / สถานีงานฝีมือ (MS, MB, AL, AD, SKL)
  MODELS.workbench = function (R, M, V) {
    const mode = V.mode || "sand";
    B(R, M.wood2, 1.8, .06, .9, 0, .84, 0); legs(R, M, 1.7, .8, .84, 0, 0, .05);
    B(R, M.frame, 1.6, .04, .7, 0, .3, 0);
    const lampArm = G(R, -.7, .9, -.35); C(lampArm, M.dark, .015, .6, 0, .3, 0, "y", 8); const lh = G(lampArm, .15, .6, .1); lh.rotation.z = -.5; C(lh, M.dark, .08, .12, 0, 0, 0, "y", 16, .03); C(lh, M.lamp, .07, .01, 0, -.06, 0, "y", 16);
    let tool = null, part = null;
    if (mode === "pallet") {
      BC(R, M.wood2, 1.2, .12, .9, 1.6, .06, .2);
      BC(R, M.carton, .5, .45, .4, 1.4, .35, 0); BC(R, M.carton2, .5, .45, .4, 1.85, .35, .35); BC(R, M.carton, .45, .4, .4, 1.5, .8, .1);
      part = slab(R, M, .9, .6, 0, .9, 0);
      tool = G(R, -.4, 1.0, .5); BC(tool, M.dark, .1, .06, .12, 0, 0, 0); // เครื่องยิงฉลาก
    } else if (mode === "assemble") {
      [-.2, 0, .2].forEach(z => B(R, M.steel, 1.2, .03, .03, 0, .9, z));
      B(R, M.steel, .03, .03, .5, -.5, .9, 0); B(R, M.steel, .03, .03, .5, .5, .9, 0);
      tool = G(R, .2, 1.0, 0); C(tool, M.safety, .02, .2, 0, .1, 0, "y", 10); C(tool, M.steel, .006, .1, 0, -.05, 0, "y", 6);
      part = tool;
    } else {
      part = slab(R, M, 1.0, .6, 0, .9, 0);
      tool = G(R, 0, .93, 0); BC(tool, M.dark, .14, .05, .09, 0, 0, 0); BC(tool, M.safety, .1, .03, .06, 0, .04, 0);
    }
    B(R, M.dark, .25, .08, .15, .7, .9, -.3); C(R, M.white, .035, .12, .6, .96, .3, "y", 10);
    const fx = mode === "sand" ? [{ obj: tool, type: "dust", rate: .5, color: 0xe3d2a8 }] : [];
    return {
      beacon: [-1.05, 0, .55], fx,
      tick(t) {
        if (mode === "sand") { tool.position.x = Math.sin(t * 3) * .3; tool.position.z = Math.cos(t * 2.1) * .18; fx[0].active = true; }
        else if (mode === "assemble") { tool.position.x = -.4 + .8 * tri(cycle(t, 4)); tool.position.y = 1.0 - .03 * (Math.sin(t * 12) * .5 + .5); }
        else { tool.position.y = 1.0 - .07 * tri(cycle(t, 2)); part.position.z = .1 * Math.sin(t * .7); }
      },
    };
  };

  // เครื่องจักรทั่วไป (ไม่รู้จักชนิด)
  MODELS.generic = function (R, M) {
    B(R, M.frame, 1.4, 1.15, .9, 0, 0, 0);
    B(R, M.accent, 1.42, .3, .92, 0, .55, 0);
    B(R, M.dark, .5, .3, .02, -.3, .15, .46); B(R, M.screen, .3, .14, .01, .25, .75, .46);
    [M.ledG, M.ledR, M.safety].forEach((m, i) => C(R, m, .018, .012, .12 + i * .1, .62, .46, "z", 12));
    const mot = motor(R, M, .14, .45, -.3, 1.4, -.1, "x");
    const fan = spinner(R, M.steelDark, .13, .02, .0, 1.4, -.1, "x", 20);
    C(R, M.steel, .04, .5, .45, 1.4, -.1, "x", 10); C(R, M.steel, .04, .5, .7, 1.2, -.1, "y", 10);
    B(R, M.steelDark, 1.4, .05, .95, 0, 1.15, 0);
    return { beacon: [.9, 0, .6], tick(t) { fan.mesh.rotation.y = t * 8; } };
  };

  // ป้ายชื่อชนิดสำหรับ HUD และหน้าสาธิต
  MODELS._labels = {
    beam_saw: "เครื่องตัดแผ่นแบบคาน", table_saw: "เลื่อยโต๊ะเลื่อน", miter_saw: "เลื่อยแขน / ตัดองศา", band_saw: "เลื่อยสายพาน",
    cnc_router: "CNC Router / Point-to-point", cnc_drill: "เจาะ CNC แบบป้อนผ่าน", multi_drill: "เจาะหลายหัว", drill_press: "สว่านแท่น",
    edge_bander: "เครื่องปิดขอบตรง", edge_curve: "เครื่องปิดขอบโค้ง", postformer: "เครื่องห่อโค้ง (Postform)", glue_spreader: "เครื่องทากาว",
    panel_press: "เครื่องอัดแผ่น (Press)", metal_press: "เครื่องปั๊มโลหะ", press_brake: "เครื่องพับเหล็ก", tube_bender: "เครื่องดัดท่อ",
    moulder: "เครื่องไส / ใสไม้", sander: "เครื่องขัดสายพาน", spindle_moulder: "เครื่องเพลาตั้ง / เร้าเตอร์", polisher: "เครื่องขัดเงา",
    lathe: "เครื่องกลึง", milling: "เครื่องมิลลิ่ง", grinder: "เครื่องลับคมใบเลื่อย",
    compressor: "เครื่องอัดอากาศ", air_dryer: "เครื่องทำลมแห้ง", chiller: "เครื่องทำน้ำเย็น", dust_collector: "ระบบดูดฝุ่น",
    spray_booth: "บู้ทพ่นสี", oven: "เตาอบสี", spray_line: "ไลน์พ่นสีอัตโนมัติ", conveyor: "สายพานลำเลียง",
    sewing: "จักรเย็บอุตสาหกรรม", pallet_wrapper: "เครื่องพันพาเลท", strapping: "เครื่องรัดกล่อง", shrink_tunnel: "อุโมงค์อบฟิล์มหด",
    welder: "เครื่องเชื่อม", robot_welder: "หุ่นยนต์เชื่อม", lifter: "แขนยกบาลานซ์", workbench: "สถานีงานฝีมือ", generic: "เครื่องจักรทั่วไป",
  };
})();
