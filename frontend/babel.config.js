// Metro already defaults to babel-preset-expo; this file exists so that Jest
// (which has no Metro) transforms the app's TypeScript and React Native's
// Flow-typed sources the same way.
module.exports = function (api) {
  api.cache(true);
  return { presets: ["babel-preset-expo"] };
};
