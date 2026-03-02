# iso-topojson — ISO 3166-1 Alpha-2 World Map

## Context

This is one of three sibling TopoJSON projects by the same author:

| Project | Features | Key | Purpose |
|---------|----------|-----|---------|
| `~/work/tcc-topojson` | 330 | `tcc_index` | Travelers' Century Club destinations |
| `~/work/nm-unp-topojson` | 265 | `unp_index` | NomadMania UN+ regions |
| **`~/work/iso-topojson`** | ~249 | `iso_a2` | ISO 3166-1 alpha-2 (this project) |

**Read `~/work/nm-unp-topojson/CLAUDE.md` before proceeding.** The pipeline,
toolchain, source data, and extraction strategies are identical. This document
describes only what is different.

## Goal

Produce a public-domain TopoJSON world map with **one polygon per ISO 3166-1
alpha-2 entry**, keyed by `iso_a2`. Output: `iso-a2.json`.

The primary consumer is **`~/work/tripclimate_com`** — a travel calendar app
that serves data for ~250 countries identified by ISO alpha-2 code. The map
powers a planned world choropleth view at `/map`.

No ready-made solution exists: `world-atlas` (the standard npm package) merges
overseas territories into their sovereign state and uses ISO numeric codes, not
alpha-2.

## What Is Different from nm-unp-topojson

### Include: territories with ISO alpha-2 codes

ISO 3166-1 assigns alpha-2 codes to overseas territories, Crown dependencies,
and special administrative regions. These **must be separate polygons**, not
merged into the sovereign state. Examples:

| ISO A2 | Name | Sovereign |
|--------|------|-----------|
| GF | French Guiana | France |
| GP | Guadeloupe | France |
| MQ | Martinique | France |
| RE | Réunion | France |
| YT | Mayotte | France |
| PM | Saint Pierre and Miquelon | France |
| BL | Saint-Barthélemy | France |
| MF | Saint Martin (French part) | France |
| NC | New Caledonia | France |
| PF | French Polynesia | France |
| TF | French Southern Territories | France |
| WF | Wallis and Futuna | France |
| GP | Guadeloupe | France |
| PR | Puerto Rico | USA |
| VI | US Virgin Islands | USA |
| GU | Guam | USA |
| MP | Northern Mariana Islands | USA |
| AS | American Samoa | USA |
| UM | US Minor Outlying Islands | USA |
| AW | Aruba | Netherlands |
| CW | Curaçao | Netherlands |
| SX | Sint Maarten | Netherlands |
| BQ | Bonaire, Sint Eustatius and Saba | Netherlands |
| AI | Anguilla | UK |
| BM | Bermuda | UK |
| VG | British Virgin Islands | UK |
| KY | Cayman Islands | UK |
| FK | Falkland Islands | UK |
| GI | Gibraltar | UK |
| MS | Montserrat | UK |
| SH | Saint Helena, Ascension and T.d.C. | UK |
| TC | Turks and Caicos | UK |
| IO | British Indian Ocean Territory | UK |
| PN | Pitcairn | UK |
| GS | South Georgia and S. Sandwich Is. | UK |
| GG | Guernsey | UK |
| JE | Jersey | UK |
| IM | Isle of Man | UK |
| CX | Christmas Island | Australia |
| CC | Cocos (Keeling) Islands | Australia |
| NF | Norfolk Island | Australia |
| GL | Greenland | Denmark |
| FO | Faroe Islands | Denmark |
| HK | Hong Kong | China |
| MO | Macao | China |
| AX | Åland Islands | Finland |
| SJ | Svalbard and Jan Mayen | Norway |
| BV | Bouvet Island | Norway |
| TW | Taiwan | (disputed) |
| EH | Western Sahara | (disputed) |
| XK | Kosovo | (disputed, quasi-ISO) |
| PS | Palestine | (disputed) |

Natural Earth `admin_0_map_units` and `admin_0_map_subunits` already separates
most of these. See nm-unp-topojson for the extraction strategies per feature.

### Exclude: sub-national regions without ISO alpha-2

nm-unp-topojson includes sub-national entries that NomadMania counts as separate
destinations but do **not** have ISO 3166-1 alpha-2 codes. **Do not include these:**

- England, Scotland, Wales, Northern Ireland (all covered by GB)
- Gibraltar — wait, GI *does* have an ISO code — include it
- Chechen Republic, Dagestan, Ingushetia, Tuva Republic (part of RU)
- Iraqi Kurdistan (part of IQ)
- Crimea (part of UA or RU — politically contested, no ISO code)
- Bosnia — Republika Srpska (part of BA)
- Tibet / Xizang (part of CN)
- Abkhazia, South Ossetia, Transnistria, Somaliland, Northern Cyprus,
  Puntland — no ISO alpha-2 codes; omit unless you can include them as
  `type="disputed"` with a note that `iso_a2` is null

### Primary key is iso_a2, not an index

The TopoJSON `objects.world.geometries` array features are identified by
`properties.iso_a2`. When building with mapshaper or topojson-server, ensure
the feature ID is set to `iso_a2`.

There is no numeric index in this project.

## Source Data

Identical to nm-unp-topojson — all Natural Earth 10m, public domain:

| Layer | Use |
|-------|-----|
| `ne_10m_admin_0_map_subunits` | Countries + UK Crown deps + Gibraltar |
| `ne_10m_admin_0_map_units` | Territories not in subunits |
| `ne_10m_admin_1_states_provinces` | Åland Islands (Finland admin1) |
| `ne_10m_admin_0_breakaway_disputed_areas` | Kosovo, Western Sahara, N. Cyprus |

