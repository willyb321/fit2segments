// Corresponding items
Vue.component("activityItem", {
  props: ["activity"],
  template:
    '<li><a title="Go to activity" @click="renderActivity(activity)">{{ activity.name }}</a></li>',
  methods: {
    renderActivity(activity) {
      this.$root.data_to_render_type = "activity";
      this.$root.data_to_render = activity;
    },
  },
});

Vue.component("segmentDefinitionItem", {
  props: ["segmentDefinition"],
  template:
    '<li><a title="Go to segment" @click="renderSegmentDefinition(segmentDefinition)">{{ segmentDefinition.name }}</a></li>',
  methods: {
    renderSegmentDefinition(segmentDefinition) {
      this.$root.data_to_render_type = "segmentDefinition";
      this.$root.data_to_render = segmentDefinition;
    },
  },
});

Vue.component("segmentInActivityContextItem", {
  props: ["segment"],
  template: `
  <div>
    <h5>
      <a title="Go to segment" @click="renderSegmentDefinition(segment.definition)">
        {{ segment.segment_name }} {{segment.definition.strava_id}}
      </a>
    </h5>
    <table>
    <tr>
      <td>Duration</td>
      <td>{{ segment.duration_str }}</td>
    </tr>
    <tr>
      <td>HR</td>
      <td>{{ segment.heart_rate_str }}</td>
    </tr>
    <tr>
      <td>Cadence</td>
      <td>{{ segment.cadence_str }}</td>
    </tr>
    <tr>
      <td>Speed</td>
      <td>{{ segment.speed_str }}</td>
    </tr>
    <tr>
      <td>Temp.</td>
      <td>{{ segment.temperature_str }}</td>
    </tr>
    <tr>
      <td>AllTime</td>
      <td>{{segment.rankAllTime}}/{{segment.nbAttemptAllTime}}</td>
    </tr>
    <tr>
      <td>ThisYear</td>
      <td>{{segment.rankThisYear}}/{{segment.nbAttemptThisYear}}</td>
    </tr>
    </table>
  </div>
  `,
  methods: {
    renderSegmentDefinition(segmentDefinition) {
      this.$root.data_to_render = segmentDefinition;
      this.$root.data_to_render_type = "segmentDefinition";
    },
  },
});

Vue.component("segmentInDefinitionContextItem", {
  props: ["segment"],
  template: `
    <tr>
      <td>
        <a title="Go to activity" @click="renderActivity(segment.activity)">{{ segment.start_date_str }}</a>
      </td>
      <td>
        {{ segment.duration_str }}
      </td>
      <td>
        {{ segment.heart_rate_str }}
      </td>
      <td>
        {{ segment.cadence_str }}
      </td>
      <td>
        {{ segment.speed_str }}
      </td>
      <td>
        {{ segment.temperature_str }}
      </td>
    </tr>
    `,
  methods: {
    renderActivity(activity) {
      this.$root.data_to_render = activity;
      this.$root.data_to_render_type = "activity";
    },
  },
});

// Convert segments loaded from JSON into proper structure (e.g. time, duration)
const convertLoadedSegment = function convertLoadedSegment(segment) {
  const newStartTime = new Date(null);
  const toReturn = segment;
  newStartTime.setUTCMilliseconds(Date.parse(segment.start_time) + 7200000);
  toReturn.start_time = newStartTime;
  const newDuration = new Date(null);
  newDuration.setSeconds(segment.duration);
  toReturn.duration = newDuration;
  [toReturn.definition] = segment_definitions.filter(
    (sg) => sg.uid === toReturn.segment_uid
  );
  [toReturn.activity] = activities.filter(
    (a) => a.name === toReturn.activity_name
  );

  return toReturn;
};

// Create adequate string representations for rendering a segment
const prepareSegmentRendering = function prepareSegmentRendering(segment) {
  const toReturn = segment;
  toReturn.start_time_str = segment.start_time.toISOString();
  toReturn.start_date_str = toReturn.start_time_str.substr(0, 10);
  toReturn.duration_str = segment.duration.toISOString().substr(11, 8);
  toReturn.year = toReturn.start_time_str.substring(0, 4);

  [
    toReturn.heart_rate_str,
    toReturn.cadence_str,
    toReturn.speed_str,
    toReturn.temperature_str,
  ] = [
    toReturn.heart_rate,
    toReturn.cadence,
    toReturn.speed,
    toReturn.temperature,
  ].map((metric) => {
    if (metric != null) {
      const [avg, stdev, lower, upper] = [
        metric.avg,
        metric.stdev,
        metric.lower,
        metric.upper,
      ].map((v) => (Number.isInteger(v) ? v : v.toFixed(1)));
      return `${avg} ± ${stdev} ∈ [${lower}:${upper}]`;
    }
    return "";
  });

  return toReturn;
};

