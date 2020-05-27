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
from typing import List, Optional, TextIO, Tuple, Union

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
    assert track_point.position_lat
    assert track_point.position_long
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

        track_points_with_gps_fix = [
            tp for tp in track.track_points if tp.position_long and tp.position_lat
        ]

        if args.verbose:
            deltas = []

            for idx, track_point in enumerate(track_points_with_gps_fix):
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
        logger.debug("Found %s attempt(s) for this segment", len(challenges))

        for virtual_start, virtual_stop in challenges:

            # Make sure all coordinates, distances, etc. are correct
            assert virtual_start.track_point.position_long
            assert virtual_start.track_point.position_lat
            assert virtual_start.track_point.distance
            assert virtual_stop.track_point.position_long
            assert virtual_stop.track_point.position_lat
            assert virtual_stop.track_point.distance

            if segment_definition.debug:
                segment_debug_handler.write(
                    "%s,%s,%s\n%s,%s,%s\n"
                    % (
                        semicircles_to_degrees(
                            round(virtual_start.track_point.position_long)
                        ),
                        semicircles_to_degrees(
                            round(virtual_start.track_point.position_lat)
                        ),
                        track.name,
                        semicircles_to_degrees(
                            round(virtual_stop.track_point.position_long)
                        ),
                        semicircles_to_degrees(
                            round(virtual_stop.track_point.position_lat)
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

    # Remove undefined segments
    segments = [
        seg

        for seg in segments

        if seg.segment_uid in [sd.uid for sd in segment_definitions]
    ]

    dump_every: int = 50

    for idx, filename in enumerate(args.fitfiles):

        # First, we need to check whether the activity has already already been
        # processed, and if it's the case, if new segment definitions have been added
        # since this previous processing.

        matching_activities = [
            a for a in activities if a.name == filename2activityname(filename)
        ]
        assert len(matching_activities) == 0 or len(matching_activities) == 1
        matching_activity: Union[Activity, None] = None

        # `segments_definitions_to_search` will contain only the segment definitions
        # that have to be searched for this activity, ie. all of them is the activity is
        # new, or only new/updates ones if it has been processed previously

        segments_definitions_to_search: Union[List[Segment_definition], None] = None

        # If it's a known activity, first check whether the GPS was enabled: if it's not
        # the case, there's no need to search for segment definitions. If the GPS was
        # enabled, then we can safely ignore segment definitions the `uid` of which,
        # which is a hash, were already matched.

        if matching_activities:
            matching_activity = matching_activities[0]

            # Don't search for segment definitions if no GPS is available

            if not matching_activity.gps_available:
                logger.debug("%s has no GPS records", filename)

                continue

            # get the list of segment definitions the hash of which is not found in this
            # known activity

            segments_definitions_to_search = [
                seg

                for seg in segment_definitions

                if seg.uid not in matching_activity.matched_against_segments
            ]

            # Don't search for segment definitions if there's no new ones

            if not segments_definitions_to_search:
                logger.debug(
                    "%s already searched for %s segments",
                    filename,
                    len(segment_definitions),
                )

                continue

        else:
            # If the activity is new, search for all segments
            segments_definitions_to_search = segment_definitions

        # Here, either the activity is new, or it's known and only a few segments have
        # to be searched for. We need to load the file, hoping the hit the cache since
        # parsing FIT files takes time.

        try:
            track = load_file(filename)
            logger.warning("Loading %s", filename)
        except MissingValueError as e:
            __import__("ipdb").set_trace()
            logger.critical("%s: %s", filename, str(e))

            continue

        # If the track has track_point coordinates, we can search for segments. If it
        # has none (hometrainer or manually added activity), then we don't need to and
        # can just add the activity as is.

        if track.gps_available:
            segments_challenged = match(track, segments_definitions_to_search, args)
            segments.extend(segments_challenged)
        else:
            logger.info("%s is HT", filename)

        # Build the activity dataclass
        activity = from_dict(
            data_class=Activity,
            data={
                "name": track.name,
                "year": track.track_points[0].timestamp.year,
                "start_time": track.track_points[0].timestamp,
                "duration": track.track_points[-1].timestamp
                - track.track_points[0].timestamp,
                "matched_against_segments": [s.uid for s in segment_definitions],
                "gps_available": track.gps_available,
            },
        )

        # If the activity was previously known, but new segments had to be matched, the
        # previous copy must be removed to avoid duplicates

        if matching_activity:
            activities.remove(matching_activity)

        # Add the new (or updated) activity
        activities.append(activity)

        # Dump from time to time, just in case it crashes, to avoid recomputing
        # everything

        if idx % dump_every == 0 and idx != 0:
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
