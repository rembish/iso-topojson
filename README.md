# iso-topojson

Public-domain TopoJSON world map with **247 polygons** keyed by [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) code.

No existing open-source solution covers this cleanly — `world-atlas` merges overseas territories into their sovereign states and uses ISO numeric codes, not alpha-2.

## Install

```bash
npm install @rembish/iso-topojson
```

## CDN

```
https://unpkg.com/@rembish/iso-topojson/iso-a2.json
https://unpkg.com/@rembish/iso-topojson/iso-a2-markers.json
```

## Files

| File | Size | Description |
|------|------|-------------|
| `iso-a2.json` | 203 KB | Full-detail TopoJSON, 247 polygon features |
| `iso-a2-markers.json` | 246 KB | Compact variant: tiny territories (< 500 km²) replaced with Point markers |

In `iso-a2-markers.json` the ~50 smallest territories (Maldives, Malta, Liechtenstein, most Caribbean islands, etc.) appear as `Point` geometries with `"marker": true` in their properties. Bouvet Island, Heard Island, and US Minor Outlying Islands are point markers in this variant only — they are omitted from the full file. All other features share the same properties schema.

## Usage

### JavaScript

```js
const topology = await fetch(
  "https://unpkg.com/@rembish/iso-topojson/iso-a2.json"
).then(r => r.json());
```

### D3.js — polygons only

```js
import { feature } from "topojson-client";

const allFeatures = Object.values(topology.objects)
  .flatMap(obj => feature(topology, obj).features);

const projection = d3.geoNaturalEarth1();
const path = d3.geoPath(projection);

svg.selectAll("path")
  .data(allFeatures)
  .join("path")
  .attr("d", path)
  .attr("fill", d => colorByCode(d.properties.iso_a2));
```

### D3.js — markers file (polygons + point circles)

```js
import { feature } from "topojson-client";

const topology = await fetch(
  "https://unpkg.com/@rembish/iso-topojson/iso-a2-markers.json"
).then(r => r.json());

const allFeatures = Object.values(topology.objects)
  .flatMap(obj => feature(topology, obj).features);

const polygons = allFeatures.filter(
  f => f.geometry.type === "Polygon" || f.geometry.type === "MultiPolygon"
);
const markers = allFeatures.filter(f => f.geometry.type === "Point");

// Draw polygon features
svg.selectAll("path")
  .data(polygons)
  .join("path")
  .attr("d", path)
  .attr("fill", d => colorByCode(d.properties.iso_a2));

// Draw point markers
svg.selectAll("circle")
  .data(markers)
  .join("circle")
  .attr("r", 3)
  .attr("cx", d => projection(d.geometry.coordinates)[0])
  .attr("cy", d => projection(d.geometry.coordinates)[1])
  .attr("fill", d => colorByCode(d.properties.iso_a2));
```

## Feature Properties

| Property | Type | Description |
|----------|------|-------------|
| `iso_a2` | `string` | ISO 3166-1 alpha-2 code — primary key |
| `iso_a3` | `string \| null` | ISO 3166-1 alpha-3 code |
| `iso_n3` | `number \| null` | ISO 3166-1 numeric code |
| `name` | `string` | Common English name |
| `sovereign` | `string` | Sovereign state name (same as `name` for independent countries) |
| `type` | `string` | `"country"`, `"territory"`, `"disputed"`, or `"dependency"` |
| `marker` | `boolean` | `true` if this feature is a Point marker (markers file only) |
| `area_km2` | `number` | Area in km² (markers file only, for classified features) |

## Coverage

All 249 ISO 3166-1 alpha-2 entries with a meaningful geographic polygon are included, plus Kosovo (`XK`, quasi-ISO). Overseas territories, Crown dependencies, and special administrative regions are **separate polygons**, not merged into their sovereign state:

- French overseas departments and territories (GF, GP, MQ, RE, YT, PM, BL, MF, NC, PF, TF, WF)
- British Overseas Territories (AI, BM, FK, GI, GG, GS, IO, IM, JE, KY, MS, SH, TC, VG)
- US territories (AS, GU, MP, PR, VI)
- Dutch Caribbean (AW, BQ, CW, SX)
- Australian territories (CC, CX, NF)
- Danish territories (FO, GL)
- Norwegian territories (SJ)
- Chinese SARs (HK, MO)
- Disputed / quasi-ISO (EH, PS, TW, XK)
- And many more…

Bouvet Island (BV), Heard Island (HM), and US Minor Outlying Islands (UM) appear as Point markers in `iso-a2-markers.json` only.

## Build

Prerequisites: **Python 3.12+**, **Node.js** (for `npx mapshaper`).

```bash
make all
```

Full pipeline:

1. **venv** — creates `.venv` and installs Python dependencies
2. **check** — lint (`ruff`, `black`), type-check (`mypy`), tests (`pytest`, ≥ 80% coverage)
3. **download** — fetches Natural Earth 10m shapefiles
4. **build** — assembles 247 GeoJSON features via direct matches, subunit extractions, admin-1 merges, island bbox extractions, and disputed-area overlays → `output/merged.geojson`
5. **simplify** — runs `mapshaper` at **3% vertex retention** → `output/iso-a2.json` (203 KB)
6. **markers** — replaces polygons < 500 km² with centroid point markers → `output/iso-a2-markers.json` (246 KB)
7. **validate** — checks all expected codes are present and valid
8. **dist** — copies both files to the repo root

### Tuning simplification

```bash
make simplify SIMPLIFY=5%   # more detail (larger file)
make simplify SIMPLIFY=1%   # more compression (smaller file)
```

## Viewer

```bash
make serve
# → http://localhost:8000/viewer.html
```

Renders all features coloured by type (country / territory / disputed / dependency). Toggle between Full and Markers variants. Hover for iso_a2, name, sovereign, type, and area.

## Data Sources

| Source | License | Use |
|--------|---------|-----|
| [Natural Earth 10m](https://www.naturalearthdata.com/) | Public domain | Base polygons |

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — derived from [Natural Earth](https://www.naturalearthdata.com/) (public domain).
