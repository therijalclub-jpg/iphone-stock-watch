# iPhone 18 Pro Max 512GB Silver Stock Watch

Checks Apple UK pickup availability for:

- **iPhone 18 Pro Max**
- **512GB**
- **Silver**
- Apple part number: `MJXU4QN/A`
- Search location: `N8 0QL`

The GitHub Action runs every 5 minutes (GitHub's minimum supported scheduled interval).

When a newly available Apple Store appears, it sends one Gmail alert. It does not repeatedly email every 5 minutes while the same store remains available.

## 1. Create the repository

A **public repository** is recommended because standard GitHub-hosted Actions are free for public repositories. Do not put any passwords or app passwords in the files.

Upload all files in this ZIP, including the `.github/workflows/stock-watch.yml` path.

## 2. Add GitHub Actions secrets

In the repository:

**Settings → Secrets and variables → Actions → New repository secret**

Create:

- `SMTP_USERNAME` — the Gmail address that will send the alert
- `SMTP_APP_PASSWORD` — a Gmail App Password, not your normal Google password
- `ALERT_EMAIL` — `therijalclub@gmail.com`

If you want the sending account to be `therijalclub@gmail.com`, set `SMTP_USERNAME` to the same address.

## 3. Create a Gmail App Password

The sending Google account normally needs 2-Step Verification enabled.

In your Google Account security settings, create an App Password for this stock watcher and use that 16-character value as `SMTP_APP_PASSWORD`.

Do **not** commit the App Password to the repository.

## 4. Run a test

Open the repository's **Actions** tab → **iPhone Stock Watch** → **Run workflow**.

If no stock is found, the run should complete without sending an email.

If Apple blocks or changes the endpoint, the workflow fails instead of falsely reporting "out of stock".

## How duplicate alerts are prevented

`stock_state.json` stores only the last verified store availability. The workflow commits that state when it changes.

You get an email when a store becomes newly available. If it later goes unavailable, the state resets; if it appears again later, you'll get another alert.

## Notes

Apple's pickup endpoint is undocumented and may change. The script uses the public, read-only pickup data and does not attempt to bypass CAPTCHA, authentication, rate limits, or anti-bot controls.
