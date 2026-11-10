"""Step 1 of the data pipeline: timetable, routing graph, coastline and water.

Also adds ESTIMATED timetables for commuter rail (pendeltåg, Roslagsbanan,
Saltsjöbanan) and ferries 80, 82, 89, which are not in the SL extract.

Inputs (all real data):
  - SL GTFS extract (one weekday, 2022): metro, trams/light rail, inner-city buses
    github.com/ludvigwarpe/travelplanner  info/sl_*.txt
  - OSM coastline + SL route geometry (fetched 2026-09), ODbL
    github.com/monolu/jetlag-stockholm  data/osm/*.json
  - Stockholm stad water polygons (Stadskarta 2021), CC0
    github.com/krasch/stockholm-stadsdelar  geojson/simplified/vatten.geo.json

Output: build/timetable.js  (window.DATA = {...}), the input for prep_basemap.py
"""
import base64, json, math, re
import numpy as np
import pandas as pd
from shapely.geometry import shape, box, LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

G = 'sources/travelplanner/info/'
J = 'sources/jetlag-stockholm/data/osm/'
K = 'sources/stockholm-stadsdelar/geojson/simplified/'

LAT0, LON0 = 59.33, 18.06
MY = 111320.0
MX = 111320.0 * math.cos(math.radians(LAT0))
BBOX = (17.70, 59.14, 18.36, 59.51)  # lon0, lat0, lon1, lat1: every station in the data, with a margin


def xy(lon, lat):
    return ((lon - LON0) * MX, (LAT0 - lat) * MY)  # metres, y down


X0, Y1 = xy(BBOX[0], BBOX[1])
X1, Y0 = xy(BBOX[2], BBOX[3])
CLIP = box(X0, Y0, X1, Y1)


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode()


# ---------------- GTFS ----------------
stops = pd.read_csv(G + 'sl_stops.txt', dtype={'stop_id': str})
trips = pd.read_csv(G + 'sl_trips.txt', dtype=str)
routes = pd.read_csv(G + 'sl_routes.txt', dtype=str)
st = pd.read_csv(G + 'sl_stop_times.txt', dtype={'trip_id': str, 'stop_id': str})

# Unnamed light-rail routes in the extract
NAMES = {'1275001200001': '12', '1275002100001': '21', '1275002200001': '30'}
routes['ref'] = routes.apply(lambda r: NAMES.get(r.route_id, r.route_short_name), axis=1)


def mode(r):
    if r.route_type == '401':
        return 'metro'
    if r.route_type == '900':
        return 'tram'
    return 'bus'


routes['mode'] = routes.apply(mode, axis=1)


def clean(n):
    n = re.sub(r'\s+(T-bana|Spårv|station)$', '', n)
    n = re.sub(r'^Stockholm\s+', '', n)
    return n.strip()


used = set(st.stop_id)
stops = stops[stops.stop_id.isin(used)].reset_index(drop=True)
stops['name'] = stops.stop_name.map(clean)
sidx = {s: i for i, s in enumerate(stops.stop_id)}

# which modes serve each stop
tm = trips.merge(routes[['route_id', 'ref', 'mode']], on='route_id')
st = st.merge(tm[['trip_id', 'ref', 'mode']], on='trip_id')
smode = st.groupby('stop_id')['mode'].agg(lambda m: set(m))
MODEBIT = {'metro': 1, 'tram': 2, 'bus': 4}
stops['modes'] = stops.stop_id.map(lambda s: sum(MODEBIT[m] for m in smode[s]))


def secs(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)


st['dep'] = st.departure_time.map(secs)
st['arr'] = st.arrival_time.map(secs)
st = st.sort_values(['trip_id', 'stop_sequence'])

refs = sorted(routes.ref.unique(), key=lambda r: (len(r), r))
ridx = {r: i for i, r in enumerate(refs)}
tlist = list(st.trip_id.unique())
tidx = {t: i for i, t in enumerate(tlist)}

