import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup


STATE_FILE = "state.json"
PRODUCTS_FILE = "products.json"
TIMEOUT = 20


@dataclass
class ProductResult:
    name: str
    url: str
    trigger: str
    price: Optional[float]
    in_stock: Optional[bool]
    raw_price_text: Optional[str]
    matched_text: Optional[str]


def load_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def fetch_html(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    request_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    if headers:
        request_headers.update(headers)

    response = requests.get(url, headers=request_headers, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def extract_text_by_selector(html: str, selector: Optional[str]) -> Optional[str]:
    if not selector:
        return None
    soup = BeautifulSoup(html, "html.parser")
    element = soup.select_one(selector)
    if not element:
        return None
    return element.get_text(" ", strip=True)


def extract_text_by_regex(html: str, pattern: Optional[str]) -> Optional[str]:
    if not pattern:
        return None
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    if match.groups():
        return match.group(1).strip()
    return match.group(0).strip()


def regex_exists(html: str, pattern: Optional[str]) -> bool:
    if not pattern:
        return False
    return re.search(pattern, html, re.IGNORECASE | re.DOTALL) is not None


def parse_price(text: Optional[str]) -> Optional[float]:
    if not text:
        return None

    cleaned = text.replace(",", "")
    match = re.search(r"(?<!\d)(\d+(?:\.\d{1,2})?)(?!\d)", cleaned)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_stock_from_text(
    text: Optional[str],
    in_stock_terms: list[str],
    out_of_stock_terms: list[str],
) -> Optional[bool]:
    if not text:
        return None

    normalized = text.lower()

    for term in out_of_stock_terms:
        if term.lower() in normalized:
            return False

    for term in in_stock_terms:
        if term.lower() in normalized:
            return True

    return None


def evaluate_product(product: Dict[str, Any]) -> ProductResult:
    html = fetch_html(product["url"], headers=product.get("headers"))

    price_text = None
    stock_text = None

    if "price_selector" in product:
        price_text = extract_text_by_selector(html, product.get("price_selector"))
    elif "price_regex" in product:
        price_text = extract_text_by_regex(html, product.get("price_regex"))

    if "stock_selector" in product:
        stock_text = extract_text_by_selector(html, product.get("stock_selector"))
    elif "stock_regex" in product:
        stock_text = extract_text_by_regex(html, product.get("stock_regex"))

    price = parse_price(price_text)

    in_stock = parse_stock_from_text(
        stock_text,
        in_stock_terms=product.get(
            "in_stock_terms",
            ["in stock", "available", "add to cart", "buy now"],
        ),
        out_of_stock_terms=product.get(
            "out_of_stock_terms",
            ["out of stock", "sold out", "unavailable"],
        ),
    )

    matched_text = stock_text or price_text

    return ProductResult(
        name=product["name"],
        url=product["url"],
        trigger=product["trigger"],
        price=price,
        in_stock=in_stock,
        raw_price_text=price_text,
        matched_text=matched_text,
    )


def evaluate_page_match(product: Dict[str, Any]) -> Dict[str, Any]:
    html = fetch_html(product["url"], headers=product.get("headers"))

    matched = regex_exists(html, product.get("page_regex"))
    blocked = regex_exists(html, product.get("must_not_match_regex"))

    return {
        "matched": matched,
        "blocked": blocked,
    }


def should_alert(product: Dict[str, Any], result: ProductResult, old_state: Dict[str, Any]) -> Optional[str]:
    trigger = product["trigger"]

    if trigger == "price_below":
        threshold = float(product["threshold"])
        old_price = old_state.get("price")

        if result.price is None:
            return None

        crossed_down = old_price is not None and old_price >= threshold and result.price < threshold
        first_seen_below = old_price is None and result.price < threshold

        if crossed_down or first_seen_below:
            return (
                f"Price alert: {result.name} is now ${result.price:.2f}, "
                f"below your threshold of ${threshold:.2f}.\n{result.url}"
            )

    elif trigger == "stock_change":
        old_stock = old_state.get("in_stock")

        if result.in_stock is True and old_stock is not True:
            return f"Stock alert: {result.name} appears to be IN STOCK.\n{result.url}"

    elif trigger == "any_change":
        if (
            old_state.get("price") != result.price
            or old_state.get("in_stock") != result.in_stock
        ):
            return (
                f"Change detected for {result.name}.\n"
                f"Price: {old_state.get('price')} -> {result.price}\n"
                f"Stock: {old_state.get('in_stock')} -> {result.in_stock}\n"
                f"{result.url}"
            )

    return None


def should_alert_page_match(product: Dict[str, Any], page_result: Dict[str, Any], old_state: Dict[str, Any]) -> Optional[str]:
    old_matched = old_state.get("matched")
    old_blocked = old_state.get("blocked")

    if page_result["matched"] and not page_result["blocked"]:
        if old_matched is not True or old_blocked is True:
            return (
                f"Listing alert: {product['name']} appears to be live "
                f"and not marked sold out.\n{product['url']}"
            )

    return None


def send_slack_message(webhook_url: str, text: str) -> None:
    payload = {"text": text}
    response = requests.post(webhook_url, json=payload, timeout=TIMEOUT)
    response.raise_for_status()


def main() -> int:
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not slack_webhook_url:
        print("Missing SLACK_WEBHOOK_URL environment variable.", file=sys.stderr)
        return 1

    products = load_json_file(PRODUCTS_FILE, [])
    state = load_json_file(STATE_FILE, {})

    updated_state: Dict[str, Any] = dict(state)
    alerts: list[str] = []

    for product in products:
        if product.get("disabled"):
            print(f"[SKIP] {product['name']} is disabled.")
            continue

        key = product["id"]
        old_state = state.get(key, {})

        try:
            if product["trigger"] == "page_match_change":
                page_result = evaluate_page_match(product)
                alert = should_alert_page_match(product, page_result, old_state)

                updated_state[key] = {
                    "name": product["name"],
                    "url": product["url"],
                    "matched": page_result["matched"],
                    "blocked": page_result["blocked"],
                }

                if alert:
                    alerts.append(alert)

                print(
                    f"[OK] {product['name']}: "
                    f"matched={page_result['matched']}, blocked={page_result['blocked']}"
                )

            else:
                result = evaluate_product(product)
                alert = should_alert(product, result, old_state)

                updated_state[key] = {
                    "name": result.name,
                    "url": result.url,
                    "price": result.price,
                    "in_stock": result.in_stock,
                    "raw_price_text": result.raw_price_text,
                    "matched_text": result.matched_text,
                }

                if alert:
                    alerts.append(alert)

                print(f"[OK] {result.name}: price={result.price}, in_stock={result.in_stock}")

        except Exception as exc:
            error_message = f"[ERROR] {product['name']}: {exc}"
            print(error_message, file=sys.stderr)
            alerts.append(error_message)

    save_json_file(STATE_FILE, updated_state)

    for alert in alerts:
        try:
            send_slack_message(slack_webhook_url, alert)
        except Exception as exc:
            print(f"[ERROR] Failed to send Slack alert: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())