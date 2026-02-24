from dataclasses import dataclass


@dataclass
class LaneEstimate:
    confidence: float
    metadata: dict


class LaneDetector:
    """Phase-2 extension point for lane segmentation/understanding."""

    def infer(self, frame) -> LaneEstimate:
        return LaneEstimate(confidence=0.0, metadata={"status": "not_implemented"})
