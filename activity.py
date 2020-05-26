#!/usr/bin/env python
"""
"""

import argparse
import logging
from typing import List

from fitlib import Activity, Segment, get_logger, load_activities, load_segments


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
    print(f"Name     : {segment.segment_name}")
    print(f"Duration : {str(segment.duration)}")

    # Show segment context
    all_time = sorted(
        [s for s in segments if s.segment_uid == segment.segment_uid],
        key=lambda s: s.duration,
    )

    all_time_rank = all_time.index(segment) + 1
    all_time_delta_pr = segment.duration - all_time[0].duration
    print(
        f"  Rank : {all_time_rank: 4d}    "
        f"𝚫 PR : {str(all_time_delta_pr)} ({str(all_time[0].duration)})"
    )

    this_year = [s for s in all_time if s.start_time.year == segment.start_time.year]
    this_year_rank = this_year.index(segment) + 1
    this_year_delta_pr = segment.duration - this_year[0].duration
    print(
        f"  yRank: {this_year_rank: 4d}    "
        f"𝚫 yPR: {str(this_year_delta_pr)} ({str(this_year[0].duration)})"
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
