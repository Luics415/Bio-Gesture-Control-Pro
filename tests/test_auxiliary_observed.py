"""Anonymous still-image hand landmarks, plus transformations; no image/OS I/O."""

from dataclasses import replace
import json
import math
from pathlib import Path

import pytest

from biogesture.auxiliary import AuxiliaryGestureEngine
from biogesture.gestures import GestureEngine, HandGeometry
from biogesture.models import HandSample, Landmark
from biogesture.settings import Settings
from tests.test_auxiliary_scroll import l_hand, l_frames
from tests.test_gestures import hand


FIXTURE = json.loads((Path(__file__).parent / "fixtures/auxiliary_observed_hands.json").read_text(encoding="utf-8"))
OBSERVED = {
    entry["name"]: HandSample(10, tuple(Landmark(*point) for point in entry["landmarks"]),
                              FIXTURE["width"], FIXTURE["height"], entry["handedness"], entry["confidence"])
    for entry in FIXTURE["hands"]
}


def old_l_acceptance(geometry):
    """The strict dev.5 predicate, retained here to explain actual regressions."""
    if not geometry.thumb_extended or geometry.extended != (True, False, False, False):
        return False
    p = geometry.points
    if any(math.dist(p[0], p[base + 3]) > math.dist(p[0], p[base + 1]) * 1.05 for base in (9, 13, 17)):
        return False
    thumb = tuple(b - a for a, b in zip(p[2], p[4]))
    index = tuple(b - a for a, b in zip(p[5], p[8]))
    angle = math.degrees(math.acos(max(-1, min(1, sum(a*b for a, b in zip(thumb, index))
                                             / (math.hypot(*thumb) * math.hypot(*index))))))
    return 60 <= angle <= 120 and geometry.distance(4, 8) >= .7


def transformed(sample, *, rotation=0, mirror=False, size=1, depth=1, width=640, height=480, center_y=.6):
    """Preserve image-plane shape across scale, translation, mirror and aspect."""
    cx = sum(sample.landmarks[i].x for i in (0, 5, 9, 13, 17)) / 5 * sample.width
    cy = sum(sample.landmarks[i].y for i in (0, 5, 9, 13, 17)) / 5 * sample.height
    angle = math.radians(rotation)
    points = []
    for point in sample.landmarks:
        x, y = (point.x * sample.width - cx) * (-1 if mirror else 1), point.y * sample.height - cy
        points.append(Landmark(.5 + size * (x * math.cos(angle) - y * math.sin(angle)) / width,
                               center_y + size * (x * math.sin(angle) + y * math.cos(angle)) / height,
                               point.z * sample.width * size * depth / width))
    return replace(sample, landmarks=tuple(points), width=width, height=height)


@pytest.mark.parametrize("entry", FIXTURE["hands"], ids=lambda entry: entry["name"])
def test_observed_l_is_accepted_and_all_three_observed_open_palms_are_rejected(entry):
    geometry = HandGeometry(OBSERVED[entry["name"]])
    assert old_l_acceptance(geometry) is entry["expected_l"]
    assert AuxiliaryGestureEngine._is_l_pose(geometry) is entry["expected_l"]


@pytest.mark.parametrize("fps", [15, 30])
def test_actual_l_near_neutral_has_a_prompt_first_step_not_a_minutes_long_delay(fps):
    observed = OBSERVED["natural_l"]
    center_y = sum(observed.landmarks[i].y for i in (0, 5, 9, 13, 17)) / 5
    assert .55 < center_y < .551
    old_rate = 6 * (center_y - .55) / .45
    assert 1 / old_rate > 250  # Actual cause: the original L was already accepted.
    engine = AuxiliaryGestureEngine(Settings(detection_fps=fps))
    first_step = None
    for frame in range(fps * 2 + 1):
        now = 10 + frame / fps
        events = engine.update(replace(observed, timestamp=now), now)
        assert all(event.kind == "scroll" and event.value < 0 for event in events)
        if events and first_step is None:
            first_step = now - 10
    assert .45 <= first_step <= 1.2


