from app.ingestion.eia860m import PlantLocation, select_worksites


def plant(plant_id: str, state: str, lat: float, lon: float, capacity: float = 1) -> PlantLocation:
    return PlantLocation(plant_id, f"Plant {plant_id}", state, lat, lon, True, capacity)


def test_generators_at_one_plant_become_one_worksite() -> None:
    rows = [
        plant("10", "TX", 30.0, -97.0, capacity=5),
        plant("10", "TX", 30.0, -97.0, capacity=20),
    ]
    selected = select_worksites(rows)
    assert len(selected) == 1
    assert selected[0].capacity_mw == 20


def test_same_coordinates_are_one_location() -> None:
    rows = [
        plant("1", "TX", 30.00001, -97.00001),
        plant("2", "TX", 30.00002, -97.00002),
    ]
    assert len(select_worksites(rows)) == 1


def test_small_state_is_not_padded_with_invented_plants() -> None:
    rows = [plant("1", "DC", 38.9, -77.0), plant("2", "DC", 38.8, -77.1)]
    rows.extend(plant(str(index), "CA", 32 + index * 0.5, -120) for index in range(40))
    selected = select_worksites(rows)
    dc = [item for item in selected if item.state == "DC"]
    assert 1 <= len(dc) <= 2
    assert {item.plant_id for item in dc} <= {"1", "2"}


def test_average_is_about_five_and_counts_are_not_flat() -> None:
    rows = []
    sizes = (("CA", 200), ("TX", 80), ("NY", 40), ("WY", 20), ("DC", 15), ("DE", 12))
    for index, (state, count) in enumerate(sizes):
        rows.extend(
            plant(f"{state}-{item}", state, 25 + index + item * 0.05, -120 - item * 0.05)
            for item in range(count)
        )
    selected = select_worksites(rows)
    counts = {}
    for item in selected:
        counts[item.state] = counts.get(item.state, 0) + 1
    average = len(selected) / len(counts)
    assert 4.5 <= average <= 5.5
    assert len(set(counts.values())) > 1
    assert max(counts.values()) > 5
