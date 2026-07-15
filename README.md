# BathroomReport

**BathroomReport** is a community-rated bathroom finder. Currently featuring Stewart's Shops
across New York and Vermont, with the app structured so additional chains can be added later
without another rebrand.

Live site: https://bathroomreport.app

## Files
- `index.html` — page structure
- `styles.css` — visual styles
- `locations.js` — Stewart's location data
- `firebase.js` — Firebase initialization
- `app.js` — map, ratings, Bathroom Now, amenities, condition reports, sorting, achievements, Bathroom Passport
- `manifest.webmanifest` — PWA metadata
- `sw.js` — service worker (offline shell caching)
- `robots.txt` / `sitemap.xml` — search engine metadata

## Firestore collections
`aggregates`, `votes`, `tips`, `activity`, `reports`, `missingReports`, `blockedDevices`,
`displayNames`, `nameReports`, `leaderboardBlocklist`, `checkins`, `achievements`,
`conditionReports`. Firestore rules use a single wildcard rule
(`match /{document=**} { allow read, write: if true; }`) covering all current and future
collections, so no rule updates are needed when adding new features.

## Brand vs. content
BathroomReport is the product. Stewart's Shops is the first supported chain (content, not the
brand). Anonymous visitors can use nearly the entire app — logging in unlocks personalization
(Bathroom Passport, Achievements, Leaderboard participation, cross-device sync), not basic
functionality.
