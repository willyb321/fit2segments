# Goal

- Detect segments in FIT files, measure distance and duration.

# Usage

`usage: fit2segments.py [-h] [--verbose] fitfiles [fitfiles ...]`\_

# Output

- `segmentname_timings.csv`: CSV files containing date, kms, and duration (minutes)
- `segmentname_debug.csv`: CSV file containing detected virtual start and stop points
  (labeled by date), as well as segment reference (labeled w/segment name)

# How it works

- Load segments from `segments.json`
- For each FIT file, load track points
- Match the segment, compute distance and duration

# Note

- Reading FIT files is slow. Once read, they are bz2's pickle'd in `.cache`
  directory.
