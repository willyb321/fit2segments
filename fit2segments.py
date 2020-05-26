#!/usr/bin/env python
"""
Parse a list of FIT files and generate the following output files:

- `segments.json`: JSON file containing all segments and timings
- `activities.json`: JSON file containing all activities
- `segmentname_timings.csv`: CSV files containing date, kms, and duration (minutes)
- `segmentname_debug.csv`: CSV file containing detected virtual start and stop points
  (labeled by date), as well as segment reference (labeled w/segment name)
"""


import argparse
import logging
import operator
import re
from datetime import datetime, timedelta
from math import sqrt
from statistics import mean, stdev
from typing import List, Optional, TextIO, Tuple

from dacite import from_dict
from dacite.exceptions import MissingValueError

from fitlib import (
    Activity,
    Matched_track_point,
    Metric,
    Segment,
    Segment_definition,
    Segment_definition_point,
    Track,
    Track_point,
    filename2activityname,
    get_logger,
    get_segment_debug_handler,
    get_segment_tag,
    get_segment_timing_handler,
    load_activities,
    load_file,
    load_segment_definitions,
    load_segments,
    semicircles_to_degrees,
    write_activities,
    write_segments,
)


def parse_args() -> argparse.Namespace:
    """ Call me with args = parse_args() """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )

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


def distance(
    track_point: Track_point, segment_point: Segment_definition_point
) -> float:
    d2_lat = (track_point.position_lat - segment_point.latitude) ** 2
    d2_long = (track_point.position_long - segment_point.longitude) ** 2
    to_return = sqrt(d2_lat + d2_long)

    return to_return


def find_candidates(
    track: List[Track_point], segpoint: Segment_definition_point, threshold: int
) -> List[Matched_track_point]:

    return [
        from_dict(
            data_class=Matched_track_point,
            data={"track_point": track_point, "dist_to_segment": dist, "idx": idx},
        )

        for idx, track_point in enumerate(track)

        if (dist := int(distance(track_point, segpoint))) < threshold
    ]


def compute_metric(
    field_name: str, segment_points: List[Track_point]
) -> Optional[Metric]:

    for sp in segment_points:
        if not hasattr(sp, field_name) or getattr(sp, field_name) is None:
            return None

    ts = [mtp.timestamp for mtp in segment_points]
    durations = [z[1] - z[0] for z in zip(ts, ts[1:])]
    values = [
        value

        for duration, metric in zip(
            durations, [getattr(mtp, field_name) for mtp in segment_points][1:]
        )

        for value in duration.seconds * [metric]
    ]

    if field_name == "enhanced_speed":
        # cf. <https://github.com/pcolby/bipolar/issues/74>
        values = [v * 3.6 for v in values]

    to_return: Metric = from_dict(
        data_class=Metric,
        data={
            "avg": mean(values),
            "upper": max(values),
            "lower": min(values),
            "stdev": stdev(values),
        },
    )

    return to_return


