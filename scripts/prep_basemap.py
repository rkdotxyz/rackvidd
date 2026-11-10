"""Clean basemap for v10: parks/forest, lakes, main roads (OSM via seunajetomobi/stockholm-life, ODbL),
district outlines + names (Stockholm stad, CC0). Adds window.DATA.base to data_v4."""
import base64, json, math
import numpy as np
from shapely.geometry import Polygon, LineString, shape, box
from shapely.ops import unary_union
from shapely.affinity import affine_transform

src = open('build/timetable.js').read()
D = json.loads(src[len('window.DATA='):-1]); M = D['meta']
CLIP = box(M['x0'], M['y0'], M['x1'], M['y1'])
b64 = lambda a: base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()
def q(coords): return b64(np.round(np.asarray(coords) / 10).astype(np.int16).reshape(-1))
# stockholm-life units: 0.5 m, origin 59.3313 N 18.0603 E, y south
OX = (18.0603 - M['lon0']) * M['mx']; OY = (M['lat0'] - 59.3313) * M['my']; SX = 0.5 * M['mx'] / 56817.0
def T(xs, ys): return np.stack([np.asarray(xs) * SX + OX, np.asarray(ys) * 0.5 + OY], 1)

SL = 'sources/stockholm-life/data/'
m = json.load(open(SL + 'm.json'))
KIND = {'park': 'park', 'garden': 'park', 'recreation_ground': 'park', 'cemetery': 'park', 'golf_course': 'park', 'pitch': 'park', 'grass': 'park', 'meadow': 'park', 'allotments': 'park',
        'wood': 'wood', 'forest': 'wood', 'nature_reserve': 'wood', 'scrub': 'wood', 'beach': None}
polys = {'park': [], 'wood': []}
for tile, lst in m['green'].items():
    for g in lst:
        k = KIND.get(m['gkind'][g[0]]); pts = g[1:]
        if not k or len(pts) < 8: continue
        P = T(pts[0::2], pts[1::2])
        try:
            pg = Polygon(P).buffer(0)
            if pg.area > 1500: polys[k].append(pg)
        except Exception: pass
GREEN = []
for k, ps in polys.items():
    u = unary_union(ps).buffer(15).buffer(-15).simplify(12).intersection(CLIP)
    geoms = list(u.geoms) if hasattr(u, 'geoms') else [u]
    out = []
    for pg in geoms:
        if pg.geom_type != 'Polygon' or pg.area < 4000: continue
        out.append([q(list(pg.exterior.coords))] + [q(list(r.coords)) for r in pg.interiors if Polygon(r).area > 4000])
    GREEN.append({'kind': k, 'polys': out}); print(k, len(out))
LAKES = []
for name, pts in m['water']:
    if len(pts) < 8: continue
    P = T(pts[0::2], pts[1::2])
    try:
        pg = Polygon(P).buffer(0).simplify(10)
        if pg.area > 6000: LAKES.append(q(list(pg.exterior.coords)))
    except Exception: pass
print('lakes', len(LAKES))

r = json.load(open(SL + 'r.json')); nodes = np.array(r['nodes'], float).reshape(-1, 2)
ROADS = {}
for e in r['edges']:
    c = e[2]
    if c > 7: continue
    pts = [nodes[e[0]]] + [np.array(e[6 + 2 * i:8 + 2 * i], float) for i in range((len(e) - 6) // 2)] + [nodes[e[1]]]
    pts = np.array(pts); ROADS.setdefault(c, []).append(T(pts[:, 0], pts[:, 1]))
ROADL = []
for c, lines in sorted(ROADS.items()):
    from shapely.ops import linemerge
    ml = linemerge([LineString(l) for l in lines if len(l) >= 2])
    geoms = list(ml.geoms) if hasattr(ml, 'geoms') else [ml]
    out = [q(list(g.simplify(8).coords)) for g in geoms if g.length > 60]
    tier = 0 if c <= 1 else 1 if c <= 3 else 2 if c <= 5 else 3
    ROADL.append({'tier': tier, 'lines': out})
print('road groups', [(x['tier'], len(x['lines'])) for x in ROADL])

K = 'sources/stockholm-stadsdelar/geojson/simplified/stadsdelar_utan_vatten.geo.json'
dd = json.load(open(K)); DIST = []
for f in dd['features']:
    g = affine_transform(shape(f['geometry']), [M['mx'], 0, 0, -M['my'], -M['lon0'] * M['mx'], M['lat0'] * M['my']]).buffer(0)
    pt = g.representative_point(); big = max(list(g.geoms) if hasattr(g, 'geoms') else [g], key=lambda p: p.area)
    DIST.append({'name': (f['properties'].get('name') or '').title(), 'x': round(pt.x), 'y': round(pt.y), 'area': round(g.area / 1e6, 2),
                 'ring': q(list(big.simplify(25).exterior.coords))})
print('districts', len(DIST), DIST[0]['name'])

D['base'] = {'green': GREEN, 'lakes': LAKES, 'roads': ROADL, 'districts': DIST,
             'attribution': 'Parks, lakes, roads © OpenStreetMap contributors (ODbL), via github.com/seunajetomobi/stockholm-life · districts Stockholm stad (CC0)'}
out = 'window.DATA=' + json.dumps(D, separators=(',', ':'), ensure_ascii=False) + ';'
open('data/stockholm.js', 'w').write(out); print('data/stockholm.js', round(len(out) / 1e6, 2), 'MB')
