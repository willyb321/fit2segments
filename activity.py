#!/usr/bin/env python
"""
"""

import argparse
import logging
from typing import List

from fitlib import Activity, Metric, Segment, get_logger, load_activities, load_segments


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
    #     help="help message",
    # )

    # Positional arguments
    parser.add_argument(
        "activity_names", nargs="+", help="Activity name, e.g 2020-05-24-10-42-18"
    )

    # Boolean
    parser.add_argument("--verbose", "-v", help="Verbose mode", action="store_true")

    args: argparse.Namespace = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    return args


def render_activity_summary(activity: Activity) -> None:
    """Show activity details"""
    print("*" * 80)
    print(f"Date: {activity.start_time}")
    print(f"Duration: {str(activity.duration)}")
    print("*" * 80)


def render_segment_in_context(segment: Segment, segments: List[Segment]) -> None:
    """Show segment details in context"""

    # Show segment
    print()
    print(f"Segment    : {segment.segment_name}\n")
    print(f"  Duration : {str(segment.duration)}")

    for label, (metric_name, unit) in {
        "  HR": ["heart_rate", "bpm"],
        "  Cadence": ["cadence", "Hz"],
        "  Speed": ["speed", "km/h"],
        "  Temp.": ["temperature", "°C"],
    }.items():
        metric: Metric = getattr(segment, metric_name)

        if metric is None:
            continue
        average = metric.avg
        lower = metric.lower
        upper = metric.upper
        stdev = metric.stdev
        print(
            f"{label:<11}: {average:>5.1f} {unit:<4} ± {stdev:2.1f} "
            f"∈ [{lower:2.0f}:{upper:2.0f}]"
        )

    # Compute context
    all_time = sorted(
        [s for s in segments if s.segment_uid == segment.segment_uid],
        key=lambda s: s.duration,
    )
    this_year = [s for s in all_time if s.start_time.year == segment.start_time.year]

    # Render context
    render = {
        "All-time ": all_time,
        "This year": this_year,
    }

    print()

    for label, data in render.items():

        rank = data.index(segment) + 1

        attempts = len(data)

        # TODO if PR, print delta w/previous PR
        # if rank == 1 and len(data) > 1:
        #     ref = data[1].duration
        #     day = data[1].start_time.date()
        #     delta_pr = segment.duration - ref
        # else:
        ref = data[0].duration
        day = data[0].start_time.date()
        delta_pr = segment.duration - ref

        print(
            f"  {label}: {rank: 3d}/{attempts:>3d}    "
            f"𝚫 PR : {str(delta_pr)} ({str(ref)}, {str(day)})"
        )


def render_activity(
    activity: Activity, activities: List[Activity], segments: List[Segment]
) -> None:
    """docstring for render_activity"""
    matching_activities = [a for a in activities if a.name == activity]
    assert matching_activities, "Activity %s not found!" % activity
    assert len(matching_activities) == 1, "Activity %s found %s times !" % (
        activity,
        len(matching_activities),
    )

    matching_activity = matching_activities.pop()

    render_activity_summary(matching_activity)

    matching_segments = [s for s in segments if s.activity_name == activity]

    for matching_segment in matching_segments:
        render_segment_in_context(matching_segment, segments)


def main(args: argparse.Namespace) -> None:
    # segment_definitions = load_segment_definitions()
    activities = load_activities()
    segments = load_segments()

    for activity in args.activity_names:
        render_activity(activity, activities, segments)
        print()


if __name__ == "__main__":
    logger = get_logger(__name__)
    args = parse_args()
    main(args)
    logging.debug("Done")
