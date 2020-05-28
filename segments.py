#!/usr/bin/env python
"""
"""

import argparse
import logging
from typing import List

from fitlib import (
    Segment,
    Segment_definition,
    get_logger,
    load_segment_definitions,
    load_segments,
)


def parse_args() -> argparse.Namespace:
    """ Call me with args = parse_args() """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )

    # Positional arguments
    parser.add_argument("seg_ids", nargs="+", help="Segment IDs")

    # Boolean
    parser.add_argument("--verbose", "-v", help="Verbose mode", action="store_true")

    args: argparse.Namespace = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    return args


def render_segment_summary(segment_definition: Segment_definition) -> None:
    print(segment_definition.name)


def render_segment_in_context(rank: int, segment: Segment) -> None:
    duration = str(segment.duration)
    start_time = str(segment.start_time.date())
    temp = segment.temperature.avg

    # Heart rate
    hr = segment.heart_rate
    hr_str = " " * 24

    if hr:
        hr_str = f"{hr.avg:<5.1f} ± {hr.stdev:>4.1f} ∈ [{hr.lower:>3}:{hr.upper:>3}]"

    # Cadence rate
    cad = segment.cadence
    cad_str = " " * 23

    if cad:
        cad_str = (
            f"{cad.avg:<4.1f} ± {cad.stdev:>4.1f} ∈ [{cad.lower:>3}:{cad.upper:>3}]"
        )

    # Cadence rate
    speed = segment.speed
    speed_str = " " * 24

    if speed:
        speed_str = (
            f"{speed.avg:<4.1f} ± {speed.stdev:>3.1f} ∈"
            f" [{speed.lower:>4.1f}:{speed.upper:>4.1f}]"
        )

    # f"{label:<11}: {average:>5.1f} {unit:<4} ± {stdev:2.1f} "
    # f"∈ [{lower:2.0f}:{upper:2.0f}]"
    print(
        (
            f"{rank:<5} "
            f"{duration:<10} "
            f"{start_time:<10}  "
            f"{temp:>3.0f}  "
            f"{hr_str}  "
            f"{cad_str}  "
            f"{speed_str}  "
        )
    )


def render_segment(
    segment_uid: str,
    segments: List[Segment],
    segment_definitions: List[Segment_definition],
) -> None:
    """docstring for render_segment"""
    matching_segment_definitions = [
        s for s in segment_definitions if s.uid == segment_uid
    ]
    assert matching_segment_definitions, "Segment %s not found!" % segment_uid
    assert len(matching_segment_definitions) == 1, "segment_uid %s found %s times !" % (
        segment_uid,
        len(matching_segment_definitions),
    )

    matching_segment_definition = matching_segment_definitions[0]

    matching_segments = sorted(
        [s for s in segments if s.segment_uid == segment_uid], key=lambda x: x.duration,
    )
    print("*" * 80)
    render_segment_summary(matching_segment_definition)

    print("Found %s attempts" % len(matching_segments))
    print("*" * 80)
    print()
    print(
        "Rank  Time       -- Date --   °C  ------- Heart rate -----  "
        "------- Cadence -------  "
        "------- Speed ----------"
    )

    for idx, matching_segment in enumerate(matching_segments):
        render_segment_in_context(idx + 1, matching_segment)


def main(args: argparse.Namespace) -> None:

    segment_definitions = load_segment_definitions()
    segments = load_segments()

    for seg_id in args.seg_ids:
        render_segment(seg_id, segments, segment_definitions)


if __name__ == "__main__":
    logger = get_logger(__name__)
    args = parse_args()
    main(args)
    logging.debug("Done")
