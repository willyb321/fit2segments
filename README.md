# Goal

- Detect segments in FIT files, measure distance and duration.

# Usage

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
