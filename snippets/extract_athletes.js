// Strava Kudos Tracker — athlete extractor
// 1. Open https://www.strava.com/athletes/YOUR_ID/follows?type=followers
//    or            /follows?type=following
// 2. Scroll to the bottom so every name is loaded into the DOM.
// 3. Paste this snippet into the browser DevTools console.
// 4. Run `kudostracker paste followers` (or `paste following`) in your terminal.

copy(
  [...document.querySelectorAll('a[href^="/athletes/"]')]
    .map(a => {
      const m = a.href.match(/\/athletes\/(\d+)/);
      const name = a.textContent.trim();
      return m && name ? { id: Number(m[1]), name, url: a.href } : null;
    })
    .filter(Boolean)
    .filter((v, i, arr) => arr.findIndex(x => x.id === v.id) === i)
);
console.log("JSON copied to clipboard.");
