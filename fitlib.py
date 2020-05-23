import bz2
import json
import pickle
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TextIO

from dacite import from_dict
from fitparse import FitFile

DEFAULT_CACHE_PATH = "./.cache"
DEFAULT_SEGMENT_FILENAME = "segments.json"

# https://docs.microsoft.com/en-us/previous-versions/windows/embedded/cc510650(v=msdn.10)

SEMICIRCLES_TO_DEGREES: float = 180 / pow(2, 31)
DEGREES_TO_SEMICIRCLES: float = pow(2, 31) / 180


@dataclass
class Segment_point:
    latitude: float
    longitude: float
    altitude: float
    tolerance: float


@dataclass
class Segment:
    debug: bool
    name: str
    start: Segment_point
    stop: Segment_point


@dataclass
class Track_point:
    # TODO could unknown_61 or 66 be accuracy?
    altitude: float
    cadence: Optional[float]
    distance: float
    enhanced_altitude: float
    enhanced_speed: Optional[float]
    fractional_cadence: Optional[float]
    heart_rate: Optional[float]
    position_lat: float
    position_long: float
    speed: float
    temperature: float
    timestamp: datetime
    unknown_61: Optional[float]
    unknown_66: Optional[float]


@dataclass
class Matched_track_point:
    track_point: Track_point
    dist_to_segment: float
    index_in_track: int
    category: Optional[str]


@dataclass
class Track:
    name: str
    track_points: List[Track_point]


def load_file(fitfilename: str, cache_path_name: Optional[str] = None) -> Track:
    if not cache_path_name:
        cache_path_name = DEFAULT_CACHE_PATH

    cache_path = Path(cache_path_name)

    if not cache_path.is_dir():
        # FIXME  https://docs.python-guide.org/writing/logging/
        # logger.error("tralala")
        pass

    if not cache_path.exists():
        cache_path.mkdir(parents=True)

    cached_file = cache_path / (Path(fitfilename).stem + ".pbz2")

    if not cached_file.exists():
        to_write: Track = Track(
            name=Path(fitfilename).stem,
            track_points=[
                from_dict(data_class=Track_point, data=data.get_values())

                for data in FitFile(fitfilename).get_messages("record")

                if data.get("position_lat") and data.get("position_long")
            ],
        )
        with bz2.BZ2File(cached_file, "wb") as f_handler:
            pickle.dump(to_write, f_handler)

    with bz2.BZ2File(cached_file, "rb") as f_handler:
        to_return: Track = pickle.load(f_handler)

    return to_return


def semicircles_to_degrees(semicircles: int) -> float:
    return semicircles * SEMICIRCLES_TO_DEGREES


def degrees_to_semicircles(degrees: float) -> int:
    return int(degrees * DEGREES_TO_SEMICIRCLES)


def get_segment_tag(segment_name: str) -> str:
    return re.sub(r"\W+", "", segment_name)


def get_segment_timing_handler(segment: Segment) -> TextIO:
    debug_file = Path("%s_timings.csv" % get_segment_tag(segment.name))

    if not debug_file.exists():
        to_return = debug_file.open("w")
    else:
        to_return = debug_file.open("a")

    return to_return


def get_segment_debug_handler(segment: Segment) -> TextIO:
    debug_file = Path("%s_debug_start.csv" % get_segment_tag(segment.name))

    if not debug_file.exists():
        to_return = debug_file.open("w")
        to_return.write(
            "%s,%s,%s-start\n%s,%s,%s-stop\n"
            % (
                semicircles_to_degrees(int(segment.start.longitude)),
                semicircles_to_degrees(int(segment.start.latitude)),
                segment.name,
                semicircles_to_degrees(int(segment.stop.longitude)),
                semicircles_to_degrees(int(segment.stop.latitude)),
                segment.name,
            )
        )

    else:
        to_return = debug_file.open("a")

    return to_return


def load_segments(segment_filename: Optional[str] = None) -> List[Segment]:
    """Load segments from input file"""

    def convert_units(segment: Segment) -> Segment:

        old_start = segment.start
        new_start = Segment_point(
            latitude=degrees_to_semicircles(old_start.latitude),
            longitude=degrees_to_semicircles(old_start.longitude),
            altitude=old_start.altitude,
            tolerance=old_start.tolerance,
        )

        old_stop = segment.stop
        new_stop = Segment_point(
            latitude=degrees_to_semicircles(old_stop.latitude),
            longitude=degrees_to_semicircles(old_stop.longitude),
            altitude=old_stop.altitude,
            tolerance=old_stop.tolerance,
        )

        segment.start = new_start
        segment.stop = new_stop

        return segment

    if segment_filename is None:
        segment_filename = DEFAULT_SEGMENT_FILENAME
    with open(segment_filename) as f_handler:
        return [
            convert_units(from_dict(data_class=Segment, data=data))

            for data in json.load(f_handler)
        ]
