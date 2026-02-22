from app.ml.heuristics import cut_in_confidence, close_following_confidence, congestion_score


def test_cut_in_confidence_high():
    pts = [
        {"xc": 100, "area": 1000, "area_ratio": 0.01, "t": 0.0},
        {"xc": 220, "area": 1500, "area_ratio": 0.02, "t": 0.5},
        {"xc": 350, "area": 2200, "area_ratio": 0.04, "t": 1.0},
    ]
    assert cut_in_confidence(pts, 1000) > 0.5


def test_close_following_confidence_duration():
    pts = [{"xc": 500, "area": 5000, "area_ratio": 0.1, "t": i} for i in [0.0, 1.0, 2.5, 3.0]]
    assert close_following_confidence(pts, 1000) > 0


def test_congestion_score_bounds():
    score = congestion_score(18, avg_compensated_speed=2, stopped_ratio=0.7, density_index=0.9)
    assert 0 <= score <= 100


def test_congestion_score_monotonicity():
    freer = congestion_score(4, avg_compensated_speed=6.0, stopped_ratio=0.1, density_index=0.2)
    congested = congestion_score(18, avg_compensated_speed=0.8, stopped_ratio=0.9, density_index=0.9)
    assert congested > freer
