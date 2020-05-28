# Goal

- Detect segments in FIT files, measure distance and duration.

# Usage

First, you need to create a file containing the definitions of your segments. You can
either create it manually (eg. with [GPXSee](https://www.gpxsee.org/)) and save it as
`segment_definitions.json`, or import strava segments with `import_strava_segments.py`
(in this case, the list of segments to import should be defined in
`strava_segments.json`).

Once you have the `segment_definitions.json` file and your FIT files, you can:

- compute segments with `fit2segments.py`: `usage: fit2segments.py [-h] [--verbose] fitfiles [fitfiles ...]`
- view activity with `activity.py`

# Output

# How it works

- Load segments definitions from `segment_definitions.json`
- For each FIT file, load track points
- Match the segment, compute distance and duration
- Update `activities.json` and `segments.json`

# Note

- Reading FIT files is slow. Once read, they are bz2's pickle'd in `.cache`
  directory.
