from app.services.data_product import build_marketplace_payload, hash_payload


def test_hash_payload_is_deterministic_for_same_payload():
    payload = {
        "a": 1,
        "b": {"x": 2, "y": [3, 4]},
    }
    assert hash_payload(payload) == hash_payload({"b": {"y": [3, 4], "x": 2}, "a": 1})


def test_marketplace_payload_shape():
    payload = build_marketplace_payload(
        job_id=12,
        filename="video.mp4",
        duration_s=15.423,
        analytics_windows=[{"t_start": 0, "t_end": 5, "congestion_score": 55.0}],
        event_counts={"cut_in": 2},
        class_counts={"car": 10},
    )
    assert payload["job_id"] == 12
    assert payload["aggregates"]["event_counts"]["cut_in"] == 2
    assert payload["privacy"]["contains_identifiers"] is False
