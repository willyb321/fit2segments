import bz2
import json
import logging
import pickle
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import List, Optional, TextIO, Union

from dacite import Config, from_dict
from fitparse import FitFile

DEFAULT_CACHE_PATH = "./.cache"
DEFAULT_SEGMENT_DEFINITIONS_FILENAME = "segment_definitions.json"
DEFAULT_SEGMENTS_FILENAME = "segments.json"
DEFAULT_ACTIVITIES_FILENAME = "activities.json"

# https://docs.microsoft.com/en-us/previous-versions/windows/embedded/cc510650(v=msdn.10)

SEMICIRCLES_TO_DEGREES: float = 180 / pow(2, 31)
DEGREES_TO_SEMICIRCLES: float = pow(2, 31) / 180


@dataclass
class Activity:
    name: str
    year: int
    start_time: datetime
    duration: timedelta


@dataclass
class Segment:
    activity_name: str
    segment_name: str
    segment_uid: str
    start_time: datetime
    duration: timedelta


@dataclass
class Segment_definition_point:
    latitude: float
    longitude: float
    altitude: float
    tolerance: float


@dataclass
class Segment_definition:
    debug: bool
    name: str
    start: Segment_definition_point
    stop: Segment_definition_point
    uid: str = field(init=False)

    def __post_init__(self) -> None:
        self.uid = sha256(f"{self.name}-{self.start}-{self.stop}".encode()).hexdigest()


@dataclass
class Track_point:
    # TODO could unknown_61 or 66 be accuracy?
    altitude: float
    cadence: Optional[float]
    distance: Optional[float]
    enhanced_altitude: float
    enhanced_speed: Optional[float]
    fractional_cadence: Optional[float]
    heart_rate: Optional[float]
    position_lat: Optional[float]
    position_long: Optional[float]
    speed: Optional[float]
    temperature: float
    timestamp: datetime
    unknown_61: Optional[float]
    unknown_66: Optional[float]


@dataclass
class Matched_track_point:
    track_point: Track_point
    dist_to_segment: float
    category: Optional[str]


@dataclass
class Track:
    name: str
    track_points: List[Track_point]
    gps_available: bool = field(init=False)

    def __post_init__(self) -> None:
        self.gps_available = any(
            [
                hasattr(t, "position_lat")
                and t.position_lat
                and hasattr(t, "position_long")
                and t.position_long

                for t in self.track_points
            ]
        )


def filename2activityname(fitfilename: str) -> str:
    return Path(fitfilename).stem


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
            name=filename2activityname(fitfilename),
            track_points=[
                from_dict(data_class=Track_point, data=data.get_values())

                for data in FitFile(fitfilename).get_messages("record")
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


def get_segment_timing_handler(segment: Segment_definition) -> TextIO:
    debug_file = Path("%s_timings.csv" % get_segment_tag(segment.name))

    if not debug_file.exists():
        to_return = debug_file.open("w")
    else:
        to_return = debug_file.open("a")

    return to_return


def get_segment_debug_handler(segment: Segment_definition) -> TextIO:
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


_TYPEHOOKS = {
    datetime: datetime.fromisoformat,
    timedelta: lambda i: timedelta(seconds=int(i)),
}


def _encode_durations(x: Union[datetime, timedelta]) -> Union[str, float]:

    if isinstance(x, datetime):
        return x.isoformat()
    else:
        return x.total_seconds()


def load_segments(segments_filename: Optional[str] = None,) -> List[Segment]:
    if segments_filename is None:
        segments_filename = DEFAULT_SEGMENTS_FILENAME
    segments_file = Path(segments_filename)
    to_return = []

    if segments_file.exists():
        with segments_file.open() as f_handler:
            # FIXME test hooks
            to_return = [
                from_dict(
                    data_class=Segment, data=data, config=Config(type_hooks=_TYPEHOOKS),
                )

                for data in json.load(f_handler)
            ]

    return to_return


def load_activities(activities_filename: Optional[str] = None,) -> List[Activity]:
    if activities_filename is None:
        activities_filename = DEFAULT_ACTIVITIES_FILENAME
    activities_file = Path(activities_filename)
    to_return = []

    if activities_file.exists():
        with activities_file.open() as f_handler:
            # FIXME test hooks
            to_return = [
                from_dict(
                    data_class=Activity,
                    data=data,
                    config=Config(type_hooks=_TYPEHOOKS),
                )

                for data in json.load(f_handler)
            ]

    return to_return


def write_segments(
    segments: List[Segment], segments_filename: Optional[str] = None,
) -> None:

    if segments_filename is None:
        segments_filename = DEFAULT_SEGMENTS_FILENAME
    segments_file = Path(segments_filename)
    with segments_file.open("w") as f_handler:
        # TODO should encode:
        # - timedelta as total_seconds
        # - datetimes as isoformat or timestamp
        # pb: default= can handle a single function, which should check which one to use
        json.dump(
            [asdict(s) for s in segments],
            f_handler,
            indent=True,
            default=_encode_durations,
        )


def write_activities(
    activities: List[Activity], activities_filename: Optional[str] = None,
) -> None:
    if activities_filename is None:
        activities_filename = DEFAULT_ACTIVITIES_FILENAME
    activitys_file = Path(activities_filename)
    with activitys_file.open("w") as f_handler:
        # TODO should encode:
        # - timedelta as total_seconds
        # - datetimes as isoformat or timestamp
        # pb: default= can handle a single function, which should check which one to use
        json.dump(
            [asdict(a) for a in activities],
            f_handler,
            indent=True,
            default=_encode_durations,
        )


def load_segment_definitions(
    segment_definitions_filename: Optional[str] = None,
) -> List[Segment_definition]:
    """Load segments from input file"""

    def convert_units(segment: Segment_definition) -> Segment_definition:

        old_start = segment.start
        new_start = Segment_definition_point(
            latitude=degrees_to_semicircles(old_start.latitude),
            longitude=degrees_to_semicircles(old_start.longitude),
            altitude=old_start.altitude,
            tolerance=old_start.tolerance,
        )

        old_stop = segment.stop
        new_stop = Segment_definition_point(
            latitude=degrees_to_semicircles(old_stop.latitude),
            longitude=degrees_to_semicircles(old_stop.longitude),
            altitude=old_stop.altitude,
            tolerance=old_stop.tolerance,
        )

        segment.start = new_start
        segment.stop = new_stop

        return segment

    if segment_definitions_filename is None:
        segment_definitions_filename = DEFAULT_SEGMENT_DEFINITIONS_FILENAME
    with open(segment_definitions_filename) as f_handler:
        return [
            convert_units(from_dict(data_class=Segment_definition, data=data))

            for data in json.load(f_handler)
        ]


def get_logger(
    name: str, level: int = logging.WARNING, stderr: bool = True, logfile: bool = False
) -> logging.Logger:
    # Logger name and format
    logger = logging.getLogger(name)
    logger.setLevel(level=level)
    fh_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(filename)s:%(lineno)d(%(process)d) - %(message)s"
    )

    # Stderr logger

    if stderr:
        stderr_logger = logging.StreamHandler()
        stderr_logger.setFormatter(fh_formatter)
        logger.addHandler(stderr_logger)

    # File logger

    if logfile:
        file_logger = logging.FileHandler(f"{name}.log")
        file_logger.setFormatter(fh_formatter)
        logger.addHandler(file_logger)

    return logger
