# Helper scripts

One-off checks and setup tools. **These talk to live APIs** — they are not unit
tests, which is why they live here rather than in `tests/` and no longer carry a
`test_` prefix (a bare `pytest` used to collect them and authenticate against
real Gmail).

Run them from the repo root with the virtualenv active:

```bash
python scripts/check_config.py
```

| Script | What it does | Side effects |
|---|---|---|
| `check_config.py` | Validates that `.env` has every required setting | None |
| `check_connections.py` | Checks Gmail, Notion, Claude and Drive all authenticate | None |
| `check_gmail.py` | Authenticates Gmail and polls the label once | None |
| `check_drive.py` | Authenticates Drive and verifies folder access | None |
| `check_geocoding.py` | Checks the Google Maps key, billing and permissions | None |
| `check_email_alerts.py` | Sends real alert emails to the configured recipients | **Sends email** |
| `check_notion.py` | Creates a throwaway item in the Items database | **Writes to Notion** — delete the page afterwards |
| `get_refresh_token.py` | Interactive OAuth flow to mint `GMAIL_REFRESH_TOKEN` | Opens a browser |

Each script imports `_bootstrap` first, which puts the repo root on `sys.path`
and forces UTF-8 output (Windows consoles default to cp1252 and cannot encode
the ✓/✗ marks these scripts print).
