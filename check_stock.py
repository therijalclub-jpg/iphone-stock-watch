#!/usr/bin/env python3
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PART_NUMBER = "MJXU4QN/A"
PRODUCT_NAME = "iPhone 18 Pro Max 512GB Silver"
LOCATION = "N8 0QL"
APPLE_ENDPOINT = "https://www.apple.com/uk/shop/retail/pickup-message"
STATE_FILE = Path("stock_state.json")


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_state():
    if not STATE_FILE.exists():
        return {"available_store_numbers": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"available_store_numbers": []}


def write_state(available_stores):
    state = {
        "part_number": PART_NUMBER,
        "product": PRODUCT_NAME,
        "location": LOCATION,
        "available_store_numbers": sorted(
            s["storeNumber"] for s in available_stores if s.get("storeNumber")
        ),
        "available_stores": available_stores,
        "last_checked_utc": now_utc(),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def fetch_stock():
    query = urlencode(
        {
            "pl": "true",
            "parts.0": PART_NUMBER,
            "location": LOCATION,
        }
    )
    url = f"{APPLE_ENDPOINT}?{query}"
    req = Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-GB,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0 Safari/537.36"
            ),
        },
    )

    try:
        with urlopen(req, timeout=20) as response:
            status = getattr(response, "status", 200)
            raw = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"Apple returned HTTP {exc.code}; not treating this as out of stock.") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Apple: {exc}; not treating this as out of stock.") from exc

    if status != 200:
        raise RuntimeError(f"Apple returned HTTP {status}; not treating this as out of stock.")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("Apple returned a non-JSON response; not treating this as out of stock.") from exc

    stores = payload.get("body", {}).get("stores")
    if not isinstance(stores, list):
        raise RuntimeError("Apple response did not contain body.stores; endpoint may have changed.")

    available = []
    matched_part_records = 0

    for store in stores:
        part = (store.get("partsAvailability") or {}).get(PART_NUMBER)
        if not isinstance(part, dict):
            continue

        matched_part_records += 1
        pickup_display = str(part.get("pickupDisplay") or "").strip().lower()
        store_selection_enabled = part.get("storeSelectionEnabled") is True

        is_available = pickup_display == "available" or store_selection_enabled
        if not is_available:
            continue

        available.append(
            {
                "storeName": store.get("storeName", "Unknown store"),
                "storeNumber": store.get("storeNumber", ""),
                "city": store.get("city", ""),
                "distance": store.get("storeDistanceWithUnit")
                or (
                    f'{store.get("storedistance")} mi'
                    if store.get("storedistance") is not None
                    else ""
                ),
                "pickup": part.get("pickupSearchQuote")
                or part.get("storePickupQuote")
                or part.get("pickupDisplay")
                or "Available",
            }
        )

    if matched_part_records == 0:
        raise RuntimeError(
            f"Apple returned stores but no availability record for {PART_NUMBER}; "
            "not treating this as out of stock."
        )

    return available


def send_email(new_stores):
    smtp_username = os.environ.get("SMTP_USERNAME", "").strip()
    smtp_password = os.environ.get("SMTP_APP_PASSWORD", "").strip()
    recipient = os.environ.get("ALERT_EMAIL", "").strip()

    if not smtp_username or not smtp_password or not recipient:
        raise RuntimeError(
            "Stock was found, but SMTP_USERNAME, SMTP_APP_PASSWORD, or ALERT_EMAIL is missing."
        )

    lines = [
        f"{PRODUCT_NAME} is showing as available for Apple Store pickup.",
        "",
    ]

    for store in new_stores:
        details = [store["storeName"]]
        if store.get("storeNumber"):
            details.append(store["storeNumber"])
        if store.get("distance"):
            details.append(store["distance"])
        if store.get("pickup"):
            details.append(str(store["pickup"]))
        lines.append(" - " + " | ".join(details))

    lines += [
        "",
        f"Part number: {PART_NUMBER}",
        f"Search area: {LOCATION}",
        f"Checked: {now_utc()}",
        "",
        "Apple UK: https://www.apple.com/uk/shop/buy-iphone",
        "",
        "Stock can change quickly, so verify on Apple's checkout/pickup page before travelling.",
    ]

    msg = EmailMessage()
    msg["Subject"] = "iPhone 18 Pro Max 512GB Silver IN STOCK"
    msg["From"] = smtp_username
    msg["To"] = recipient
    msg.set_content("\n".join(lines))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as server:
        server.login(smtp_username, smtp_password)
        server.send_message(msg)


def main():
    previous = load_state()
    previous_numbers = set(previous.get("available_store_numbers") or [])

    current = fetch_stock()
    current_by_number = {
        s["storeNumber"]: s for s in current if s.get("storeNumber")
    }
    current_numbers = set(current_by_number)

    new_numbers = current_numbers - previous_numbers
    new_stores = [current_by_number[n] for n in sorted(new_numbers)]

    if new_stores:
        print(f"NEW STOCK FOUND at {len(new_stores)} store(s).")
        for store in new_stores:
            print(
                f'{store["storeName"]} {store.get("storeNumber","")} '
                f'{store.get("distance","")} {store.get("pickup","")}'
            )
        # Only save the new state after the email succeeds.
        send_email(new_stores)
        print("Alert email sent.")
    else:
        if current:
            print(f"Stock still available at {len(current)} previously-alerted store(s); no duplicate email.")
        else:
            print("No verified pickup stock right now.")

    # Update state after a successful, verified check.
    write_state(current)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
