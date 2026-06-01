// Strava Kudos Tracker — athlete extractor
// 1. Open https://www.strava.com/athletes/YOUR_ID/follows?type=followers
//    or            /follows?type=following
// 2. Scroll to the bottom so every name is loaded into the DOM.
// 3. Paste this snippet into the browser DevTools console.
// 4. Run `kudostracker paste followers` (or `paste following`) in your terminal.

// Derive the current user's own id from the URL so we exclude it.
const ownId = (location.pathname.match(/\/athletes\/(\d+)/) || [])[1];

copy(
  [...document.querySelectorAll('a[href^="/athletes/"]')]
    .map(a => {
      // Only pure /athletes/{id} links (ignore /athletes/{id}/training, /follows, etc.)
      const m = a.getAttribute('href').match(/^\/athletes\/(\d+)\/?$/);
      const name = a.textContent.trim();
      return m && name ? { id: Number(m[1]), name, url: a.href } : null;
    })
    .filter(Boolean)
    .filter(v => String(v.id) !== ownId)
    .filter((v, i, arr) => arr.findIndex(x => x.id === v.id) === i)
);
console.log("JSON copied to clipboard.");