// Convert activities loaded from JSON into proper structure (e.g. time, duration)
const convertLoadedActivity = function convertLoadedActivity(activity) {
  const newStartTime = new Date(null);
  const toReturn = activity;
  newStartTime.setUTCMilliseconds(Date.parse(activity.start_time) + 7200000);
  toReturn.start_time = newStartTime;
  const newDuration = new Date(null);
  newDuration.setSeconds(activity.duration);
  toReturn.duration = newDuration;
  return toReturn;
};

// Create adequate string representations for rendering a activity
const prepareActivityRendering = function prepareActivityRendering(activity) {
  const toReturn = activity;
  toReturn.start_time_str = activity.start_time.toString();
  toReturn.duration_str = activity.duration.toISOString().substr(11, 8);
  return toReturn;
};

const prepareSegmentDefinitionRendering = async function prepareSegmentDefinitionRendering(
  segmentDefinition
) {
  const stravaSegmentUrl = `https://www.strava.com/stream/segments/${segmentDefinition.strava_id}?streams%5B%5D=latlng`;

  const response = await fetch(stravaSegmentUrl)
    .then((res) => {
      console.log(res);
      return res.json();
    })
    .catch((err) => {
      throw err;
    });
  console.log(reponse);
  toReturn = segmentDefinition;
  toReturn.coordinates = response;
  return toReturn;
};

const app = new Vue({
  el: "#app",

  data: {
    activities: activities
      .filter((a) => a.gps_available)
      .sort((a, b) => Date.parse(b.start_time) - Date.parse(a.start_time))
      .map(convertLoadedActivity)
      .map(prepareActivityRendering),
    segments: segments
      .sort((a, b) => Date.parse(a.duration) - Date.parse(b.duration))
      .map(convertLoadedSegment)
      .map(prepareSegmentRendering),
    segmentDefinitions: segment_definitions,
    // segmentDefinitions: segment_definitions.map(
    //   prepareSegmentDefinitionRendering
    // ),
    data_to_render: "",
    data_to_render_type: "",
    content: "",
  },
  mounted: function mounted() {
    const mymap = L.map("mapid").setView([44.936, 5.041], 12);
    L.tileLayer(
      "https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}",
      {
        attribution:
          'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
        maxZoom: 18,
        id: "mapbox/streets-v11",
        tileSize: 512,
        zoomOffset: -1,
        accessToken:
          "pk.eyJ1IjoiYWhtb3Bob2UiLCJhIjoiY2thenE1amFiMDBqeTJzbXR3eGozZ244dyJ9.vaCiRX2sTWjSgG71qOLhBQ",
      }
    ).addTo(mymap);

    this.$root.data_to_render_type = "activity";
    this.$root.data_to_render = activities[activities.length - 1];
  },
  computed: {
    context() {
      if (this.data_to_render_type === "activity") {
        return this.segments
          .filter(
            (segment) => segment.activity_name === this.data_to_render.name
          )
          .sort((a, b) => Date.parse(a.start_time) - Date.parse(b.start_time))
          .map((targetsegment) => {
            const allTime = this.segments.filter(
              (segment) => segment.segment_uid === targetsegment.segment_uid
            );
            const thisYear = allTime.filter(
              (segment) => segment.year === targetsegment.year
            );

            const toReturn = targetsegment;
            toReturn.rankAllTime = allTime.indexOf(targetsegment);
            toReturn.nbAttemptAllTime = allTime.length;
            [toReturn.bestAllTime] = allTime;
            toReturn.rankThisYear = thisYear.indexOf(targetsegment);
            toReturn.nbAttemptThisYear = thisYear.length;
            [toReturn.bestThisYear] = thisYear;
            return toReturn;
          });
      }
      if (this.data_to_render_type === "segmentDefinition") {
        const { uid } = this.data_to_render;
        return this.segments
          .filter((segment) => segment.segment_uid === uid)
          .concat()
          .sort((a, b) => Date.parse(a.duration) - Date.parse(b.duration));
      }
      return ["unknown"];
    },
  },
});
