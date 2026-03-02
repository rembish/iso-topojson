"""Download Natural Earth 10m shapefiles for the ISO-A2 build pipeline."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

NE_CULTURAL = "https://naciscdn.org/naturalearth/10m/cultural"
NE_PHYSICAL = "https://naciscdn.org/naturalearth/10m/physical"

NE_DATASETS: list[tuple[str, str]] = [
    (NE_CULTURAL, "ne_10m_admin_0_map_subunits"),
    (NE_CULTURAL, "ne_10m_admin_0_map_units"),
    (NE_CULTURAL, "ne_10m_admin_1_states_provinces"),
    (NE_CULTURAL, "ne_10m_admin_0_disputed_areas"),
    (NE_PHYSICAL, "ne_10m_land"),
]


def download_ne_dataset(base_url: str, name: str) -> None:
    """Download and extract a Natural Earth shapefile zip.

    Skips the download if the ``.shp`` file already exists in ``DATA_DIR``.

    Args:
        base_url: Base URL for the dataset category (cultural or physical).
        name: Dataset basename without extension, e.g. ``ne_10m_admin_0_map_subunits``.
    """
    target = DATA_DIR / f"{name}.shp"
    if target.exists():
        print(f"  {name} — already exists, skipping")
        return

    url = f"{base_url}/{name}.zip"
    print(f"  Downloading {name}...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(DATA_DIR)
    print(f"  {name} — done")


def main() -> None:
    """Download all source datasets to ``DATA_DIR``."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading source data...")

    for base_url, name in NE_DATASETS:
        download_ne_dataset(base_url, name)

    print("All downloads complete.")


if __name__ == "__main__":
    main()
