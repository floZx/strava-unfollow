# kudostracker

Find Strava followers who never give you kudos, and accounts you follow that don't follow back.

## Install

```bash
git clone <this repo>
cd strava-unfollow
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## One-time setup — Strava OAuth app

1. Go to https://www.strava.com/settings/api and create an app.
2. Set the Authorization Callback Domain to `localhost`.
3. Note your **Client ID** and **Client Secret**.

```bash
export STRAVA_CLIENT_ID=12345
export STRAVA_CLIENT_SECRET=your_secret
kudostracker auth
```

A browser window opens. Approve, and the tokens land in `data/tokens.json` (chmod 600).

## Workflow

```bash
# 1. Export your followers and following lists (manual — see below)
kudostracker paste followers
kudostracker paste following

# 2. Pull activities + kudoers from the Strava API (12 last months)
kudostracker sync

# 3. Generate the report
kudostracker report
open data/report.md
```

### Exporting followers / following

The Strava API doesn't expose your follower lists, so the export is manual:

1. Open https://www.strava.com/athletes/YOUR_ID/follows?type=followers in your browser.
2. **Scroll to the very bottom of the list** — Strava lazy-loads names as you scroll.
3. Open DevTools (F12) → Console.
4. Paste the contents of `snippets/extract_athletes.js` and press Enter.
   The JSON is now in your clipboard.
5. Run `kudostracker paste followers` in your terminal.
6. Repeat steps 1–5 with `?type=following` and `kudostracker paste following`.

If clipboard access fails (Linux without xclip), the tool falls back to opening the target file in `$EDITOR`.

## Output

`data/report.md` contains two sections:

- **Abonnés qui ne te kudosent (presque) jamais** — your followers ranked by kudos given to you over the past 12 months (least first), with profile links.
- **Comptes que tu suis qui ne te suivent pas en retour** — accounts you follow that don't follow you back.

## Re-running

Re-run `sync` periodically; it only fetches new activities. Re-run `paste followers` / `paste following` whenever you want to refresh the lists. Re-run `report` any time.

## Development

```bash
pip install -e ".[dev]"
pytest -v
```

Tests don't touch the Strava API — all network calls are mocked via stravalib.
