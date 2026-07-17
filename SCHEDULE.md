# Scheduling the 3×/day check

Three options, easiest/most-robust first.

## Option A — GitHub Actions (recommended: free, cloud, laptop can be off)

The repo ships with `.github/workflows/check.yml`, which runs at
**06:00 / 12:00 / 18:00 UTC** and commits the updated de-dup state back.

Setup:

0. **Seed a baseline first** so the first scheduled run doesn't alert you about
   the ~26 internships already open today (only future *new* ones should ping):
   ```bash
   python3 check.py --seed     # marks current matches as seen, sends nothing
   ```
1. Make this folder its own git repo and push it to GitHub (including the
   seeded state). Run these from the `prop-internship-tracker/` directory:
   ```bash
   gh auth login                       # one-time, interactive
   git init && git add -A && git commit -m "Prop internship tracker"
   gh repo create prop-internship-tracker --private --source . --push
   ```
2. Add your CallMeBot secrets (kept encrypted by GitHub, never in the code):
   ```bash
   gh secret set CALLMEBOT_PHONE  --body "+33XXXXXXXXX"
   gh secret set CALLMEBOT_APIKEY --body "123456"
   ```
3. Enable write access for the workflow so it can commit state:
   Repo → Settings → Actions → General → *Workflow permissions* →
   **Read and write permissions** → Save.
4. Trigger a manual run to confirm: Actions tab → *prop-internship-check* →
   **Run workflow**. Or:
   ```bash
   gh workflow run prop-internship-check
   ```

Times are UTC and do **not** shift with daylight saving. Western Europe is
UTC+1 (winter) / UTC+2 (summer), so the runs land mid-morning / early-afternoon
/ evening year-round. Edit the three `cron:` lines to taste.

## Option B — Local macOS (launchd), simplest but only when the Mac is awake

`launchd/com.prop.internship.plist` runs the check at 08:00, 14:00, 20:00 local
time. Install:

```bash
cp launchd/com.prop.internship.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.prop.internship.plist
```

Put your CallMeBot creds in `.env` (already gitignored). Logs go to
`state/launchd.log`. Unload with `launchctl unload ...` to stop.

## Option C — Claude Code scheduled routine

If you'd rather drive it from Claude Code, create a routine that runs
`python3 check.py` on a cron and commits state. This is heavier than Options A/B
for a deterministic script, so prefer GitHub Actions unless you specifically
want the Claude agent in the loop.
