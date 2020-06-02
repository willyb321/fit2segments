// Corresponding items
Vue.component("activityItem", {
  props: ["activity"],
  template: '<li @click="renderActivity(activity)">{{ activity.name }}</li>',
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
    '<li @click="renderSegmentDefinition(segmentDefinition)">{{ segmentDefinition.name }}</li>',
  methods: {
    renderSegmentDefinition(segmentDefinition) {
      this.$root.data_to_render_type = "segmentDefinition";
      this.$root.data_to_render = segmentDefinition;
    },
  },
});

Vue.component("segmentInActivityContextItem", {
  props: ["segment"],
  template:
    '<li><a @click="renderSegmentDefinition(segment.definition)"> {{ segment.segment_name }}</a> ({{segment.definition.strava_id}}): {{ segment.duration_str }}, {{segment.rankAllTime}}/{{segment.nbAttemptAllTime}}, {{segment.rankThisYear}}/{{segment.nbAttemptThisYear}} </li> ',
  methods: {
    renderSegmentDefinition(segmentDefinition) {
      this.$root.data_to_render_type = "segmentDefinition";
      this.$root.data_to_render = segmentDefinition;
    },
  },
});

Vue.component("segmentInDefinitionContextItem", {
  props: ["segment"],
  template:
    '<li><a @click="renderActivity(segment.activity)">{{ segment.start_date_str }}</a>: {{ segment.duration_str }}</li>',
  methods: {
    renderActivity(activity) {
      this.$root.data_to_render_type = "activity";
      this.$root.data_to_render = activity;
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
    data_to_render: "",
    data_to_render_type: "",
    content: "",
  },
  mounted: function () {
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
        return this.segments.filter((segment) => segment.segment_uid === uid);
      }
      return ["unknown"];
    },
  },
});
