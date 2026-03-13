# Drop Watcher

Lightweight product watcher for GitHub Actions.

It polls product or listing pages, detects meaningful changes, sends Slack alerts, and persists state in the repository so changes are only reported when something actually changes.

## What it supports

- `price_below`: alert when a product price drops below a target threshold
- `stock_change`: alert when a known product page changes from unavailable to in stock
- `page_match_change`: alert when a listing or search page starts matching a target product signal
- `any_change`: optional debug trigger for any price or stock change

## Repository layout

- [watcher.py](/Users/raja/projects/drop-watcher/watcher.py): main watcher script
- [products.json](/Users/raja/projects/drop-watcher/products.json): product configuration
- [state.json](/Users/raja/projects/drop-watcher/state.json): persisted watcher state
- [requirements.txt](/Users/raja/projects/drop-watcher/requirements.txt): Python dependencies
- [.github/workflows/watcher.yml](/Users/raja/projects/drop-watcher/.github/workflows/watcher.yml): scheduled GitHub Actions workflow
- [agents.md](/Users/raja/projects/drop-watcher/agents.md): project intent and next steps

## How it works

1. Load products from `products.json`
2. Fetch each configured page
3. Parse price, stock, or page-match signals using CSS selectors or regex
4. Compare current results with the previous run in `state.json`
5. Send Slack alerts for meaningful changes
6. Save updated state for the next run

## Product configuration

Each product entry includes:

- `id`
- `name`
- `url`
- `trigger`

Depending on the trigger, products can also define:

- `threshold`
- `price_selector`
- `price_regex`
- `stock_selector`
- `stock_regex`
- `page_regex`
- `must_not_match_regex`
- `in_stock_terms`
- `out_of_stock_terms`
- `headers`
- `disabled`

Example:

```json
{
  "id": "wd_20tb_bestbuy",
  "name": "WD 20TB External HDD",
  "url": "https://www.bestbuy.com/site/example-product-page",
  "trigger": "price_below",
  "threshold": 279.99,
  "price_selector": "[data-testid='customer-price']"
}
```

## Setup

### GitHub Actions

1. Add a repository secret named `SLACK_WEBHOOK_URL`
2. Commit your product definitions in `products.json`
3. Let the scheduled workflow run every 15 minutes, or trigger it manually from Actions

### Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
python watcher.py
```

## Notes

- `state.json` is committed back by the workflow so the watcher remembers prior values
- HTML scraping is the current default approach, using BeautifulSoup selectors or regex on raw HTML
- Dynamic storefronts may eventually need JSON or API-based parsing for better reliability

## Current focus

The near-term use cases are:

- hard drive price alerts
- Tom Sachs x Nike GPS Black discovery alerts
- product-page stock alerts once the real sneaker product page is known
