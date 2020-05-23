#!/usr/bin/env python

import argparse
import logging
import operator
import re
from datetime import datetime, timedelta
from math import sqrt
from typing import List, Optional, TextIO, Tuple

from dacite import from_dict
from dacite.exceptions import MissingValueError

from fitlib import (
    Matched_track_point,
    Segment,
    Segment_point,
    Track,
    Track_point,
    get_segment_debug_handler,
    get_segment_tag,
    get_segment_timing_handler,
    load_file,
    load_segments,
    semicircles_to_degrees,
)


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
    parser.add_argument("fitfiles", nargs="+", help="FIT files")

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


def create_virtual_point(candidates: List[Matched_track_point]) -> Matched_track_point:
    logger.debug("Create virtual point from %s candidates", len(candidates))
    min_index, min_dist = min(
        enumerate([c.dist_to_segment for c in candidates]), key=operator.itemgetter(1),
    )

    # TODO Interpolate a virtual start point instead of returning the closest one
    logger.debug(
        "Closest distance is %s, at %s",
        min_dist,
        candidates[min_index].track_point.timestamp,
    )

    return candidates[min_index]


def select_virtual_points(
    candidates: List[Matched_track_point], category: Optional[str] = None
) -> List[Matched_track_point]:
    # Group candidates by time, allowing at most `max_delta_time` between them
    max_delta_time = timedelta(seconds=10)
    prev_time: Optional[datetime] = None
    candidate_groups = []
    consecutive_points = []

    for vpoint in sorted(candidates, key=lambda x: x.track_point.timestamp):
        if category:
            vpoint.category = category

        if prev_time:
            dist = vpoint.track_point.timestamp - prev_time

            if dist < max_delta_time:
                consecutive_points.append(vpoint)
            else:
                if consecutive_points:
                    candidate_groups.append(consecutive_points)
                consecutive_points = []
        prev_time = vpoint.track_point.timestamp

    if consecutive_points:
        candidate_groups.append(consecutive_points)
    logger.debug("Track points form %s group(s)", len(candidate_groups))

    virtual_points = [create_virtual_point(group) for group in candidate_groups]

    return virtual_points


def get_challenges(
    start_candidates: List[Matched_track_point],
    stop_candidates: List[Matched_track_point],
) -> List[Tuple[Matched_track_point, Matched_track_point]]:

    virtual_starts = select_virtual_points(start_candidates, category="start")
    virtual_stops = select_virtual_points(stop_candidates, category="stop")

    #  merge start+stop virtual, ordered by time
    ordered = sorted(
        virtual_starts + virtual_stops, key=lambda x: x.track_point.timestamp
    )

    # Search for consecutive start/stop
    to_return = []

    for idx in range(len(ordered) - 1):
        if ordered[idx].category == "start" and ordered[idx + 1].category == "stop":
            to_return.append((ordered[idx], ordered[idx + 1]))

    return to_return


def get_track_tag(track_name: str) -> str:
    return re.sub(r"[^0-9]+", "", track_name)


def get_csv_filename(track_name: str, segment_name: str) -> str:
    segment_tag = get_segment_tag(segment_name)
    track_tag = get_track_tag(track_name)

    return f"./csv/distances.{track_tag}.{segment_tag}.csv"


def distance(track_point: Track_point, segment_point: Segment_point) -> float:
    d2_long = (track_point.position_long - segment_point.longitude) ** 2
    d2_lat = (track_point.position_lat - segment_point.latitude) ** 2
    to_return = sqrt(d2_lat + d2_long)

    return to_return


def match(track: Track, segments: List[Segment], args: argparse.Namespace) -> None:
    # TODO Autodetect segments
    # TODO Import segments
    # TODO Compute exact distances with geopy
    threshold = 5000

    def find_candidates(
        track: List[Track_point], segpoint: Segment_point, threshold: int
    ) -> List[Matched_track_point]:
        return [
            from_dict(
                data_class=Matched_track_point,
                data={
                    "track_point": track_point,
                    "dist_to_segment": dist,
                    "index_in_track": idx,
                },
            )

            for idx, track_point in enumerate(track)

            if (dist := int(distance(track_point, segpoint))) < threshold
        ]

    for segment in segments:
        logger.info("Searching for segment %s", segment.name)

        if args.verbose:
            deltas = []

            for idx, track_point in enumerate(track.track_points):
                to_add = (
                    idx,
                    track_point.timestamp,
                    int(distance(track_point, segment.start)),
                    int(distance(track_point, segment.stop)),
                )
                deltas.append(to_add)

            if deltas:
                with open(get_csv_filename(track.name, segment.name), "w") as f_handler:
                    f_handler.write(
                        "\n".join([",".join([str(x) for x in d]) for d in deltas])
                    )

        if segment.debug:
            segment_debug_handler: TextIO = get_segment_debug_handler(segment)
        segment_timing_handler: TextIO = get_segment_timing_handler(segment)

        logger.debug("Looking for start points")
        start_candidates = find_candidates(track.track_points, segment.start, threshold)

        if not start_candidates:
            logger.debug("None found, segment not started")

            continue

        logger.debug("Looking for stop points")
        stop_candidates = find_candidates(track.track_points, segment.stop, threshold)

        if not stop_candidates:
            logger.debug("None found, segment not stopped")

            continue

        challenges = get_challenges(start_candidates, stop_candidates)
        # TODO compute any relevant metric
        logger.debug("Found %s attempt(s) for this segment", len(challenges))

        for virtual_start, virtual_stop in challenges:
            if segment.debug:
                segment_debug_handler.write(
                    "%s,%s,%s\n%s,%s,%s\n"
                    % (
                        semicircles_to_degrees(
                            int(virtual_start.track_point.position_long)
                        ),
                        semicircles_to_degrees(
                            int(virtual_start.track_point.position_lat)
                        ),
                        track.name,
                        semicircles_to_degrees(
                            int(virtual_stop.track_point.position_long)
                        ),
                        semicircles_to_degrees(
                            int(virtual_stop.track_point.position_lat)
                        ),
                        track.name,
                    )
                )

            virtual_distance = (
                virtual_stop.track_point.distance - virtual_start.track_point.distance
            ) / 1000
            virtual_timing = (
                virtual_stop.track_point.timestamp - virtual_start.track_point.timestamp
            )

            segment_timing_handler.write(
                "%s,%2.2f,%3.2f\n"
                % (track.name, virtual_distance, virtual_timing.total_seconds() / 60)
            )
            logger.warning(
                "%s : %s found %1.2f km / %s",
                track.name,
                segment.name,
                virtual_distance,
                virtual_timing,
            )
            logger.debug(
                "Start: %s\nStop %s",
                virtual_start.track_point,
                virtual_stop.track_point,
            )

        if segment.debug:
            segment_debug_handler.close()


def main() -> None:
    args = parse_args()
    segments = load_segments()
    logger.warning("%s Segments loaded", len(segments))
    # TODO Add metrics: avg heart rate, avg cadence, etc.?

    for filename in args.fitfiles:
        try:
            track = load_file(filename)
        except MissingValueError as e:
            logger.critical("%s: %s", filename, str(e))

            continue

        logger.warning("Loading %s", filename)
        match(track, segments, args)


if __name__ == "__main__":
    logger = get_logger("fit2seg")
    main()
    logger.debug("Done")
