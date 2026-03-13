# AGENTS.md

## Project
Build a lightweight product watcher that runs on GitHub Actions and alerts via Slack when:
1. a hard drive falls below a target price
2. a sneaker product changes from unavailable to available
3. a sneaker listing first appears on a store page before the product page is known

The initial goal is a universal watcher that can support both categories with one codebase.

## Why
This project started from two separate user needs:
- watch for Nike GPS / Tom Sachs sneaker drops expected in spring
- watch external hard drive pricing for a Mac mini media server / Blu-ray ripping setup

These are treated as one monitoring system with different trigger types.

## Core product idea
A single watcher should:
- poll product pages on a schedule
- parse either price or stock signals
- compare current values to last known state
- send Slack alerts on meaningful changes
- persist state in the repository

## Trigger types
### 1. `price_below`
Used for products like hard drives.
Alert when current price is below a configured threshold.

### 2. `stock_change`
Used for products like sneaker drops on known product pages.
Alert when a page appears to move from unavailable/sold out to in stock.

### 3. `page_match_change`
Used for product discovery when no product page is known yet.
Alert when a page starts matching a target regex and is not blocked by an optional secondary regex such as "Sold out".

### 4. `any_change`
Optional debug mode.
Alert when either price or stock value changes.

## Current implementation shape
Repo structure:

- `.github/workflows/watcher.yml`
- `watcher.py`
- `products.json`
- `requirements.txt`
- `state.json` (generated and committed by workflow)
- `AGENTS.md`

## Technical approach
### Runtime
- GitHub Actions on a cron schedule
- Python 3.11

### Parsing
Use one of:
- CSS selectors via BeautifulSoup
- regex against raw HTML

Each product config can specify:
- `price_selector` or `price_regex`
- `stock_selector` or `stock_regex`
- `page_regex`
- `must_not_match_regex`
- `in_stock_terms`
- `out_of_stock_terms`

### Notifications
Slack incoming webhook using repository secret:
- `SLACK_WEBHOOK_URL`

### Persistence
Persist last-known state in `state.json` and commit it back to the repo after each run.

## Configuration format
Products are defined in `products.json`.

Each item should include:
- `id`
- `name`
- `url`
- `trigger`

Depending on trigger, may also include:
- `threshold`
- `price_selector`
- `price_regex`
- `stock_selector`
- `stock_regex`
- `page_regex`
- `must_not_match_regex`
- `in_stock_terms`
- `out_of_stock_terms`
- optional custom headers
- `disabled`

## Important product nuances
### Hard drives
- slower-moving use case
- GitHub Actions polling cadence is perfectly fine
- threshold-based price alerts are the main feature

### Sneakers
- inventory can change quickly
- GitHub Actions is fine for alerting, but not ideal for competitive buying
- dynamic storefronts may require API inspection, not just HTML scraping
- false positives are possible if page copy says "coming soon" or loads inventory client-side

## Tom Sachs GPS Black target
The current target sneaker is:
- Tom Sachs x Nike GPS “Black”
- Style code: FZ1363-002

Important implementation note:
- the watcher should first monitor Tom Sachs store/search/collection pages for the product to appear
- after the real product URL is known, add or enable a product-page stock watcher

## Tom Sachs-specific implementation notes
Tom Sachs store pages may expose useful scrapeable text such as:
- "NikeCraft: General Purpose Shoe"
- "Sold out"
- per-size "Unavailable"

This means HTML scraping is a reasonable first pass.
A later improvement would be to detect store JSON endpoints once the product handle exists.

## Constraints
- Do not build an auto-checkout bot
- Keep this focused on monitoring and alerts
- Prefer maintainable parsing over brittle hacks
- Support multiple products across multiple retailers

## Near-term improvements
1. Add richer Slack messages with product name, old/new values, and direct URL
2. Add per-site parser modules if selectors become messy
3. Add retries / backoff around network errors
4. Add a debug mode that prints matched selectors and snippets
5. Add support for JSON/API-based product endpoints when available
6. Add alert deduping / cooldown window
7. Add optional email or Discord notifications
8. Add size-specific stock tracking for sneaker products
9. Add unit tests for parsing helpers
10. Add a simple README for setup

## Good next steps for Codex
1. Refactor `watcher.py` into:
   - `fetch.py`
   - `parse.py`
   - `notify.py`
   - `state.py`
2. Add schema validation for `products.json`
3. Add tests for:
   - price parsing
   - stock term detection
   - page regex detection
   - trigger logic
4. Improve the GitHub Actions workflow to avoid noisy commits
5. Add site-specific examples for Best Buy, WD, Shopify-like sneaker stores, and Nike-style product pages

## Success criteria
The project is successful if:
- a HDD page triggers a Slack alert when price drops below a target
- a sneaker discovery page triggers a Slack alert when the target product appears
- a sneaker product page triggers a Slack alert when stock appears
- state persists between workflow runs
- adding a new product usually requires only config changes