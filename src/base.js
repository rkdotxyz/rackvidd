// Shared map base for the Stockholm-in-time variants: geometry, view, input, per-cell minutes, warp field.
(function () {
  function Base(opt) {
    const D = window.DATA, E = new Engine(D), M = D.meta, dec = Engine.dec;
    const B = { D, E, M, dec, NX: M.nx, NY: M.ny, CELL: M.cell, KN: M.kn };
    const NX = B.NX, NY = B.NY, CELL = B.CELL, KN = B.KN;

    const decLine = b => { const a = dec(b, Int16Array), f = new Float32Array(a.length); for (let i = 0; i < a.length; i++) f[i] = a[i] * 10; return f; };
    B.water = D.water.map(p => p.map(decLine));
    B.coast = D.coast.map(decLine);
    B.lines = D.lines.map(l => ({ col: l.col, kind: l.kind, ways: l.ways.map(decLine) }));
    B.mask = dec(D.grid.mask, Uint8Array); B.near = dec(D.grid.near, Uint16Array); B.neard = dec(D.grid.neard, Uint16Array);
    B.landCells = []; for (let k = 0; k < NX * NY; k++) if (B.mask[k]) B.landCells.push(k);
    B.cellX = i => M.x0 + CELL * (i + 0.5); B.cellY = j => M.y0 + CELL * (j + 0.5);
    B.ll = (lat, lon) => [(lon - M.lon0) * M.mx, (M.lat0 - lat) * M.my];
    B.names = D.stops.name; B.modes = D.stops.modes; B.SN = B.names.length;

    // Campus coordinates are approximate building locations.
    B.CAMPUS = [
      { k: '1', short: 'KTH', name: 'KTH Royal Institute of Technology', at: B.ll(59.3498, 18.0707) },
      { k: '2', short: 'Konstfack', name: 'Konstfack', at: B.ll(59.2983, 17.9968) },
      { k: '3', short: 'KMH', name: 'Royal College of Music (KMH)', at: B.ll(59.3449, 18.0830) },
      { k: '4', short: 'SKH', name: 'Stockholm University of the Arts (SKH)', at: B.ll(59.3380, 18.0985) },
      { k: '5', short: 'SSE', name: 'Stockholm School of Economics', at: B.ll(59.3422, 18.0573) },
      { k: '6', short: 'KKH', name: 'Royal Institute of Art (KKH)', at: B.ll(59.3253, 18.0850) },
      { k: '7', short: 'Scenkonstmuseet', name: 'Scenkonstmuseet', at: B.ll(59.3349, 18.0790) },
    ];
    B.LINEC = { '10': '#1f6fd1', '11': '#1f6fd1', '13': '#e2323b', '14': '#e2323b', '17': '#2fa84f', '18': '#2fa84f', '19': '#2fa84f', '7': '#878A83', '12': '#648FA8', '21': '#B56631', '30': '#D77D00' };
    B.routeColor = r => B.LINEC[r] || null;
    B.pill = r => `<span class="pill" style="background:${B.LINEC[r] || '#6b6e71'}">${/^1\d$/.test(r) ? 'T' : (/^(7|12|21|30)$/.test(r) ? 'L' : '')}${r}</span>`;
    B.fmtMin = m => m >= 119 ? '2 h+' : Math.round(m) + ' min';

    // ---------- view ----------
    const cv = opt.canvas, ctx = cv.getContext('2d');
    B.cv = cv; B.ctx = ctx; B.W = 0; B.H = 0; B.DPR = 1; B.base = 1;
    B.view = { s: 1, cx: 0, cy: 0 };
    const ins = () => opt.insets ? opt.insets() : { left: 0, right: 0, top: 0, bottom: 0 };
    B.fit = function () {
      const i = ins(), aw = B.W - i.left - i.right - 20, ah = B.H - i.top - i.bottom - 20;
      const fx0 = -14000, fx1 = 11500, fy0 = -9500, fy1 = 13000;
      B.base = Math.min(aw / (fx1 - fx0), ah / (fy1 - fy0));
      B.view = { s: B.base, cx: (fx0 + fx1) / 2, cy: (fy0 + fy1) / 2 };
    };
    B.center = () => { const i = ins(); return [i.left + (B.W - i.left - i.right) / 2, i.top + (B.H - i.top - i.bottom) / 2]; };
    B.toS = (x, y) => { const c = B.center(); return [(x - B.view.cx) * B.view.s + c[0], (y - B.view.cy) * B.view.s + c[1]]; };
    B.toM = (px, py) => { const c = B.center(); return [(px - c[0]) / B.view.s + B.view.cx, (py - c[1]) / B.view.s + B.view.cy]; };
    B.resize = function () {
      B.DPR = Math.min(devicePixelRatio || 1, 2); B.W = innerWidth; B.H = innerHeight;
      cv.width = B.W * B.DPR; cv.height = B.H * B.DPR; B.fit(); opt.draw();
    };
    B.zoomAt = function (px, py, f) {
      const a = B.toM(px, py);
      B.view.s = Math.max(B.base * 0.6, Math.min(B.base * 8, B.view.s * f));
      const b = B.toM(px, py);
      B.view.cx += a[0] - b[0]; B.view.cy += a[1] - b[1]; opt.draw();
    };

    // ---------- input ----------
    let down = null, moved = false;
    cv.addEventListener('pointerdown', e => { down = { x: e.clientX, y: e.clientY, cx: B.view.cx, cy: B.view.cy }; moved = false; cv.setPointerCapture(e.pointerId); });
    cv.addEventListener('pointermove', e => {
      if (down) {
        const dx = e.clientX - down.x, dy = e.clientY - down.y;
        if (Math.hypot(dx, dy) > 6) moved = true;
        if (moved) { B.view.cx = down.cx - dx / B.view.s; B.view.cy = down.cy - dy / B.view.s; opt.onHover && opt.onHover(-1, -1, e); opt.draw(); }
        return;
      }
      if (e.pointerType === 'mouse' && opt.onHover) opt.onHover(e.clientX, e.clientY, e);
    });
    cv.addEventListener('pointerup', e => {
      const was = down; down = null;
      if (!was || moved) return;
      const m = B.toM(e.clientX, e.clientY);
      if (m[0] < M.x0 || m[0] > M.x1 || m[1] < M.y0 || m[1] > M.y1) return;
      for (const c of B.CAMPUS) { const p = B.toS(c.at[0], c.at[1]); if (Math.hypot(p[0] - e.clientX, p[1] - e.clientY) < 12) return opt.onTap(c.at[0], c.at[1], c.name, c); }
      const n = B.nearestStop(m[0], m[1]);
      opt.onTap(m[0], m[1], n.d < 350 ? 'Near ' + B.names[n.s] : (n.d / 1000).toFixed(1) + ' km from ' + B.names[n.s], null);
    });
    cv.addEventListener('pointerleave', () => { if (!down && opt.onHover) opt.onHover(-1, -1, null); });
    cv.addEventListener('wheel', e => { e.preventDefault(); B.zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
    addEventListener('resize', B.resize);

    // ---------- helpers ----------
    B.nearestStop = function (x, y) {
      let b = 0, bd = 1e18;
      for (let s = 0; s < B.SN; s++) { const d = Math.hypot(E.sx[s] - x, E.sy[s] - y); if (d < bd) { bd = d; b = s; } }
      return { s: b, d: bd };
    };
    B.stopAtScreen = function (px, py, rad, P, railOnly) {
      P = P || B.toS; let b = -1, bd = rad * rad;
      for (let s = 0; s < B.SN; s++) {
        if (railOnly !== false && !(B.modes[s] & 3)) continue;
        const p = P(E.sx[s], E.sy[s]), d = (p[0] - px) ** 2 + (p[1] - py) ** 2;
        if (d < bd) { bd = d; b = s; }
      }
      return b;
    };
    // minutes to every cell, given minutes to every stop
    B.cellTimes = function (min, ox, oy, out) {
      out = out || new Float32Array(NX * NY);
      for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
        const k = j * NX + i;
        let t = Math.hypot(B.cellX(i) - ox, B.cellY(j) - oy) / M.walk / 60;
        if (B.mask[k]) for (let q = 0; q < KN; q++) { const s = B.near[k * KN + q], tt = min[s] + B.neard[k * KN + q] / 60; if (tt < t) t = tt; }
        out[k] = t;
      }
      return out;
    };
    // smooth everywhere-defined field (for warping geometry)
    B.buildField = function (cellT, F) {
      const n = NX * NY; F = F || new Float32Array(n);
      for (let k = 0; k < n; k++) F[k] = B.mask[k] ? cellT[k] : NaN;
      for (let it = 0; it < 80; it++) {
        let left = 0;
        for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
          const k = j * NX + i; if (!isNaN(F[k])) continue;
          let s = 0, c = 0;
          if (i > 0 && !isNaN(F[k - 1])) { s += F[k - 1]; c++; }
          if (i < NX - 1 && !isNaN(F[k + 1])) { s += F[k + 1]; c++; }
          if (j > 0 && !isNaN(F[k - NX])) { s += F[k - NX]; c++; }
          if (j < NY - 1 && !isNaN(F[k + NX])) { s += F[k + NX]; c++; }
          if (c) F[k] = s / c + 0.15; else left++;
        }
        if (!left) break;
      }
      for (let k = 0; k < n; k++) if (isNaN(F[k])) F[k] = 120;
      const tmp = new Float32Array(n);
      for (let pass = 0; pass < 3; pass++) {
        for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
          let s = 0, c = 0;
          for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
            const ii = i + di, jj = j + dj; if (ii < 0 || jj < 0 || ii >= NX || jj >= NY) continue; s += F[jj * NX + ii]; c++;
          }
          tmp[j * NX + i] = s / c;
        }
        F.set(tmp);
      }
      return F;
    };
    B.fieldAt = function (F, x, y) {
      let gx = (x - M.x0) / CELL - 0.5, gy = (y - M.y0) / CELL - 0.5;
      gx = Math.max(0, Math.min(NX - 1.001, gx)); gy = Math.max(0, Math.min(NY - 1.001, gy));
      const i = gx | 0, j = gy | 0, fx = gx - i, fy = gy - j;
      const a = F[j * NX + i], b = F[j * NX + i + 1], c = F[(j + 1) * NX + i], d = F[(j + 1) * NX + i + 1];
      return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
    };
    // run the router from a point
    B.route = function (x, y, dep) {
      const res = E.average(x, y, dep, 1200, 8);
      return { min: res.min, first: res.first, origin: res.origin };
    };
    // stops along the fastest journey (for drawing), starting with -1 = the origin point
    B.journeyStops = function (first, s) {
      const legs = E.path(first, s), out = [];
      legs.forEach(l => { const st = E.legStops(l); for (const q of st) if (out[out.length - 1] !== q) out.push(q); });
      if (!out.length) out.push(s);
      return { legs, stops: out };
    };
    B.polyline = function (f, P, close) {
      ctx.beginPath();
      for (let i = 0; i < f.length; i += 2) { const p = P(f[i], f[i + 1]); if (i) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); }
      if (close) ctx.closePath();
    };
    B.tag = function (x, y, txt, bg, fg) {
      ctx.font = '500 11px "IBM Plex Mono", monospace'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      const w = ctx.measureText(txt).width + 10, r = 4;
      ctx.fillStyle = bg; ctx.beginPath(); ctx.moveTo(x + r, y - 9); ctx.arcTo(x + w, y - 9, x + w, y + 9, r); ctx.arcTo(x + w, y + 9, x, y + 9, r); ctx.arcTo(x, y + 9, x, y - 9, r); ctx.arcTo(x, y - 9, x + w, y - 9, r); ctx.closePath(); ctx.fill();
      ctx.fillStyle = fg; ctx.fillText(txt, x + 5, y + 0.5);
      return w;
    };
    B.campusPins = function (P, isOn, colOn, colOff, fgOff, bgOff) {
      const placed = [];
      for (const c of B.CAMPUS) {
        const p = P(c.at[0], c.at[1]), on = isOn(c);
        ctx.save(); ctx.translate(p[0], p[1]); ctx.rotate(Math.PI / 4); ctx.fillStyle = on ? colOn : colOff; ctx.fillRect(-3.5, -3.5, 7, 7); ctx.restore();
        ctx.font = '500 11px "IBM Plex Mono", monospace';
        const wdt = ctx.measureText(c.short).width + 10;
        let x = p[0] + 8, y = p[1];
        for (const r of placed) if (Math.abs(r[1] - y) < 15 && x < r[0] + r[2] && x + wdt > r[0]) y = r[1] + 16;
        placed.push([x, y, wdt]);
        B.tag(x, y, c.short, on ? colOn : (bgOff || 'rgba(0,0,0,0)'), on ? '#0d0e0f' : fgOff);
      }
    };
    return B;
  }
  window.Base = Base;
})();