conns = []
for tid, g in st.groupby('trip_id', sort=False):
    s = g.stop_id.map(sidx).values
    d = g.dep.values
    a = g.arr.values
    r = ridx[g.ref.iloc[0]]
    for k in range(len(s) - 1):
        conns.append((d[k], a[k + 1], s[k], s[k + 1], tidx[tid], r))
conns = np.array(conns, dtype=np.int64)
conns = conns[np.argsort(conns[:, 0], kind='stable')]
print('connections', len(conns), 'trips', len(tlist), 'stops', len(stops))


# ================= v4: ESTIMATED commuter rail + ferries =================
import json as _j
_d = _j.load(open(J + 'rail_members.json'))['elements']
_nodes = {x['id']: x for x in _d if x['type'] == 'node'}
SYN = []  # (ref, mode, [(name, lat, lon)], speed_kmh, dwell_min, headways{peak,day,eve})
for r in [x for x in _d if x['type'] == 'relation']:
    ref = r['tags']['ref']
    if ref not in ('40', '41', '43', '25', '26', '27', '28', '29'):
        continue
    seq = []
    for m in r['members']:
        if m['type'] == 'node' and m['role'].startswith('stop') and m['ref'] in _nodes:
            n = _nodes[m['ref']]; seq.append((n['tags'].get('name'), n['lat'], n['lon']))
    if ref in ('40', '41', '43'):
        SYN.append((ref, 'commuter', seq, 70, 0.5, {'peak': 15, 'day': 15, 'eve': 30}))
    elif ref in ('27', '28'):
        SYN.append((ref, 'commuter', seq, 45, 0.5, {'peak': 10, 'day': 15, 'eve': 30}))
    elif ref == '29':
        SYN.append((ref, 'commuter', seq, 45, 0.5, {'peak': 20, 'day': 30, 'eve': 30}))
    elif ref == '25':
        SYN.append((ref, 'commuter', seq, 45, 0.5, {'peak': 10, 'day': 15, 'eve': 30}))
    else:
        SYN.append((ref, 'commuter', seq, 45, 0.5, {'peak': 30, 'day': 30, 'eve': 30}))
# Ferry piers: approximate positions (SL pendelbåt 80, 82, 89)
F80 = [('Nybroplan', 59.3336, 18.0765), ('Allmänna gränd', 59.3236, 18.0965), ('Saltsjöqvarn', 59.3175, 18.1105),
       ('Finnboda', 59.3155, 18.1255), ('Kvarnholmen', 59.3185, 18.1360), ('Blockhusudden', 59.3220, 18.1490),
       ('Nacka strand', 59.3175, 18.1630), ('Dalénum', 59.3490, 18.1230), ('Ropsten brygga', 59.3560, 18.1035)]
F82 = [('Slussen brygga', 59.3218, 18.0745), ('Skeppsholmen', 59.3245, 18.0820), ('Allmänna gränd', 59.3236, 18.0965)]
F89 = [('Klara Mälarstrand', 59.3300, 18.0510), ('Lilla Essingen', 59.3255, 17.9960), ('Ekensberg', 59.3176, 17.9905),
       ('Kungshatt', 59.3045, 17.8880), ('Tappström', 59.3365, 17.7990)]
SYN.append(('80', 'ferry', F80, 18, 1.0, {'peak': 30, 'day': 30, 'eve': 60}))
SYN.append(('82', 'ferry', F82, 14, 1.0, {'peak': 12, 'day': 15, 'eve': 20}))
SYN.append(('89', 'ferry', F89, 22, 1.0, {'peak': 60, 'day': 60, 'eve': 120}))

lo0, la0, lo1, la1 = BBOX
def inside(la, lo, m=0.06):
    return lo0 - m < lo < lo1 + m and la0 - m < la < la1 + m