def match(
    track: Track,
    segment_definitions: List[Segment_definition],
    args: argparse.Namespace,
) -> List[Segment]:
    # TODO Autodetect segment_definitions
    # TODO Import segment_definitions
    # TODO Compute exact distances with geopy
    threshold = 5000

    segments_challenged = []

    for segment_definition in segment_definitions:
        logger.debug("Searching for segment_definition %s", segment_definition.name)

        if args.verbose:
            deltas = []

            for idx, track_point in enumerate(track.track_points):
                to_add = (
                    idx,
                    track_point.timestamp,
                    int(distance(track_point, segment_definition.start)),
                    int(distance(track_point, segment_definition.stop)),
                )
                deltas.append(to_add)

            if deltas:
                with open(
                    get_csv_filename(track.name, segment_definition.name), "w"
                ) as f_handler:
                    f_handler.write(
                        "\n".join([",".join([str(x) for x in d]) for d in deltas])
                    )

        if segment_definition.debug:
            segment_debug_handler: TextIO = get_segment_debug_handler(
                segment_definition
            )
        segment_timing_handler: TextIO = get_segment_timing_handler(segment_definition)

        logger.debug("Looking for start points")

        track_points_with_gps_fix = [
            tp for tp in track.track_points if tp.position_long and tp.position_lat
        ]

        # Ignore points without GPS fix yet, if any
        start_candidates = find_candidates(
            track_points_with_gps_fix, segment_definition.start, threshold,
        )

        if not start_candidates:
            logger.debug("None found, segment not started")

            continue

        logger.debug("Looking for stop points")
        stop_candidates = find_candidates(
            track_points_with_gps_fix, segment_definition.stop, threshold
        )

        if not stop_candidates:
            logger.debug("None found, segment not stopped")

            continue

        challenges = get_challenges(start_candidates, stop_candidates)
        # TODO compute any relevant metric
        logger.debug("Found %s attempt(s) for this segment", len(challenges))

        for virtual_start, virtual_stop in challenges:
            if segment_definition.debug:
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
            segment_points = track_points_with_gps_fix[
                virtual_start.idx : virtual_stop.idx + 2
            ]
            segments_challenged.append(
                from_dict(
                    data_class=Segment,
                    data={
                        "activity_name": track.name,
                        "segment_name": segment_definition.name,
                        "segment_uid": segment_definition.uid,
                        "duration": virtual_timing,
                        "start_time": virtual_start.track_point.timestamp,
                        "heart_rate": compute_metric("heart_rate", segment_points),
                        "cadence": compute_metric("cadence", segment_points),
                        "speed": compute_metric("enhanced_speed", segment_points),
                        "temperature": compute_metric("temperature", segment_points),
                    },
                )
            )

            segment_timing_handler.write(
                "%s,%2.2f,%3.2f\n"
                % (track.name, virtual_distance, virtual_timing.total_seconds() / 60)
            )
            logger.warning(
                "%s : %s found %1.2f km / %s",
                track.name,
                segment_definition.name,
                virtual_distance,
                virtual_timing,
            )
            logger.debug(
                "Start: %s\nStop %s",
                virtual_start.track_point,
                virtual_stop.track_point,
            )

        if segment_definition.debug:
            segment_debug_handler.close()

    return segments_challenged


def update_storage(
    segment_definitions: List[Segment_definition],
    activities: List[Activity],
    segments: List[Segment],
    args: argparse.Namespace,
) -> Tuple[List[Activity], List[Segment]]:

    logger.warning("%s segment definitions loaded", len(segment_definitions))
    logger.warning("%s activities loaded", len(activities))
    logger.warning("%s segments loaded", len(segments))

    # FIXME prune missing segment definitions, if flag?

    dump_every = 50

    for idx, filename in enumerate(args.fitfiles):

        # Skip already processed activities

        if [a for a in activities if a.name == filename2activityname(filename)]:
            logger.info("%s already processed, skipping", filename)

            continue
        try:
            track = load_file(filename)
            logger.warning("Loading %s", filename)
        except MissingValueError as e:
            __import__("ipdb").set_trace()
            logger.critical("%s: %s", filename, str(e))

            continue

        # the track has no track_point (HT, disabled GPS),

        if track.gps_available:
            segments_challenged = match(track, segment_definitions, args)
            segments.extend(segments_challenged)
        else:
            logger.info("%s is HT", filename)

        activity = from_dict(
            data_class=Activity,
            data={
                "name": track.name,
                "year": track.track_points[0].timestamp.year,
                "start_time": track.track_points[0].timestamp,
                "duration": track.track_points[-1].timestamp
                - track.track_points[0].timestamp,
            },
        )

        activities.append(activity)

        if idx % dump_every == 0:
            logger.debug("Dumping activites and segments, %s processed", idx)
            write_activities(activities)
            write_segments(segments)

    return (activities, segments)


def main() -> None:
    args = parse_args()

    new_activities, new_segments = update_storage(
        load_segment_definitions(), load_activities(), load_segments(), args
    )

    write_activities(new_activities)
    write_segments(new_segments)


if __name__ == "__main__":
    logger = get_logger("fit2seg")
    main()
    logger.debug("Done")
