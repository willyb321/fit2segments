## Urgent

Update existing timings, don't recompute everything + use multiprocessing:

- Each segment definition is internally identified by a hash taking into account the
  name of the segment, and its start and stop coordinates and tolerance.
- The list of processed segments should be kept for each activity, e.g. in a
  "non-matching" list, so thatI know it's not worth recomputing them, and focus on those
  that have not yet been computed.
- FIT files should be ignored unless they are missing in `activities.json` and/or

# Desired UI

## Segments

- Add CoteBlanche
- add others from Strava (My segments)/ export ?
- When new (y?)PR, show improvement.

Command-line or single-page rendering (`vuejs`/`d3js`?):

## Activity viewer

- automatic when connecting the Garmin device **or** activity selector
- show activity:
  - average/min/max HR + splits
  - average/min/max cadence + splits
  - average/min/max speed + splits
  - effort score? HR x duration?
- for each segments found, show:
  - HR, cadence, speed splits?
  - effort score? HR x duration?

## Segment viewer

## Interactions

- select segment to list attempts (name + date)
- choose attempt to see corresponding activity

# Processing

## Segments comparison and detection accuracy

- **Interpolate** a virtual start point instead of returning the closest one
- **Import segments**: from Strava?
- **Autodetect segments**: Segments can be matched from starting point and climbing,
  since only interested in climing: 1/ Set lowest/starting point only. 2/ Read all
  trajectories. 3/ For those passing by this lowest point (deltastart), 4/ identify the
  highest points (min-alt-diff, min-dist-diff): 5/ merge these highest points if
  delta(x,y,z)<threshold, and 6/ consider these as possible end points. 7/ Then for each
  pair(lowest, highest) points, 8/ cluster by distances to identify multiple paths, if
  any (e.g. Barbière -> Tourniol direct vs via petit Tourniol). 9/ Those are segments.
  10/ For each of them, the set of tracks in which they can be found can be used to
  infer the stdev of start point (lower than deltastart), the stdev of end point, the
  stdev of distance. 11/ Store them in `inferred_segments.json`, that are periodically
  recomputed to take into account new tracks as they are arred, 12/ and compare each new
  track fo these inferred_segments.
- **Compute exact distances** with Geopy for those below a semicircles threshold:
  Distance in semicircles for now, but bad since: Length in meters of 1° of latitude =
  always 111.32 km Length in meters of 1° of longitude = 40075 km \* cos( latitude ) /
  360

## Note

- Could unknown_61 or 66 in Garmin FIT file be accuracy?