syn_stops = {}  # name -> index
new_rows = []
for ref, md, seq, *_ in SYN:
    for (nm, la, lo) in seq:
        if not inside(la, lo) or nm in syn_stops:
            continue
        syn_stops[nm] = len(stops) + len(new_rows)
        new_rows.append({'stop_id': 'syn:' + nm, 'stop_name': nm, 'stop_lat': la, 'stop_lon': lo, 'name': nm,
                         'modes': 8 if md == 'commuter' else 16})
stops = pd.concat([stops, pd.DataFrame(new_rows)], ignore_index=True)
for r_ in [x[0] for x in SYN]:
    if r_ not in ridx:
        ridx[r_] = len(refs); refs.append(r_)
MODE_OF = {r: m for r, m, *_ in SYN}

def hw(t, h):
    hr = t / 3600
    if 7 <= hr < 9 or 16 <= hr < 18: return h['peak']
    if hr >= 20 or hr < 6: return h['eve']
    return h['day']

def hav(a, b):
    return math.hypot((a[2] - b[2]) * MX, (a[1] - b[1]) * MY)

extra = []
ntrip = len(tlist)
for k_, (ref, md, seq, spd, dwell, H) in enumerate(SYN):
    seq = [p for p in seq if inside(p[1], p[2])]
    if len(seq) < 2: continue
    # segment run times (s): straight-line distance x1.15 at speed, plus dwell
    seg = [hav(seq[i], seq[i + 1]) * 1.15 / (spd / 3.6) + dwell * 60 for i in range(len(seq) - 1)]
    for direction in (0, 1):
        sq = seq if direction == 0 else seq[::-1]
        sg = seg if direction == 0 else seg[::-1]
        t = 5 * 3600 + (k_ * 97 + direction * 211) % 600
        while t < 24.5 * 3600:
            tt = t
            for i in range(len(sq) - 1):
                a = tt; b = tt + sg[i]
                extra.append((int(a), int(b - dwell * 60 * 0.5), syn_stops[sq[i][0]], syn_stops[sq[i + 1][0]], ntrip, ridx[ref]))
                tt = b
            ntrip += 1
            t += hw(t, H) * 60
conns = np.vstack([conns, np.array(extra, dtype=np.int64)])
conns = conns[np.argsort(conns[:, 0], kind='stable')]
tlist = tlist + ['syn'] * (ntrip - len(tlist))
SYN_LINES = []
for ref, md, seq, *_ in SYN:
    seq = [p for p in seq if inside(p[1], p[2])]
    pts = []
    for (nm, la, lo) in seq:
        x_, y_ = xy(lo, la); pts += [round(x_), round(y_)]
    SYN_LINES.append({'ref': ref, 'kind': md, 'pts': pts})
print('v4: synthetic stops', len(new_rows), 'connections', len(extra), 'trips', ntrip)

# trip -> route index
trip_route = np.zeros(len(tlist), dtype=np.uint8)
trip_route[conns[:, 4]] = conns[:, 5]

# ---------------- stops geometry + footpaths ----------------
sx, sy = zip(*[xy(lo, la) for lo, la in zip(stops.stop_lon.astype(float), stops.stop_lat.astype(float))])
sx = np.array(sx); sy = np.array(sy)
WALK = 1.25 / 1.3  # m/s along the crow-fly line (1.25 m/s with 30% detour)
fp = []
for i in range(len(stops)):
    d = np.hypot(sx - sx[i], sy - sy[i])
    for j in np.where((d < 450) & (d > 0))[0]:
        fp.append((i, j, int(d[j] / WALK) + 60))
fp = np.array(fp, dtype=np.int32)
print('footpaths', len(fp))

# ---------------- map geometry ----------------
def q(coords):
    """quantise a list of (x,y) metres to int16 decametres, flat."""
    a = np.round(np.array(coords) / 10).astype(np.int16)
    return a.reshape(-1)


