# iso-topojson

Public-domain TopoJSON world map with **250 polygons** keyed by [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) code.

No existing open-source solution covers this cleanly — `world-atlas` merges overseas territories into their sovereign states and uses ISO numeric codes, not alpha-2.

## Install

```bash
npm install @rembish/iso-topojson
```

## CDN

```
https://unpkg.com/@rembish/iso-topojson/iso-a2.json
https://unpkg.com/@rembish/iso-topojson/iso-a2-markers.json
https://unpkg.com/@rembish/iso-topojson/iso-a2-markers-biomes.json
```

## Files

| File | Size | Description |
|------|------|-------------|
| `iso-a2.json` | 204 KB | Full-detail TopoJSON, 250 polygon features |
| `iso-a2-markers.json` | 246 KB | Compact variant: tiny territories (< 500 km²) replaced with Point markers |
| `iso-a2-markers-biomes.json` | 317 KB | Biomes variant: 25 large countries subdivided into 83 climate/travel zones |

### Biomes variant

`iso-a2-markers-biomes.json` replaces 25 large countries with multiple **biome polygons** — climate and travel zones derived from admin-1 province boundaries. For example, the United States is split into 7 zones (Northeast, Southeast, Midwest, West Coast, Southwest, Hawaii, Alaska) and Russia into 4 (West, North, Siberia, Far East).

Countries with biome subdivisions: AR, AU, BR, CA, CL, CN, CO, ES, FI, GR, ID, IN, IT, JP, MX, NO, NZ, PE, RU, SE, TH, TR, US, VN, ZA.

The remaining 225 countries appear as single polygons, same as in `iso-a2-markers.json`. Tiny territories are Point markers. Total: 308 features (258 polygons + 50 point markers).

In `iso-a2-markers.json` the ~50 smallest territories (Maldives, Malta, Liechtenstein, most Caribbean islands, etc.) appear as `Point` geometries with `"marker": true` in their properties. All features share the same properties schema.

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
| `marker` | `boolean` | `true` if this feature is a Point marker (markers files only) |
| `area_km2` | `number` | Area in km² (markers files only, for classified features) |

### Biome-specific properties (biomes variant only)

| Property | Type | Description |
|----------|------|-------------|
| `biome_id` | `string` | Biome identifier, e.g. `"US-ALASKA"`, `"RU-SIBERIA"` |
| `aurora_zone` | `boolean` | Whether the biome is in the aurora viewing zone |

## Coverage

All 250 entries (249 ISO 3166-1 alpha-2 + Kosovo `XK` quasi-ISO) are included as polygons. Overseas territories, Crown dependencies, and special administrative regions are **separate polygons**, not merged into their sovereign state:

- French overseas departments and territories (GF, GP, MQ, RE, YT, PM, BL, MF, NC, PF, TF, WF)
- British Overseas Territories (AI, BM, FK, GI, GG, GS, IO, IM, JE, KY, MS, SH, TC, VG)
- US territories (AS, GU, MP, PR, VI)
- Dutch Caribbean (AW, BQ, CW, SX)
- Australian territories (CC, CX, NF)
- Danish territories (FO, GL)
- Norwegian territories (SJ)
- Chinese SARs (HK, MO)
- Disputed / quasi-ISO (EH, PS, TW, XK)
- And many more...

All 250 entries appear as polygons in `iso-a2.json`. Bouvet Island (BV, ~55 km²) is extracted from the NE physical land layer since it is absent from the admin layers. In `iso-a2-markers.json`, the ~50 smallest territories are replaced with centroid point markers.

## Build

Prerequisites: **Python 3.12+**, **Node.js** (for `npx mapshaper`).

```bash
make all
```

Full pipeline:

1. **venv** — creates `.venv` and installs Python dependencies
2. **check** — lint (`ruff`, `black`), type-check (`mypy`), tests (`pytest`, >= 80% coverage)
3. **download** — fetches Natural Earth 10m shapefiles
4. **build** — assembles 250 GeoJSON features via direct matches, subunit extractions, admin-1 merges, island bbox extractions, and disputed-area overlays -> `output/merged.geojson`
5. **simplify** — runs `mapshaper` at **3% vertex retention** -> `output/iso-a2.json` (204 KB)
6. **markers** — replaces polygons < 500 km² with centroid point markers -> `output/iso-a2-markers.json` (246 KB)
7. **validate** — checks all expected codes are present and valid
8. **dist** — copies output files to the repo root

### Biomes build

```bash
make build-biomes dist-biomes
```

Subdivides 25 large countries into climate/travel zones using admin-1 province boundaries and produces `iso-a2-markers-biomes.json` (317 KB, 308 features).

### Tuning simplification

```bash
make simplify SIMPLIFY=5%   # more detail (larger file)
make simplify SIMPLIFY=1%   # more compression (smaller file)
```

## Viewer

```bash
make serve
# -> http://localhost:8000/viewer.html
```

Renders all features coloured by type (country / territory / disputed / dependency). Toggle between Full, Markers, and Biomes variants. Hover for iso_a2, name, sovereign, type, and area.

## Data Sources

| Source | License | Use |
|--------|---------|-----|
| [Natural Earth 10m](https://www.naturalearthdata.com/) | Public domain | Base polygons |

## License

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — derived from [Natural Earth](https://www.naturalearthdata.com/) (public domain).
