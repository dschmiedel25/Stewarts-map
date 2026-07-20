#!/bin/bash
set -e
echo "── Bathroom Report: weekly bake ──"
node fetch-and-bake.js
if ls baked/*-locations.js >/dev/null 2>&1; then
  cp baked/*-locations.js .
else
  echo "Nothing baked. Done."; exit 0
fi
if git status --porcelain | grep -qi "serviceAccountKey\|overrides.json"; then
  echo ""; echo "🛑 STOP: a secret file is staged. Not committing."; exit 1
fi
git add -A
git commit -m "Weekly bake of location overrides"
git push
echo ""; echo "✅ Baked, committed, pushed."
echo "   Next: confirm on live app, then delete baked overrides by hand in Firebase Console."
