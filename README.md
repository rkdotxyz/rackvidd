# Räckvidd

**How far does Stockholm let you go in half an hour?**

Click anywhere on the map. Ink spreads as far as SL can take you from that spot: strong up to 30 minutes, thinning out towards an hour. Each area is painted in the colour of the line that gets you there, and the lines you would ride grow out to every station they reach, in step with the ink.

*Räckvidd* is Swedish for *reach*. It is an interactive piece made for NAVET Week at Scenkonstmuseet, Stockholm (December 2026).

## Run it

Open `index.html` in a browser. It is one self-contained file and works offline (fonts load from Google Fonts when online).

## How it works

- **Routing:** a Connection Scan router (`src/engine.js`) runs in the browser over a full weekday SL timetable plus walking (1.25 m/s, 30% detour). Travel times are door to door and include waiting; each click averages eight departures between 08:00 and 08:20.
- **Ink:** the city is split into 200 m cells. Each cell gets its travel time and the line that reaches it, then the cells are rendered as a blurred, granulated watercolour wash with pigment pooling at the 30-minute edge.
- **Lines:** the hops of the fastest journeys are drawn station to station, timed with the same travel times as the ink, so they branch as the ink spreads.
- **Map:** greyscale basemap (land, water, parks, forests, roads, districts) drawn on a canvas from open data, so the only colour on screen is the ink.

## Repository

| Path | What it is |
| --- | --- |
| `index.html` | The built piece, ready to open |
| `src/app.html` | Page, styles and interaction (template) |
| `src/engine.js` | Connection Scan router |
| `src/base.js` | Map projection, pan/zoom, grid helpers |
| `data/stockholm.js` | Pre-built data: timetable, routing grid, basemap |
| `scripts/` | Data pipeline and build script |

### Rebuild

```bash
pip install numpy pandas shapely
./scripts/fetch_sources.sh               # download the open datasets into ./sources
mkdir -p build
python3 scripts/prep_timetable.py        # -> build/timetable.js
python3 scripts/prep_basemap.py          # -> data/stockholm.js
python3 scripts/build.py                 # -> index.html
```

Only `scripts/build.py` is needed after editing `src/`.

## Data and limitations

- **SL timetable:** a GTFS extract (one weekday, 2022) with metro, trams/light rail and inner-city buses, via [ludvigwarpe/travelplanner](https://github.com/ludvigwarpe/travelplanner). It is not the current timetable; for that, download SL's GTFS Regional feed from [Trafiklab](https://www.trafiklab.se/) (free API key) and point `prep_timetable.py` at it.
- **Estimated:** commuter rail (pendeltåg, Roslagsbanan, Saltsjöbanan) and ferries 80, 82, 89 are not in that extract. Their timetables are estimated from OpenStreetMap station order with speeds and frequencies tuned to typical journey times, and ferry piers are approximate. They are marked with * in the piece.
- **Suburban buses** are not included, so the outer suburbs look less connected than they are.
- **Basemap detail** (parks, roads) covers central Stockholm (about 20 × 18 km).

## Credits

- Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, ODbL: coastline and rail geometry via [monolu/jetlag-stockholm](https://github.com/monolu/jetlag-stockholm); parks, lakes and roads via [seunajetomobi/stockholm-life](https://github.com/seunajetomobi/stockholm-life).
- Districts and water: Stockholm stad open data (Stadskarta), CC0, via [krasch/stockholm-stadsdelar](https://github.com/krasch/stockholm-stadsdelar).
- SL timetable data from Samtrafiken/SL.

By [Rama Krushna Behera](https://ramakrushna.xyz) (RK).
