from app.workers.datapack import DATAPACK_VERSION, compute_window_metrics, contains_plate_like_keys


def test_compute_window_metrics_schema():
    out = compute_window_metrics(active_tracks=8, avg_compensated_speed=4.5)
    assert set(out.keys()) == {"stopped_ratio", "density_index", "avg_speed_proxy"}
    assert 0.0 <= out["stopped_ratio"] <= 1.0
    assert 0.0 <= out["density_index"] <= 1.0
    assert out["avg_speed_proxy"] >= 0.0


def test_contains_plate_like_keys_detects_forbidden_fields():
    clean_payload = {
        "datapack_version": DATAPACK_VERSION,
        "windows": [{"congestion_score": 22}],
        "privacy": {"contains_identifiers": False},
    }
    assert contains_plate_like_keys(clean_payload) is False

    bad_payload = {"license_plate": "ABC123"}
    assert contains_plate_like_keys(bad_payload) is True
