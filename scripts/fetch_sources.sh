#!/usr/bin/env bash
# Fetch the open datasets the prep scripts read into ./sources (only needed to rebuild data/stockholm.js).
set -e
mkdir -p sources && cd sources
clone() { [ -d "$2" ] || git clone --depth 1 "https://github.com/$1" "$2"; }
clone ludvigwarpe/travelplanner travelplanner          # SL GTFS extract (weekday, 2022)
clone monolu/jetlag-stockholm jetlag-stockholm          # OSM coastline, SL rail geometry
clone krasch/stockholm-stadsdelar stockholm-stadsdelar  # Stockholm stad districts + water (CC0)
clone seunajetomobi/stockholm-life stockholm-life       # OSM parks, lakes, roads