Do NOT use GADM (non-redistributable license).

## Feature Properties

```
iso_a2      str     ISO 3166-1 alpha-2 — primary key (never null for main features)
iso_a3      str?    ISO 3166-1 alpha-3 (null for Kosovo, some disputed)
iso_n3      int?    ISO 3166-1 numeric (null for Kosovo, some disputed)
name        str     Common English name
sovereign   str     Sovereign state name (same as name for independent countries)
type        str     "country" | "territory" | "disputed" | "dependency"
```

## Extraction Strategy

Start from the nm-unp-topojson strategy table (265 entries). For each entry:

1. If it has an `iso_a2` code in NE properties → include it, use that code
2. If it is sub-national with no ISO alpha-2 → skip it
3. If it is a disputed territory with a quasi-ISO code (XK for Kosovo,
   EH for Western Sahara) → include it with `type="disputed"`

For `BQ` (Bonaire, Sint Eustatius and Saba): NE splits these as three separate
features under `ADM0_A3=BES`. ISO 3166-1 assigns a single code `BQ` to the
collective entity. Options:
- Merge all three into one `BQ` feature (simplest, matches ISO)
- Or keep them separate with `BQ-BO`, `BQ-SE`, `BQ-SA` subdivision codes

**Recommendation:** merge into single `BQ` polygon.

For `SH` (Saint Helena, Ascension and Tristan da Cunha): NE has them as one
feature `ADM0_A3=SHN`. ISO assigns a single `SH` code. Keep as one feature.
(nm-unp-topojson splits them into three for NomadMania counting purposes —
do NOT do that here.)

For `PN` (Pitcairn): too small for a polygon — use a Point marker at
lat=-25.07, lon=-130.09.

For `BV` (Bouvet Island): uninhabited Norwegian territory in the South Atlantic,
very small. Use a Point marker at lat=-54.43, lon=3.38.

For `HM` (Heard Island and McDonald Islands): Australian territory, sub-Antarctic.
Point marker at lat=-53.1, lon=73.5.

## Build Pipeline

Follow the same Makefile structure as nm-unp-topojson:

```
make all
```

Steps:
1. `venv` — create `.venv`, install Python deps (shapely, pyproj, etc.)
2. `download` — fetch Natural Earth 10m shapefiles into `data/`
3. `build` — run `src/build.py` → `output/merged.geojson` (~249 features)
4. `simplify` — mapshaper 3% → `output/iso-a2.json` (TopoJSON)
5. `markers` — polygons ≥ 500 km² kept; smaller → centroid Point
6. `validate` — assert all expected iso_a2 codes present, no duplicates
7. `dist` — copy `iso-a2.json` + `iso-a2-markers.json` to repo root

## Output Files

| File | Description |
|------|-------------|
| `iso-a2.json` | ~249 polygon features, 3% simplified, keyed by iso_a2 |
| `iso-a2-markers.json` | Polygons ≥ 500 km² kept; tiny islands → Point markers |

Target size: `iso-a2.json` < 400 KB.

## Toolchain

Same as nm-unp-topojson:

- `ogr2ogr` (GDAL) — shapefile → GeoJSON
- `mapshaper` — simplify, dissolve, merge, set feature IDs
- Python 3.12 + `shapely` + `pyproj` — build script
- `topojson` CLI (optional) — alternative to mapshaper for final encoding

## Testing

- All expected iso_a2 codes present (derive expected set from ISO 3166-1 list,
  minus codes with no meaningful polygon, plus quasi-ISO disputed codes)
- No duplicate iso_a2 values
- No overlapping polygons
- Visual check: render in `viewer.html` (copy from nm-unp-topojson)
- File size < 400 KB

## Consuming Project

`~/work/tripclimate_com` — see `TODO.md` world map section. The map will be
served as a static asset at `/iso-a2.json` and consumed by the frontend to
render a choropleth at `/map`.

When the map is ready, copy `iso-a2.json` into `tripclimate_com/site/` and
update `tripclimate_com/TODO.md` to mark the iso-topojson dependency as done.

## Known Tricky Cases (inherited from nm-unp-topojson)

- **BES islands** (BQ): Bonaire, Saba, Sint Eustatius are one NE feature.
  Merge into single `BQ` polygon; use `island_bbox` to verify individual
  islands are captured before merging.
- **SHN** (SH): Saint Helena, Ascension, Tristan da Cunha are one NE feature.
  Keep as single `SH` — do not split.
- **Kosovo (XK)**: `ADM0_A3=XKX` in NE. Use quasi-ISO code `XK`.
- **Taiwan (TW)**: `ADM0_A3=TWN` in NE, `ISO_A2=TW`. Include normally.
- **Western Sahara (EH)**: `ADM0_A3=SAH` in NE, `ISO_A2=EH`. Include normally.
- **Palestine (PS)**: `ADM0_A3=PSX` in NE. West Bank + Gaza as one feature.
- **Åland Islands (AX)**: extract via Finland admin1, `name="Aland"` in NE.
- **France metro vs territories**: NE `admin_0_map_units` separates French
  overseas depts. `ADM0_A3=FRA` → metro France only. Each overseas dept has
  its own `ADM0_A3` and `ISO_A2`.
- **Denmark/Greenland/Faroes**: all separate in NE map_units.
- **NE ISO_A2 field quirks**: some NE features have `ISO_A2="-99"` (unknown).
  Cross-reference with `ADM0_A3` → ISO alpha-3 → alpha-2 mapping for these.
  A reference table is in `~/work/nm-unp-topojson/CLAUDE.md`.
