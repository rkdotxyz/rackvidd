// Connection Scan routing over the SL timetable + walking. Shared by the page and the node test.
(function (root) {
  function dec(b64, Type) {
    const bin = typeof atob === 'function' ? atob(b64) : Buffer.from(b64, 'base64').toString('binary');
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Type(u8.buffer);
  }

  function Engine(D) {
    const S = D.stops.name.length;
    this.D = D;
    this.S = S;
    this.sx = Float64Array.from(D.stops.x);
    this.sy = Float64Array.from(D.stops.y);
    const c = D.conn;
    this.cdep = dec(c.dep, Int32Array);
    this.carr = dec(c.arr, Int32Array);
    this.cfrom = dec(c.from, Uint16Array);
    this.cto = dec(c.to, Uint16Array);
    this.ctrip = dec(c.trip, Uint16Array);
    this.tripRoute = dec(D.tripRoute, Uint8Array);
    this.ntrips = this.tripRoute.length;
    const fa = dec(D.fp.a, Uint16Array), fb = dec(D.fp.b, Uint16Array), ft = dec(D.fp.t, Uint16Array);
    // adjacency for footpaths
    this.fpStart = new Int32Array(S + 1);
    for (let i = 0; i < fa.length; i++) this.fpStart[fa[i] + 1]++;
    for (let i = 0; i < S; i++) this.fpStart[i + 1] += this.fpStart[i];
    this.fpTo = new Uint16Array(fa.length);
    this.fpT = new Uint16Array(fa.length);
    const fill = this.fpStart.slice(0, S);
    for (let i = 0; i < fa.length; i++) { const k = fill[fa[i]]++; this.fpTo[k] = fb[i]; this.fpT[k] = ft[i]; }
    this.walk = D.meta.walk;
    this.CHANGE = 60; // seconds buffer to board at a stop
  }

  // first connection index with dep >= t
  Engine.prototype.lower = function (t) {
    let lo = 0, hi = this.cdep.length;
    while (lo < hi) { const m = (lo + hi) >> 1; if (this.cdep[m] < t) lo = m + 1; else hi = m; }
    return lo;
  };

  // origin: array of [stopIndex, walkSeconds]; t0 departure (s after midnight)
  // returns {arr: Float64Array (absolute seconds), via: Int32Array (connection index or -1 = walked from origin, -2 = footpath)}
  Engine.prototype.scan = function (origin, t0, horizon) {
    const S = this.S, INF = 1e9;
    const arr = new Float64Array(S).fill(INF);
    const via = new Int32Array(S).fill(-1);
    const viaFp = new Int32Array(S).fill(-1); // stop we walked from
    const tripOn = new Uint8Array(this.ntrips);
    const tripBoard = new Int32Array(this.ntrips).fill(-1);
    for (const [s, w] of origin) if (t0 + w < arr[s]) { arr[s] = t0 + w; via[s] = -1; }
    const tEnd = t0 + (horizon || 7200);
    const { cdep, carr, cfrom, cto, ctrip, fpStart, fpTo, fpT, CHANGE } = this;
    for (let i = this.lower(t0), n = cdep.length; i < n; i++) {
      const d = cdep[i];
      if (d > tEnd) break;
      const tr = ctrip[i];
      if (!tripOn[tr]) {
        if (arr[cfrom[i]] + CHANGE > d) continue;
        tripOn[tr] = 1; tripBoard[tr] = i;
      }
      const to = cto[i], a = carr[i];
      if (a < arr[to]) {
        arr[to] = a; via[to] = tripBoard[tr]; viaFp[to] = -1;
        this._lastConn = i;
        // remember alighting connection for path reconstruction
        if (!this._alight) this._alight = new Int32Array(S);
        this._alight[to] = i;
        for (let k = fpStart[to], e = fpStart[to + 1]; k < e; k++) {
          const s2 = fpTo[k], a2 = a + fpT[k];
          if (a2 < arr[s2]) { arr[s2] = a2; via[s2] = -2; viaFp[s2] = to; }
        }
      }
    }
    return { arr, via, viaFp, alight: this._alight ? this._alight.slice() : null, t0 };
  };

  // stops reachable on foot from point (x,y) metres
  Engine.prototype.originFromPoint = function (x, y, maxWalkSec) {
    const out = [];
    const lim = maxWalkSec || 1200;
    for (let s = 0; s < this.S; s++) {
      const w = Math.hypot(this.sx[s] - x, this.sy[s] - y) / this.walk;
      if (w <= lim) out.push([s, w]);
    }
    if (!out.length) { // nearest stop anyway
      let b = 0, bd = 1e18;
      for (let s = 0; s < this.S; s++) { const d = Math.hypot(this.sx[s] - x, this.sy[s] - y); if (d < bd) { bd = d; b = s; } }
      out.push([b, bd / this.walk]);
    }
    return out;
  };

  // average travel time (minutes) to each stop over several departures in [t0, t0+window)
  Engine.prototype.average = function (x, y, t0, window, samples) {
    const origin = this.originFromPoint(x, y);
    const S = this.S;
    const sum = new Float64Array(S);
    let last = null;
    for (let k = 0; k < samples; k++) {
      const t = t0 + (window * k) / samples;
      const r = this.scan(origin, t, 7200);
      for (let s = 0; s < S; s++) sum[s] += Math.min(r.arr[s] - t, 7200);
      if (k === 0) last = r;
    }
    const min = new Float32Array(S);
    for (let s = 0; s < S; s++) min[s] = sum[s] / samples / 60;
    return { min, first: last, origin };
  };

  // legs of the fastest journey to stop s for a scan result
  Engine.prototype.path = function (r, s) {
    const legs = [];
    let guard = 0;
    while (guard++ < 40) {
      const v = r.via[s];
      if (v === -1) break;
      if (v === -2) { legs.push({ walk: true, from: r.viaFp[s], to: s }); s = r.viaFp[s]; continue; }
      const board = v, al = r.alight[s];
      legs.push({ route: this.D.refs[this.tripRoute[this.ctrip[board]]], from: this.cfrom[board], to: s, dep: this.cdep[board], arr: this.carr[al], trip: this.ctrip[board], board, alight: al });
      s = this.cfrom[board];
    }
    return legs.reverse();
  };

  Engine.prototype.legStops = function (leg) {
    if (leg.walk) return [leg.from, leg.to];
    const out = [this.cfrom[leg.board]];
    for (let i = leg.board; i <= leg.alight; i++) if (this.ctrip[i] === leg.trip) out.push(this.cto[i]);
    return out;
  };

  Engine.dec = dec;
  root.Engine = Engine;
})(typeof window !== 'undefined' ? window : globalThis);
