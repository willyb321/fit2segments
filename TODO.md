# Desired UI

- Add interactive mode, with [1-9] to show details about segments and activities

  - initial view: activities
  - select segment to list attempts (name + date)
  - choose attempt to see corresponding activity

- automatic when connecting the Garmin device **or** activity selector
- Single-page rendering (`vuejs`/`d3js`?):

# Activity view

Add:

- distance
- D+
- elapsed time
- moving time
- title
- comments

- average/min/max HR + splits
- average/min/max cadence + splits
- average/min/max speed + splits
- effort score? HR x duration?

# Segment view

Add:

- HR, cadence, speed splits?
- effort score? HR x duration?
- When new (y?)PR, show improvement.

# Segment definition

## Strava import

Available but not used yet, as they are not part of segment definitions (would be to
cumbersome to do that manually):

- distance
- grade
- d+
- cat
- KOM
- wKom

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