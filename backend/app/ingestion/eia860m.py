"""EIA-860M August 2026 plant locations.

Source file: EIA-860M August 2026 generator inventory (august_generator2026.xlsx).
Sheets used: Operating, Planned, Operating_PR, Planned_PR.
Retired and canceled sheets are not worksites.

Verified coordinate columns:
- Operating and Operating_PR: Latitude column 35, Longitude column 36.
- Planned and Planned_PR: Latitude column 21, Longitude column 22.
Header row is Excel row 3. Values are decimal degrees. Every generator row in
the August file had numeric coordinates.

Import mapping onto Site:
- id: eia860m-{plant state}-{plant id}
- name: Plant Name
- lat, lon: coordinates from the generator with the largest nameplate capacity
- region: Plant State
- location_type: power_plant
- source: EIA-860M August 2026 (representative power plant location)

One plant is stored once. Generators at the same plant are not separate sites.
Two plants that share coordinates rounded to four decimal places are one location.
The selection keeps every state in the file. Counts vary with how many real
locations that state has, and the average is five. No state is filled with
invented plants.
"""

from collections import defaultdict
from dataclasses import dataclass
from math import floor, sqrt

SOURCE_LABEL = "EIA-860M August 2026 (representative power plant location)"
TARGET_AVERAGE = 5

_SHEETS = (
    ("Operating", 35, 36, True),
    ("Operating_PR", 35, 36, True),
    ("Planned", 21, 22, False),
    ("Planned_PR", 21, 22, False),
)


@dataclass(frozen=True)
class PlantLocation:
    plant_id: str
    name: str
    state: str
    lat: float
    lon: float
    operating: bool
    capacity_mw: float

    @property
    def site_id(self) -> str:
        return f"eia860m-{self.state}-{self.plant_id}"


def select_worksites(
    plants: list[PlantLocation], target_average: float = TARGET_AVERAGE
) -> list[PlantLocation]:
    """Pick real locations so the average count per state is about five."""
    unique = _one_per_location(plants)
    by_state: dict[str, list[PlantLocation]] = defaultdict(list)
    for plant in unique:
        by_state[plant.state].append(plant)
    if not by_state:
        return []
    quotas = _quotas({state: len(rows) for state, rows in by_state.items()}, target_average)
    chosen: list[PlantLocation] = []
    for state in sorted(by_state):
        chosen.extend(_spread(by_state[state], quotas[state]))
    return chosen


def load_plants(path: str) -> list[PlantLocation]:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        plants: list[PlantLocation] = []
        for sheet, lat_index, lon_index, operating in _SHEETS:
            if sheet not in workbook.sheetnames:
                continue
            plants.extend(_read_sheet(workbook[sheet], lat_index, lon_index, operating))
        return plants
    finally:
        workbook.close()


def import_workbook(path: str) -> list[PlantLocation]:
    """Replace previously imported EIA-860M sites with the selected worksites."""
    from app.db.init import load_env_file
    from app.db.session import get_session

    selected = select_worksites(load_plants(path))
    load_env_file()
    session = get_session()
    try:
        from app.db.models import Site

        session.query(Site).filter(Site.source.like("EIA-860M%")).delete(synchronize_session=False)
        for plant in selected:
            session.add(
                Site(
                    id=plant.site_id,
                    name=plant.name,
                    lat=plant.lat,
                    lon=plant.lon,
                    location_type="power_plant",
                    source=SOURCE_LABEL,
                    region=plant.state,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return selected


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _read_sheet(worksheet, lat_index: int, lon_index: int, operating: bool) -> list[PlantLocation]:
    plants: list[PlantLocation] = []
    for row in worksheet.iter_rows(min_row=4, values_only=True):
        if not row or row[2] in (None, ""):
            continue
        lat = _number(row[lat_index] if lat_index < len(row) else None)
        lon = _number(row[lon_index] if lon_index < len(row) else None)
        state = str(row[6] or "").strip()
        if lat is None or lon is None or not state:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            continue
        plants.append(
            PlantLocation(
                plant_id=str(row[2]).strip(),
                name=str(row[3] or "").strip() or str(row[2]).strip(),
                state=state,
                lat=lat,
                lon=lon,
                operating=operating,
                capacity_mw=_number(row[12]) or 0.0,
            )
        )
    return plants


def _one_per_location(plants: list[PlantLocation]) -> list[PlantLocation]:
    by_plant: dict[tuple[str, str], PlantLocation] = {}
    for plant in plants:
        key = (plant.state, plant.plant_id)
        current = by_plant.get(key)
        if current is None or _prefer(plant, current):
            by_plant[key] = plant
    by_location: dict[tuple[str, float, float], PlantLocation] = {}
    for plant in by_plant.values():
        key = (plant.state, round(plant.lat, 4), round(plant.lon, 4))
        current = by_location.get(key)
        if current is None or _prefer(plant, current):
            by_location[key] = plant
    return list(by_location.values())


def _prefer(candidate: PlantLocation, current: PlantLocation) -> bool:
    if candidate.operating != current.operating:
        return candidate.operating
    return candidate.capacity_mw > current.capacity_mw


def _quotas(counts: dict[str, int], target_average: float) -> dict[str, int]:
    """Keep each state near five sites, and give states with more real plants a larger share.

    A state never receives more plants than the file contains. The floor is four when
    the state has that many, so a small state is not cut to one and is not padded.
    """
    states = sorted(counts)
    target_total = min(sum(counts.values()), round(target_average * len(states)))
    quotas = {state: min(counts[state], 4) for state in states}
    remainder = target_total - sum(quotas.values())
    if remainder <= 0:
        return quotas
    weights = {state: sqrt(counts[state]) for state in states}
    weight_total = sum(weights.values())
    raw = {state: remainder * weights[state] / weight_total for state in states}
    for state in states:
        extra = min(counts[state] - quotas[state], floor(raw[state]))
        quotas[state] += extra
    remainder = target_total - sum(quotas.values())
    ranked = sorted(states, key=lambda state: (-(raw[state] - floor(raw[state])), state))
    index = 0
    while remainder > 0 and any(quotas[state] < counts[state] for state in states):
        state = ranked[index % len(ranked)]
        if quotas[state] < counts[state]:
            quotas[state] += 1
            remainder -= 1
        index += 1
    return quotas


def _spread(plants: list[PlantLocation], count: int) -> list[PlantLocation]:
    ordered = sorted(plants, key=lambda plant: (plant.lat, plant.lon, plant.plant_id))
    if count >= len(ordered):
        return ordered
    if count == 1:
        return [ordered[len(ordered) // 2]]
    step = (len(ordered) - 1) / (count - 1)
    return [ordered[round(index * step)] for index in range(count)]


def main() -> None:
    import sys
    from collections import Counter

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.ingestion.eia860m PATH_TO_AUGUST_XLSX")
    selected = import_workbook(sys.argv[1])
    counts = Counter(plant.state for plant in selected)
    average = len(selected) / len(counts)
    print(
        f"Imported {len(selected)} real plant locations across {len(counts)} states. "
        f"Average {average:.2f} per state, from {min(counts.values())} to {max(counts.values())}."
    )


if __name__ == "__main__":
    main()
