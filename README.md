# Prop-firm summer internship tracker

Checks proprietary trading firms' career pages **3× a day** and sends you a
**WhatsApp** message when a new **summer internship** in **quant / trading /
structuring** is posted. Only *new* postings trigger an alert — no repeats.

- Pure Python **standard library** — no `pip install` needed.
- Reads jobs from each firm's applicant tracking system (Greenhouse, Lever,
  Ashby, SmartRecruiters, Workday, Workable, Recruitee) for clean, reliable
  data, with an HTML fallback for plain pages.
- De-dup state is committed to the repo, so it survives across scheduled runs.

## Layout

```
check.py                 # entry point
prop_tracker/
  http.py                # urllib helpers
  ats.py                 # per-ATS fetchers → normalized Job
  filters.py             # "summer internship in quant/trading/structuring?"
  state.py               # seen-jobs de-dup store
  notify.py              # CallMeBot WhatsApp
  report.py              # Markdown report of current matches
config/firms.json        # tracked firms + their ATS config
config/filters.json      # what counts as a match (category, season, year, location)
state/seen_jobs.json     # de-dup state (auto-managed)
reports/latest.md        # current open matches (auto-written)
tools/                   # discovery/probe helpers (not needed at runtime)
```

## Quick start

```bash
# 1. See what matches right now, without sending anything or touching state:
python3 check.py --dry-run

# 2. Debug a single firm (prints every job it fetched):
python3 check.py --firm "Jump Trading" --show-all

# 3. Seed a baseline once (marks today's open roles as seen, sends nothing)
#    so you only get pinged about FUTURE new postings:
python3 check.py --seed

# 4. Real run (sends WhatsApp for new roles, updates state):
python3 check.py
```

## WhatsApp setup (CallMeBot, free)

1. Add **+34 644 51 95 23** to your phone contacts.
2. Send it this WhatsApp message: `I allow callmebot to send me messages`
3. You'll receive your **API key** in reply.
4. Copy `.env.example` to `.env` and fill in:
   ```
   CALLMEBOT_PHONE=+33XXXXXXXXX     # your number, with country code
   CALLMEBOT_APIKEY=123456
   ```
   (Env vars override the file; the cloud schedule sets them as secrets.)

Without these set, the tracker still runs and writes the report — it just skips
the WhatsApp send and logs that it was skipped.

## Matching rules

A role matches when it looks like an **internship** (title/department contains
intern / internship / co-op / "summer analyst" / summer <year> intern …) **and**
mentions at least one of:

| Category     | Matches |
|--------------|---------|
| quant        | quant, quantitative, quants |
| trading      | trade, trader, trading |
| structuring  | structuring, structurer, structured products |

Plus two constraints from `config/filters.json` (edit these, no code change):

- **`min_year`** (default `2027`): drops roles that name an earlier year (e.g.
  a stale "Summer 2026"); undated roles are kept. Set to `null` to disable.
- **`location_keywords`** (default: European hubs — London, Dublin, Amsterdam,
  Paris, Zurich, …): keeps only roles whose location matches. Empty the list to
  allow anywhere. `keep_unknown_location` keeps roles with a blank location.
- **`require_summer`** (default `true`): drops explicitly winter/fall/spring roles.

Matching is intentionally slightly permissive (better to over-notify than miss).
Deeper patterns live in `prop_tracker/filters.py`.

## Adding / editing firms

`config/firms.json` holds one object per firm. Examples of each source:

```json
{ "name": "Jump Trading",  "source": "greenhouse",      "token": "jumptrading" }
{ "name": "SomeFirm",      "source": "lever",           "company": "somefirm" }
{ "name": "SomeFirm",      "source": "ashby",           "org": "somefirm" }
{ "name": "SomeFirm",      "source": "smartrecruiters", "company": "SomeFirm" }
{ "name": "Optiver",       "source": "workday", "host": "optiver.wd3.myworkdayjobs.com", "tenant": "optiver", "site": "External" }
{ "name": "SomeFirm",      "source": "workable",        "account": "somefirm" }
{ "name": "SomeFirm",      "source": "recruitee",       "company": "somefirm" }
{ "name": "SomeFirm",      "source": "html",            "url": "https://somefirm.com/careers" }
```

Set `"disabled": true` on any entry to skip it.

To discover a firm's ATS automatically:

```bash
echo '[{"name":"NewFirm","url":"https://newfirm.com"}]' > tools/one.json
python3 tools/discover.py tools/one.json
```

## Scheduling (3× a day)

See `SCHEDULE.md` for the cloud-routine and local-cron options.
