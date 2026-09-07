import numpy as np

from backend.vision.automatic_identity import identify_player, parse_school_colors


class SequenceReader:
    def __init__(self, values):
        self.values = iter(values)
    def read(self, crop):
        return next(self.values)


def track(track_id, xs):
    return {"track_id": track_id, "frames": list(range(len(xs))), "positions": [
        {"frame": index, "timestamp_ms": index * 100, "bbox": [x, 0, x + 20, 40], "confidence": .95}
        for index, x in enumerate(xs)
    ]}


def test_school_color_parser_supports_names_and_hex():
    assert parse_school_colors("red, white, #000000") == [(200, 35, 45), (255, 255, 255), (0, 0, 0)]


def test_repeated_target_number_selects_track_automatically():
    red = np.zeros((50, 80, 3), dtype=np.uint8)
    red[:, :] = [45, 35, 200]  # BGR
    tracks = [track(1, [0, 1, 2]), track(2, [30, 31, 32])]
    reader = SequenceReader([
        [("12", .94)], [("12", .91)], [("12", .92)],
        [("24", .92)], [("24", .90)], [("24", .89)],
    ])
    result = identify_player("12", "red, white, black", tracks, {0: red, 1: red, 2: red},
                             reader, min_reads=2)
    assert result["status"] == "identified"
    assert result["selected_track_id"] == 1
    assert result["tracks"][0]["matching_reads"] == 3


def test_ambiguous_or_single_read_requires_confirmation():
    frame = np.full((50, 80, 3), 255, dtype=np.uint8)
    tracks = [track(1, [0]), track(2, [30])]
    reader = SequenceReader([[("12", .8)], [("12", .79)]])
    result = identify_player("12", "white", tracks, {0: frame}, reader, min_reads=2)
    assert result["status"] == "confirmation_required"
    assert result["selected_track_id"] is None
