# Changelog

## v1.4.0

- **Biomes variant**: 95 climate/travel zones across 30 countries in `iso-a2-markers-biomes.json`
- New biomed countries: EC (Galapagos), MY (Borneo), PT (Madeira, Azores), TZ (Zanzibar), YE (Socotra)
- New biome zones: AU-TASMANIA, CL-EASTERISLAND, IN-ANDAMAN, RU-KALININGRAD
- `short` property on all biome features for compact display labels
- Marker threshold raised from 500 km² to 1000 km² (61 markers in iso-a2-markers, 63 in biomes)
- Fix Socotra missing from Yemen (merge_a3: YES in regions.csv)
- Fix antimeridian centroid for Kiribati and US Minor Outlying Islands
- Biome data files (biomes.json, biome-provinces.json) now tracked in git
- `su_a3` override support for extracting subunit-level biomes (Socotra, Easter Island)
- Cache-busting in viewer.html to prevent stale JSON rendering

## v1.3.0

- **Biomes variant** (`iso-a2-markers-biomes.json`): subdivides large countries into climate/travel zones using admin-1 province boundaries
- Initial 25 biomed countries with 83 zones
- Exclude/transfer logic (Crimea to Ukraine, Svalbard/Bouvet/Tokelau excluded from parent biomes)
- Gap-patching for disputed areas not covered by admin-1 provinces
- Fix Somaliland missing from Somalia across all output variants

## v1.2.0

- Tokelau real polygon from ne_10m_land; no more point-only strategies

## v1.1.1

- Fix feature counts in README and package description

## v1.1.0

- All 250 features as real polygons; Bouvet Island from ne_10m_land

## v1.0.0

- Initial release — ISO 3166-1 alpha-2 world TopoJSON