water = shape(json.load(open(K + 'vatten.geo.json'))['features'][0]['geometry'])
from shapely.affinity import affine_transform
# lon/lat -> metres
water = affine_transform(water, [MX, 0, 0, -MY, -LON0 * MX, LAT0 * MY])
# the sea outside the city, from the OSM coastline (land lies left of each way):
# every 100 m cell near a coastline takes the side of its nearest coastline point
from scipy.spatial import cKDTree
_pts, _dir, _end = [], [], []
for r in json.load(open(J + 'coastline.json'))['runs']:
    if len(r) < 2: continue
    P = np.array([xy(lo, la) for la, lo in r])
    seg = np.diff(P, axis=0); L = np.hypot(seg[:, 0], seg[:, 1])
    for i in range(len(seg)):
        n = max(1, int(L[i] // 25))
        for k in range(n):
            t = k / n; _pts.append(P[i] + seg[i] * t); _dir.append(seg[i] / (L[i] + 1e-9))
            _end.append(1 if (i == 0 and k < 3) or (i == len(seg) - 1 and k > n - 3) else 0)
_pts = np.array(_pts); _dir = np.array(_dir); _end = np.array(_end); tree = cKDTree(_pts)
SC_ = 100
gx_ = np.arange(X0 + SC_ / 2, X1, SC_); gy_ = np.arange(Y0 + SC_ / 2, Y1, SC_)
GX, GY = np.meshgrid(gx_, gy_); Q = np.stack([GX.ravel(), GY.ravel()], 1)
dist, idx = tree.query(Q, k=12)
v = Q[:, None, :] - _pts[idx]; d = _dir[idx]
side = -d[..., 0] * v[..., 1] + d[..., 1] * v[..., 0]        # > 0: land (left of the way, y axis flipped)
w = 1 / (dist + 20) * (1 - _end[idx])
vote = (np.sign(side) * w).sum(1) / (w.sum(1) + 1e-9)
seaC = (vote < -0.6) & (dist[:, 0] < 1800)
from shapely.geometry import box as _box
cells = [_box(x - SC_ / 2, y - SC_ / 2, x + SC_ / 2, y + SC_ / 2) for (x, y), s_ in zip(Q, seaC) if s_]
sea = unary_union(cells).buffer(60).buffer(-60).buffer(-160).buffer(160)
print('sea km2', round(sea.area / 1e6, 1))
sea = [sea]
water = unary_union([water.buffer(0)] + sea)
water = water.intersection(CLIP).simplify(12)
water_rings = []
polys = list(water.geoms) if hasattr(water, 'geoms') else [water]
for p in polys:
    if p.area < 4000:
        continue
    rings = [p.exterior] + [r for r in p.interiors if abs(LineString(r).length) > 150]
    water_rings.append([b64(q(list(r.coords))) for r in rings])
print('water polys', len(water_rings))
water_prep = prep(water.buffer(-40))

coast = json.load(open(J + 'coastline.json'))['runs']
coast_lines = []
for run in coast:
    ls = LineString([xy(lo, la) for la, lo in run])
    ls = ls.intersection(CLIP)
    if ls.is_empty:
        continue
    parts = list(ls.geoms) if hasattr(ls, 'geoms') else [ls]
    for p in parts:
        if p.geom_type != 'LineString' or p.length < 120:
            continue
        p = p.simplify(10)
        coast_lines.append(b64(q(list(p.coords))))
print('coast lines', len(coast_lines))

rg = json.load(open(J + 'route_geom.json'))['elements']
LINECOL = {'blue': '#1f6fd1', 'red': '#e2323b', 'green': '#2fa84f'}
lines = {}
seen = set()
for rel in rg:
    tg = rel.get('tags', {})
    rt = tg.get('route')
    if rt not in ('subway', 'tram', 'light_rail'):
        continue
    col = tg.get('colour', '#888')
    col = LINECOL.get(col, col)
    for m in rel['members']:
        if m['type'] != 'way' or 'geometry' not in m:
            continue
        key = m['ref']
        if key in seen:
            continue
        seen.add(key)
        ls = LineString([xy(p['lon'], p['lat']) for p in m['geometry']]).simplify(5)
        lines.setdefault((col, 'metro' if rt == 'subway' else 'tram'), []).append(b64(q(list(ls.coords))))
line_layers = [{'col': c, 'kind': k, 'ways': w} for (c, k), w in lines.items()]
print('line layers', [(l['col'], l['kind'], len(l['ways'])) for l in line_layers])

# ---------------- grid ----------------
CELL = 200
gx = np.arange(X0 + CELL / 2, X1, CELL)
gy = np.arange(Y0 + CELL / 2, Y1, CELL)
NX, NY = len(gx), len(gy)
mask = np.zeros((NY, NX), dtype=np.uint8)  # 1 = land-ish cell within reach of a stop
KN = 6
near = np.full((NY, NX, KN), 65535, dtype=np.uint16)
neard = np.zeros((NY, NX, KN), dtype=np.uint16)
for iy, y in enumerate(gy):
    for ix, x in enumerate(gx):
        d = np.hypot(sx - x, sy - y)
        o = np.argsort(d)[:KN]
        if d[o[0]] > 1100:
            continue
        if water_prep.contains(Point(x, y)):
            continue
        mask[iy, ix] = 1
        near[iy, ix] = o
        neard[iy, ix] = np.minimum(d[o] / WALK, 65000).astype(np.uint16)
print('grid', NX, NY, 'land cells', mask.sum())

# ---------------- bundle ----------------
DATA = {
    'meta': {
        'lat0': LAT0, 'lon0': LON0, 'mx': MX, 'my': MY,
        'x0': X0, 'y0': Y0, 'x1': X1, 'y1': Y1,
        'cell': CELL, 'nx': NX, 'ny': NY, 'kn': KN, 'walk': WALK,
        'sources': [
            'SL GTFS (GTFS Sverige 2 extract, one weekday, 2022) via github.com/ludvigwarpe/travelplanner',
            'OpenStreetMap coastline + SL route geometry (2026-09) © OpenStreetMap contributors, ODbL, via github.com/monolu/jetlag-stockholm',
            'Stockholm stad Stadskarta water polygons (2021, CC0) via github.com/krasch/stockholm-stadsdelar',
        ],
    },
    'stops': {
        'name': list(stops.name),
        'x': [round(v) for v in sx], 'y': [round(v) for v in sy],
        'modes': [int(m) for m in stops.modes],
    },
    'refs': refs,
    'routeMode': [MODE_OF.get(r) or dict(zip(routes.ref, routes['mode']))[r] for r in refs],
    'estimated': sorted(set(MODE_OF)),
    'synLines': SYN_LINES,
    'conn': {
        'n': int(len(conns)),
        'dep': b64(conns[:, 0].astype(np.int32)),
        'arr': b64(conns[:, 1].astype(np.int32)),
        'from': b64(conns[:, 2].astype(np.uint16)),
        'to': b64(conns[:, 3].astype(np.uint16)),
        'trip': b64(conns[:, 4].astype(np.uint16)),
    },
    'tripRoute': b64(trip_route),
    'fp': {'n': int(len(fp)), 'a': b64(fp[:, 0].astype(np.uint16)), 'b': b64(fp[:, 1].astype(np.uint16)), 't': b64(fp[:, 2].astype(np.uint16))},
    'grid': {'mask': b64(mask), 'near': b64(near), 'neard': b64(neard)},
    'water': water_rings,
    'coast': coast_lines,
    'lines': line_layers,
}
s = 'window.DATA=' + json.dumps(DATA, separators=(',', ':'), ensure_ascii=False) + ';'
open('build/timetable.js', 'w').write(s)
print('build/timetable.js', round(len(s) / 1e6, 2), 'MB')
