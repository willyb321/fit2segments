#!/usr/bin/env python
"""
"""

import argparse
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import requests
import requests_cache
from bs4 import BeautifulSoup

from fitlib import Segment_definition, Segment_definition_point, get_logger

requests_cache.install_cache(
    str(Path.home() / ".cache" / "fit2segments" / "requests_cache")
)

headers = {
    "cookie": "explore_activity_type=cycling; G_ENABLED_IDPS=google; _ga=GA1.2.615208174.1605042358; sp=2aa4bf96-50a8-42dd-bc02-355203e01fbb; _strava4_session=1l7jtacu7dh51gkr8mcfg2aogmrc9c4s; ajs_anonymous_id=%22b3b72ac5-7a62-4c74-b7cc-bcdd53836b88%22; _sp_id.f55d=61988c17-863b-41c0-b9cb-1ec43a47f6bf.1607287259.1.1607287383.1607287259.f5c8d595-1214-4aba-9042-dd73a289c8a6; _gid=GA1.2.1038856937.1611197897; iterableEndUserId=wbwilliam7%40gmail.com; iterableEmailCampaignId=1393220; iterableTemplateId=1934428; iterableMessageId=e49f39f0b6a4469c9ea8461344553d04; _sp_ses.047d=*; elevate_daily_connection_done=true; elevate_athlete_update_done=true; fbm_284597785309=base_domain=.www.strava.com; _sp_id.047d=eb14ffe9-6f80-48ea-a580-99567a3b3682.1602189983.45.1611263211.1611203545.3f221abb-04fb-4e7c-ab8e-4ea0f4339271; fbsr_284597785309=HpPGWG7UJ6j6tZFoj7ekjCF3q4sSG55P6kxrJIhd3HQ.eyJ1c2VyX2lkIjoiMzI2NTk5NTk5MzQzMDgyNyIsImNvZGUiOiJBUUJmN2FEbDdyTkxCZVpUWTVqZVV6LXlRZE9VSXJjXzF1NHZvcUVPNFRjbTQ4N2xqdnpOT0VlNkVqQ1J3QXFyY0ZIQ3FQdFd6R0ZOLWJjZmFlVXk1YmtNNkxtX0NWQlhKUU9ncnNqc09MalZDWmo1bE15NVFZQWdkbUxkV25lbjRGc3VKd3BKdk84QUs5Wm91XzlsVlh5Mk9DaUJxS0daR1hmeFRHWGREaU9FaVhvb1lncTNGY1ctSTQzVVNPbUE3eV9zUlBOd3o2M1ZMTmNUbXJBUnNZR1N0ZWFiTFBJLVRVR3lRUUZSSUVQU183Si0zakJpSmdaZnlVcWNhR0Q4VTl6bTdwRml1cV83WnRHS3R4TUZIR0ZaVGxPSmc1cGVZWE42NEZYd3hWOE9pYnVmTHU1MEZlRUhpSFdUbFVDR2owZ3dBMzAyMWVWeHNGV2NQb1dOOUkwNSIsIm9hdXRoX3Rva2VuIjoiRUFBQUFRa05aQWt0MEJBSktaQURXbnlUbnRZTVVqNGVoYjlEbGl1MWtLU3M0d2djUmZyMUd1MmtVaUN3Z2dXVUtuenFlSzdya2lLZlBYVWJJenhMazAyM1N6WW16ZVF1VTNuN3ltU2RiNGFIdlVCV05VbkVFYmNHSjFNTDRYakl1b1dWbXhaQ2NtcVpDTnBJWkM2T1pDQW8zbkdsTDYyVGF4VWQwZ1lCaEdjWkFZWDRXNzdseFhPM3EyUENHa09BSEwxQlIwYVR0a2ZVSjZydzBjNVdKR1FjIiwiYWxnb3JpdGhtIjoiSE1BQy1TSEEyNTYiLCJpc3N1ZWRfYXQiOjE2MTEyNjMyMTJ9"
}


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


def get_segment_start_stops(
    seg_id: int,
) -> Tuple[Segment_definition_point, Segment_definition_point, List[List[float]]]:
    print(seg_id)
    
    data_req = requests.get(
        (f"https://www.strava.com/stream/segments/{seg_id}" f"?streams%5B%5D=latlng"), headers=headers
    )
    # assert data_req.status_code == 200
    print(data_req.text)
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

    return (start, stop, data["latlng"])


def get_segment_public_metadata(seg_id: int) -> Dict[str, Any]:

    metadata_req = requests.get(f"https://www.strava.com/segments/{seg_id}", headers=headers)
    assert metadata_req.status_code == 200
    soup = BeautifulSoup(metadata_req.text, "html.parser")

    strava_name = soup.find(id="js-full-name").text
    name: str = re.sub(r"\W+", " ", strava_name).strip().title()
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
    climb_category: int = int(stats[5] if stats[5] != "" else 0)

    to_return = {
        "name": f"{name}",
        "strava_id": seg_id,
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

        start, stop, latlng = get_segment_start_stops(seg_id)
        metadata = get_segment_public_metadata(seg_id)
        new_segment_definition: Segment_definition = Segment_definition(
            debug=False,
            name=metadata["name"],
            start=start,
            stop=stop,
            strava_id=metadata["strava_id"],
            latlng=latlng,
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
