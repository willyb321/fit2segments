#!/usr/bin/env python
"""
"""

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import requests
import requests_cache
from bs4 import BeautifulSoup

from fitlib import Segment_definition, Segment_definition_point

requests_cache.install_cache(".cache/requests_cache")


def parse_args() -> argparse.Namespace:
    """ Call me with args = parse_args() """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )

    # Positional arguments
    parser.add_argument("strava_segments_files", nargs="+", help="Strava segment files")

    # Boolean
    parser.add_argument("--verbose", "-v", help="Verbose mode", action="store_true")

    args: argparse.Namespace = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

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


def get_segment_start_stops(
    seg_id: int,
) -> Tuple[Segment_definition_point, Segment_definition_point]:
    data_req = requests.get(
        (f"https://www.strava.com/stream/segments/{seg_id}" f"?streams%5B%5D=latlng")
    )
    assert data_req.status_code == 200
    data = data_req.json()

    start = Segment_definition_point(
        altitude=0,
        latitude=data["latlng"][0][0],
        longitude=data["latlng"][0][1],
        tolerance=5,
    )
    stop = Segment_definition_point(
        altitude=0,
        latitude=data["latlng"][-1][0],
        longitude=data["latlng"][-1][1],
        tolerance=5,
    )

    return (start, stop)


def get_segment_public_metadata(seg_id: int) -> Dict[str, Any]:

    metadata_req = requests.get(f"https://www.strava.com/segments/{seg_id}")
    assert metadata_req.status_code == 200
    soup = BeautifulSoup(metadata_req.text, "html.parser")

    name = soup.find(id="js-full-name").text
    stats = [t.text for t in soup.find_all("b", class_="stat-text")]
    assert stats[0].endswith("km")
    assert stats[1].endswith("%")
    assert stats[2].endswith("m")
    assert stats[3].endswith("m")

    distance: float = float(stats[0][:-2])
    avg_grade: float = float(stats[1][:-1])
    lowest: int = int(stats[2][:-1].replace(",", ""))
    highest: int = int(stats[3][:-1].replace(",", ""))
    elevation_difference: int = int(stats[4][:-1].replace(",", ""))
    climb_category: int = int(stats[5])

    to_return = {
        "name": f"{name} ({seg_id})",
        "distance": distance,
        "avg_grade": avg_grade,
        "lowest": lowest,
        "highest": highest,
        "elevation_difference": elevation_difference,
        "climb_category": climb_category,
    }

    return to_return


def import_from_strava(filename: str) -> List[Segment_definition]:
    """docstring for import_from_strava"""
    strava_segments_file: Path = Path(filename)
    assert strava_segments_file.exists()
    with strava_segments_file.open() as f_handler:
        strava_segments: List[Dict[str, Union[str, int]]] = json.load(f_handler)

    # Also supports: streams%5B%5D=distance&streams%5B%5D=altitude&_=1590644676298

    to_return = []

    for strava_segment in strava_segments:
        seg_name: str = str(strava_segment["name"])
        seg_id: int = int(strava_segment["strava_segment_id"])
        logger.warning("Importing segment %s", seg_name)

        start, stop = get_segment_start_stops(seg_id)
        metadata = get_segment_public_metadata(seg_id)
        new_segment_definition: Segment_definition = Segment_definition(
            debug=False, name=metadata["name"], start=start, stop=stop,
        )
        to_return.append(new_segment_definition)

    return to_return


def main(args: argparse.Namespace) -> None:
    imported_segments = []

    for strava_segments_file in args.strava_segments_files:
        imported_segments.extend(import_from_strava(strava_segments_file))

    with open("segment_definitions.json", "w") as f_handler:
        json.dump([asdict(seg) for seg in imported_segments], f_handler, indent=True)


if __name__ == "__main__":
    logger = get_logger(__name__)
    args = parse_args()
    main(args)
    logging.debug("Done")
