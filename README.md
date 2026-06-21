# United Flight Monitor

Automated United Airlines MileagePlus award flight search tool. Logs into United.com, searches award flights (SFO→BJS, Business, flexible dates), filters by mileage threshold and transit airports, logs results, and emails findings. Designed for cron scheduling.

## Features

- **Auto-login**: Handles sign-in flow (username → Continue → password → Sign in), with MFA support on first run
- **Session persistence**: Saves cookies and bearer token — subsequent runs skip login
- **Flexible date search**: Uses United's FetchAwardCalendar API to find dates with Business award availability
- **Configurable filters**: Maximum miles threshold, excluded transit airports (e.g., MNL)
- **Structured logging**: All queries and results logged to timestamped files
- **Email notification**: HTML email with formatted flight results table
- **Cron-ready**: All output to log files, no interactive prompts when session is valid

## Prerequisites

- Python 3.12+
- Playwright browsers: `playwright install chromium`
- `cron` service running (for scheduled execution)
- SMTP credentials for email notifications

## Installation

```bash
cd united-flight-monitor
pip install -r requirements.txt
playwright install chromium
```

## Configuration

Edit `.env` to set your credentials and search parameters:

| Key | Description | Example |
|-----|-------------|---------|
| `UNITED_MP_NUMBER` | Your MileagePlus number | `HLX69604` |
| `UNITED_PASSWORD` | Your United.com password | `your_password` |
| `SEARCH_ORIGIN` | Origin airport (IATA) | `SFO` |
| `SEARCH_DESTINATION` | Destination airport (IATA) | `BJS` |
| `SEARCH_START_DATE` | Start of date range | `2026-09-01` |
| `SEARCH_END_DATE` | End of date range | `2026-09-30` |
| `SEARCH_CABIN` | Cabin class | `business` |
| `MAX_MILES` | Max miles threshold | `110000` |
| `EXCLUDE_AIRPORTS` | Comma-separated airports to exclude | `MNL` |
| `BROWSER_HEADLESS` | Run browser headless | `true` |
| `SEARCH_DELAY_SECONDS` | Delay between API calls | `60.0` |
| `EMAIL_TO` | Recipient email(s), comma-separated | `user@example.com` |
| `EMAIL_FROM` | Sender email | `user@example.com` |
| `EMAIL_SMTP_HOST` | SMTP server host | `smtp.163.com` |
| `EMAIL_SMTP_PORT` | SMTP port (SSL) | `465` |
| `EMAIL_SMTP_USER` | SMTP username | `user@example.com` |
| `EMAIL_SMTP_PASSWORD` | SMTP password/auth code | `your_auth_code` |

## Usage

```bash
python united_monitor.py
```

First run will prompt for MFA verification code. Subsequent runs within 24 hours will reuse saved session.

## Cron Setup

Edit crontab: `crontab -e`

Example (runs at 8:00, 14:00, 20:00 daily):
```
0 8,14,20 * * * cd /path/to/united-flight-monitor && /path/to/python united_monitor.py >> ~/.united_monitor/cron.log 2>&1
```

### Cron Prerequisites Checklist

1. `cron` service running: `systemctl status cron`
2. Python path in cron: use full path to Python executable (check with `which python3`)
3. `DATA_DIR` writable by cron user (default: `~/.united_monitor`)
4. Playwright browsers installed for cron user: `playwright install chromium`
5. `.env` accessible from project directory (cron sets HOME but not PWD)
6. Session must be valid before cron runs (run manually first to establish session)
7. System dependencies for Chromium: `libnss3`, `libnspr4`, `libatk1.0-0`, `libatk-bridge2.0-0`, `libcups2`, `libdrm2`, `libdbus-1-3`, `libxkbcommon0`, `libxcomposite1`, `libxdamage1`, `libxfixes3`, `libxrandr2`, `libgbm1`, `libpango-1.0-0`, `libcairo2`, `libasound2t64`

To install system dependencies on Ubuntu:
```bash
sudo apt-get install -y libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 \
    libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0t64 libcairo2 libasound2t64
```

## Log Files

Logs are written to `~/.united_monitor/logs/united_monitor_YYYYMMDD.log`.

## Troubleshooting

- **Login fails**: Check credentials in `.env`. Run manually to trigger MFA flow.
- **Session expired**: Delete `~/.united_monitor/sessions/united_session.json` and re-run to re-login.
- **No results**: Dates may have no Business award availability. Try different date ranges.
- **Browser crashes**: Ensure system dependencies are installed. Try `HEADLESS=false` to debug visually.