@pytest.mark.parametrize("rotation", [-70, 0, 65])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("depth", [.5, 1, 1.8])
@pytest.mark.parametrize(("size", "width", "height"), [(.7, 640, 480), (1, 1280, 720), (1.3, 480, 640)])
def test_observed_l_keeps_its_meaning_under_image_and_depth_variations(rotation, mirror, depth, size, width, height):
    sample = transformed(OBSERVED["natural_l"], rotation=rotation, mirror=mirror, depth=depth,
                         size=size, width=width, height=height)
    assert AuxiliaryGestureEngine._is_l_pose(HandGeometry(sample, mirror=mirror))


def test_depth_estimate_cannot_turn_a_clear_visible_l_into_an_acute_angle_rejection():
    sample = transformed(OBSERVED["natural_l"], depth=1.8)
    geometry = HandGeometry(sample)
    assert not old_l_acceptance(geometry)
    assert AuxiliaryGestureEngine._is_l_pose(geometry)


@pytest.mark.parametrize("changed_joint", ["index", "thumb"])
def test_slightly_curved_natural_index_or_thumb_does_not_require_perfect_extension(changed_joint):
    sample = l_hand()
    points = list(sample.landmarks)
    if changed_joint == "index":
        for point in (7, 8):
            points[point] = replace(points[point], x=points[point].x + 20 / sample.width)
    else:
        points[3] = replace(points[3], y=points[3].y + 10 / sample.height)
    geometry = HandGeometry(replace(sample, landmarks=tuple(points)))
    assert not old_l_acceptance(geometry)
    assert AuxiliaryGestureEngine._is_l_pose(geometry)


@pytest.mark.parametrize("name", ["open_palm_beside_l", "open_palm_a", "open_palm_b"])
@pytest.mark.parametrize("rotation", [-70, 0, 65])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("depth", [.5, 1.8])
def test_tolerant_l_still_rejects_observed_open_palms_under_the_same_variations(name, rotation, mirror, depth):
    sample = transformed(OBSERVED[name], rotation=rotation, mirror=mirror, depth=depth)
    assert not AuxiliaryGestureEngine._is_l_pose(HandGeometry(sample, mirror=mirror))


@pytest.mark.parametrize("base", [9, 13, 17])
def test_l_with_an_extra_extended_finger_is_not_a_scroll_pose(base):
    sample = l_hand()
    points = list(sample.landmarks)
    x, y, z = points[base].x, points[base].y, points[base].z
    for offset, dy in enumerate((35, 63, 88), 1):
        points[base + offset] = Landmark(x, y - dy / sample.height, z)
    assert not AuxiliaryGestureEngine._is_l_pose(HandGeometry(replace(sample, landmarks=tuple(points))))


@pytest.mark.parametrize("center_y", [.449, .551, .42, .58])
def test_default_rate_is_responsive_outside_neutral_without_changing_its_boundaries(center_y):
    engine = AuxiliaryGestureEngine(Settings())
    events = l_frames(engine, duration=1.2, center_y=center_y)
    direction = 1 if center_y < .5 else -1
    assert events and all(event.kind == "scroll" and event.value * direction > 0 for event in events)


def test_small_alternating_neutral_boundary_noise_does_not_build_up_a_wheel_step():
    engine = AuxiliaryGestureEngine(Settings())
    for frame in range(120):
        now = 10 + frame / 30
        sample = l_hand(now, center_y=.55 + (.0005 if frame % 2 else -.0005))
        assert not engine.update(sample, now)


def test_observed_auxiliary_replays_leave_every_primary_output_unchanged():
    settings = Settings(start_paused=False)
    primary, baseline = GestureEngine(settings), GestureEngine(replace(settings))
    auxiliary = AuxiliaryGestureEngine(settings)
    for frame in range(120):
        now = 10 + frame / 30
        pose = "pointer" if frame < 20 or frame >= 75 else "pinch" if frame < 55 else "right"
        main = hand(pose, now, dx=frame / 3)
        auxiliary.update(replace(OBSERVED["natural_l"], timestamp=now), now)
        assert primary.update(main, now) == baseline.update(main, now)
