#!/usr/bin/env python

import argparse
import json
import logging
import operator
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import Any, Dict, List, Optional

from dacite import from_dict
from fitparse import FitFile

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
    name: str
    start: Segment_point
    stop: Segment_point


@dataclass
class Track_point:
    # TODO could unkown_61 or 66 be accuracy?
    altitude: float
    cadence: Optional[float]
    distance: float
    enhanced_altitude: float
    enhanced_speed: float
    fractional_cadence: Optional[float]
    heart_rate: float
    position_lat: float
    position_long: float
    speed: float
    temperature: float
    timestamp: datetime
    unknown_61: float
    unknown_66: float


def parse_args() -> argparse.Namespace:
    """ Call me with args = parse_args() """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)

    # Mandatory Flag
    # parser.add_argument(
    #     "--name",
    #     "-shortname",
    #     type=str,
    #     required=True,
    #     default="default",
    #     help="help messaage",
    # )

    # Positional arguments
    # parser.add_argument("name", nargs="+", help="help messaage")  # or * if optional

    # Boolean
    parser.add_argument("--verbose", "-v", help="Verbose mode", action="store_true")

    args: argparse.Namespace = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    return args


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


def semicircles_to_degrees(semicircles: int) -> float:
    return semicircles * SEMICIRCLES_TO_DEGREES


def degrees_to_semicircles(degrees: float) -> int:
    return int(degrees * DEGREES_TO_SEMICIRCLES)


def load_segments() -> List[Segment]:
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

    with open("segments.json") as f_handler:
        return [
            convert_units(from_dict(data_class=Segment, data=data))

            for data in json.load(f_handler)
        ]


def loadfile(fitfilename: str) -> List[Track_point]:
    return [
        from_dict(data_class=Track_point, data=data.get_values())

        for data in FitFile(fitfilename).get_messages("record")
    ]


def distance(track_point: Track_point, segment_point: Segment_point) -> float:
    d2_long = (track_point.position_long - segment_point.longitude) ** 2
    d2_lat = (track_point.position_lat - segment_point.latitude) ** 2
    to_return = sqrt(d2_lat + d2_long)

    return to_return


def match(
    track: List[Track_point], segments: List[Segment], args: argparse.Namespace
) -> None:
    # TODO Segments can be matched from starting point and climbing, since only
    # interested in climing: 1/ Set lowest/starting point only. 2/ Read all
    # trajectories.  3/ For those passing by this lowest point (deltastart), 4/ identify
    # the highest points (min-alt-diff, min-dist-diff): 5/ merge these highest points if
    # delta(x,y,z)<threshold, and 6/ consider these as possible end points. 7/ Then for
    # each pair(lowest, highest) points, 8/ cluster by distances to identify multiple
    # paths, if any (e.g. Barbière -> Tourniol direct vs via petit Tourniol). 9/ Those
    # are segments. 10/ For each of them, the set of tracks in which they can be found
    # can be used to infer the stdev of start point (lower than deltastart), the stdev
    # of end point, the stdev of distance. 11/ Store them in `inferred_segments.json`,
    # that are periodically recomputed to take into account new tracks as they are
    # arred, 12/ and compare each new track fo these inferred_segments.

    # TODO use geopy to compute exact distances for those below a threshold
    # Distance in semicircles for now, but bad since:
    # Length in meters of 1° of latitude = always 111.32 km
    # Length in meters of 1° of longitude = 40075 km * cos( latitude ) / 360

    threshold = 5000

    def find_candidates(
        track: List[Track_point], segpoint: Segment_point, threshold: int
    ) -> List[Dict[str, Any]]:
        return sorted(
            [
                {
                    "track_point": track_point,
                    "dist_to_segment": dist,
                    "index_in_track": idx,
                }

                for idx, track_point in enumerate(track)

                if (dist := int(distance(track_point, segpoint))) < threshold
            ],
            key=lambda x: x["dist_to_segment"],
        )[:3]

    for segment in segments[:1]:
        logger.warning("Look for %s", segment.name)

        start_candidates = find_candidates(track, segment.start, threshold)
        stop_candidates = find_candidates(track, segment.stop, threshold)

        if args.verbose:
            deltas = []

            for idx, track_point in enumerate(track):
                to_add = (
                    idx,
                    int(distance(track_point, segment.start)),
                    int(distance(track_point, segment.stop)),
                )
                deltas.append(to_add)
            with open(f"distances.{segment.name}.csv", "w") as f_handler:
                f_handler.write(
                    "\n".join([",".join([str(x) for x in d]) for d in deltas])
                )

        # FIXME Select best candidate: chimeric point, interpolated from candidates?
        start_point = start_candidates[0]
        stop_point = stop_candidates[0]

        logger.warning(
            "%s found %1.2f km / %s",
            segment.name,
            (stop_point["track_point"].distance - start_point["track_point"].distance)
            / 1000,
            stop_point["track_point"].timestamp - start_point["track_point"].timestamp,
        )
        logger.debug(
            "Start: %s\nStop %s", start_point["track_point"], stop_point["track_point"]
        )


def main() -> None:
    args = parse_args()
    segments = load_segments()
    logger.warning("%s Segments loaded", len(segments))
    track = loadfile("2020-05-21-08-11-47.fit")
    match(track, segments, args)
    # FIXME match track points with segment start/stop
    pass


if __name__ == "__main__":
    logger = get_logger("fit2seg")
    main()
    logging.debug("Done")
