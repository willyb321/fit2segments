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

// Convert segments loaded from JSON into proper structure (e.g. time, duration)
const convertLoadedSegment = function convertLoadedSegment(segment) {
  const newStartTime = new Date(null);
  const toReturn = segment;
  newStartTime.setUTCMilliseconds(Date.parse(segment.start_time) + 7200000);
  toReturn.start_time = newStartTime;
  const newDuration = new Date(null);
  newDuration.setSeconds(segment.duration);
  toReturn.duration = newDuration;
  return toReturn;
};

// Create adequate string representations for rendering a segment
const prepareSegmentRendering = function prepareSegmentRendering(segment) {
  const toReturn = segment;
  toReturn.start_time_str = segment.start_time.toISOString().substr(0, 10);
  toReturn.duration_str = segment.duration.toISOString().substr(11, 8);
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
  computed: {
    context() {
      if (this.data_to_render_type === "activity") {
        const { name } = this.data_to_render;
        return this.segments
          .filter((segment) => segment.activity_name === name)
          .sort((a, b) => Date.parse(a.start_time) - Date.parse(b.start_time));
      }
      if (this.data_to_render_type === "segmentDefinition") {
        const { uid } = this.data_to_render;
        return this.segments.filter((segment) => segment.segment_uid === uid);
      }
      return ["unknown"];
    },
  },
});
