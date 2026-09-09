# Known Issues

Local bug tracker for the Factory Inventory Management System. Add new findings here as
they turn up; nothing in this file is fixed yet.

**Baseline:** branch `new_features` @ `27b0724` (identical to `main` — these are all in the
committed baseline, not in-flight work).
**Opened:** 2026-09-09

Status values: `open` · `in progress` · `fixed` · `wontfix` · `invalid`

---

## Summary

| ID | Severity | Area | Title | Status |
|----|----------|------|-------|--------|
| [BUG-001](#bug-001) | High | Frontend / API | Tasks feature calls `/api/tasks`, which does not exist (404) | open |
| [BUG-002](#bug-002) | High | Full stack | Purchase orders half-built across all three layers | open |
| [BUG-003](#bug-003) | Medium | Frontend | `views/Backlog.vue` is orphaned — no route, unreachable | open |
| [BUG-004](#bug-004) | Low | Docs / Tests | `TEST_SUMMARY.md` claims 55 tests; suite is 40 | open |
| [BUG-005](#bug-005) | High | Data integrity | 8 of 9 demand-forecast SKUs existed nowhere else in the system | **fixed** |
| [BUG-006](#bug-006) | Medium | Data integrity | All 4 backlog items reference orders that do not exist | open |
| [BUG-007](#bug-007) | Medium | Data integrity | `transactions.json` uses warehouse codes A/B/C, not names | open |
| [BUG-008](#bug-008) | Medium | Data integrity | 20 order records share 10 ids, making 10 orders unreachable | open |
| [OBS-001](#obs-001) | Low | Frontend | `Reports.vue` bypasses `api.js` and hardcodes the base URL | open |
| [OBS-002](#obs-002) | Low | Frontend | Some dashboard figures are hardcoded, not derived | open |
| [OBS-003](#obs-003) | Info | Security | No production hardening (documented demo scope) | open |

`BUG-*` are defects. `OBS-*` are inconsistencies or scope notes — real, tracked, but not
broken behavior. See [Lower-priority observations](#lower-priority-observations).

---

## BUG-001

**Tasks feature calls `/api/tasks`, which does not exist (404)**

- **Severity:** High — user-visible feature silently does nothing
- **Status:** open
- **Area:** Frontend / API contract

### What's wrong

`client/src/api.js` defines four methods against `/api/tasks`, and `App.vue` calls
`loadTasks()` on mount. The backend has no `/api/tasks` route at all.

- `client/src/api.js:77` — `getTasks()` → `GET /api/tasks`
- `client/src/api.js:82` — `createTask()` → `POST /api/tasks`
- `client/src/api.js:87` — `deleteTask()` → `DELETE /api/tasks/{id}`
- `client/src/api.js:92` — `toggleTask()` → `PATCH /api/tasks/{id}`
- `client/src/App.vue:149` — `onMounted(loadTasks)`
- `server/main.py` — no `/api/tasks` route defined

### Why it's invisible

Every call is wrapped in `try/catch` that only does `console.error`
(`App.vue:91`, `:99`, `:120`, `:138`). The tasks list is a computed merge of the API
results with four hardcoded mock tasks in `composables/useAuth.js`, so the modal renders
populated and looks functional. Added tasks live in browser memory only and vanish on
reload.

### Reproduce

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/api/tasks   # => 404
```

Then open the app, use the Tasks modal to add a task, and reload — the task is gone.
The browser console shows `Failed to load tasks:`.

### Decision needed

Whether tasks are meant to persist server-side. Either implement the four routes plus a
`tasks.json` data file, or drop the API calls and make the mock-only behavior explicit.
Note that the mock/API split in `deleteTask` and `toggleTask` already branches on task
origin, so the frontend is written expecting a real backend.

---

## BUG-002

**Purchase orders half-built across all three layers**

- **Severity:** High — dead UI path, guaranteed runtime component-resolution failure
- **Status:** open
- **Area:** Backend + Frontend + Data

### What's wrong

The purchase-order feature exists in fragments at every layer, with nothing connecting them.

**Backend** — models and a read-side join exist, but no routes:
- `server/main.py:104` — `class PurchaseOrder(BaseModel)` defined, never used in a route
- `server/main.py:115` — `class CreatePurchaseOrderRequest(BaseModel)` defined, never used
- `server/main.py:177` — `/api/backlog` reads `purchase_orders` to set `has_purchase_order`
- No `/api/purchase-orders` route exists → **404**

**Frontend API client** — points at the missing routes:
- `client/src/api.js:97` — `createPurchaseOrder()` → `POST /api/purchase-orders`
- `client/src/api.js:102` — `getPurchaseOrderByBacklogItem()` → `GET /api/purchase-orders/{id}`

**Frontend component** — references a component that does not exist:
- `client/src/views/Dashboard.vue:289` — template renders `<PurchaseOrderModal>`
- `client/src/views/Dashboard.vue:310-313` — `components: {}` registers only
  `ProductDetailModal` and `BacklogDetailModal`; `PurchaseOrderModal` is **not imported
  and not registered**
- `client/src/components/` — no `PurchaseOrderModal.vue` file exists
- Supporting state is wired up regardless: `showPOModal` (`:327`), set true at `:656` and
  `:662`

**Data** — `server/data/purchase_orders.json` is an empty list, so `has_purchase_order` is
always `false` on every backlog item.

### Reproduce

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/api/purchase-orders   # => 404
ls client/src/components/PurchaseOrderModal.vue                                      # => no such file
```

Load the Dashboard and check the browser console for Vue's
`Failed to resolve component: PurchaseOrderModal` warning. Any UI control that sets
`showPOModal = true` opens nothing.

### Decision needed

Whether to build the feature out or strip it. Building it means: POST/GET routes, a
writable store for `purchase_orders` (currently read-only in-memory — see the note in
[Architectural constraints](#architectural-constraints)), and the missing modal component.
Stripping it means removing the template block, the `showPOModal` state, the two `api.js`
methods, and the two unused Pydantic models.

---

## BUG-003

**`views/Backlog.vue` is orphaned — no route, unreachable**

- **Severity:** Medium — dead code, and a divergent second implementation
- **Status:** open
- **Area:** Frontend / routing

### What's wrong

`client/src/views/Backlog.vue` (152 lines) is a complete, working view — priority tiles, a
backlog table, `useFilters` integration, client-side SKU narrowing. It is unreachable:

- `client/src/main.js:14-19` — routes are `/`, `/inventory`, `/orders`, `/demand`,
  `/spending`, `/reports`. No `/backlog`.
- `client/src/App.vue` — no nav link
- No file imports it

Backlog data still reaches users, but through a **separate inline implementation** on the
Dashboard, so the same feature exists twice in divergent form.

### Reproduce

```bash
grep -rn "Backlog\.vue\|views/Backlog" client/src --include=*.js --include=*.vue   # only self-references
```

Navigating to `http://localhost:3000/backlog` falls through — no route matches.

### Decision needed

Add the route and nav entry, or delete the file. If it's added, the duplicate Dashboard
implementation should be reconciled against it.

---

## BUG-004

**`TEST_SUMMARY.md` claims 55 tests; suite is 40**

- **Severity:** Low — documentation only, no behavior impact
- **Status:** open
- **Area:** Docs / Tests

### What's wrong

`tests/TEST_SUMMARY.md` reports "**55 tests**" passing and itemizes seven suites including a
15-test "Orders Endpoints" group. Neither the number nor the breakdown has ever matched the
tree, and there is no dedicated orders test file:

| File | Tests |
|------|-------|
| `tests/backend/test_dashboard.py` | 13 |
| `tests/backend/test_inventory.py` | 10 |
| `tests/backend/test_misc_endpoints.py` | 17 |
| `tests/backend/test_restocking.py` | 44 |
| **Total** | **84** |

All 84 pass. The doc was stale at 40 before the restocking work; it is now stale at 84.
Updating it is part of fixing this entry.

### Reproduce

```bash
cd tests && uv run --project ../server pytest backend/ -q
# => 40 passed, 2 warnings
```

### Decision needed

Whether the missing ~15 tests were ever written. If the itemized Orders coverage in the doc
describes intended tests, this is a **coverage gap** rather than pure doc drift —
`/api/orders`, `/api/orders/{id}`, and quarter filtering (`Q1-2025` via `QUARTER_MAP`) have
no dedicated test file. Worth deciding before simply editing the number down.

---

## BUG-005

**8 of 9 demand-forecast SKUs existed nowhere else in the system**

- **Severity:** High — silently broke any join from forecasts to stock or cost
- **Status:** fixed (2026-09-09)
- **Area:** Data integrity

### What was wrong

`server/data/demand_forecasts.json` carried 9 SKUs. Only `PSU-501` had a matching record in
`inventory.json` or as a line item in `orders.json`. The other eight — `WDG-001`, `BRG-102`,
`GSK-203`, `MTR-304`, `FLT-405`, `VLV-506`, `SNR-420`, `CTL-330` — had no unit cost, no
category, no warehouse, and no stock level anywhere in the app.

The Demand tab did not expose this because it renders forecast records directly and never
joins to inventory. It surfaced immediately when the Restocking feature needed a unit cost
per forecast item to price a budget against.

### Fix

Added the 8 missing SKUs to `server/data/inventory.json` (32 → 40 records) with category,
warehouse, location, unit cost, on-hand quantity, and reorder point. Stock levels were set
relative to reorder points deliberately, so the three increasing-trend items sit at or below
their reorder point and exercise the recommender's urgency boost.

Side effects, both intended: these 8 items now appear in the Inventory tab, and they count
toward dashboard inventory value and low-stock metrics.

### Follow-up

`server/data/backlog_items.json` and `transactions.json` were not audited for the same class
of orphaned-SKU problem. Worth a pass — see the guard test suggestion below.

### Guard

Added. `tests/backend/test_data_integrity.py` asserts cross-file referential integrity
directly against `server/data/*.json` — SKU resolution, name agreement, warehouse and
category vocabulary, and identifier uniqueness. Running it is what surfaced BUG-006,
BUG-007 and BUG-008, which are marked `xfail(strict=True)` there so fixing the data fails
the run until the marker is removed.

---

## BUG-006

**All 4 backlog items reference orders that do not exist**

- **Severity:** Medium — every backlog row is a dangling reference
- **Status:** open
- **Area:** Data integrity

### What's wrong

`server/data/backlog_items.json` has 4 items with `order_id` values `ORD-2025-0927`,
`ORD-2025-0928`, `ORD-2025-0929`, `ORD-2025-0930`. `orders.json` order numbers run
`ORD-2025-0001` through `ORD-2025-0250`. None of the four resolve, against either
`order_number` or `id`.

This is 100% of the backlog data, not a stray record. Any feature that tries to open the
originating order from a backlog row will find nothing.

### Reproduce

```bash
cd tests && uv run --project ../server pytest \
  backend/test_data_integrity.py::TestKnownIntegrityDefects::test_backlog_order_ids_exist_in_orders -q
# currently xfail; remove the marker once the data is fixed
```

### Decision needed

Whether to repoint the four backlog items at real order numbers, or extend `orders.json` to
cover the 09xx range they expect. Repointing is smaller but changes which orders appear
backlogged.

---

## BUG-007

**`transactions.json` uses warehouse codes A/B/C, not warehouse names**

- **Severity:** Medium — breaks any warehouse join or filter on spending data
- **Status:** open
- **Area:** Data integrity

### What's wrong

Every other file uses `San Francisco` / `London` / `Tokyo`. All 56 records in
`transactions.json` use single-letter codes instead: `A` (27), `B` (19), `C` (10).

The mapping is implied by `inventory.json`'s `location` field (`Warehouse A-12` belongs to
San Francisco, `B-08` to London, `C-02` to Tokyo), so A/B/C almost certainly mean
San Francisco/London/Tokyo — but nothing in the code performs that translation.

The global warehouse filter passes a full name, so filtering transactions by warehouse can
only ever match zero records. It goes unnoticed because `/api/spending/transactions` accepts
no filter parameters at all today.

### Reproduce

```bash
python3 -c "import json,collections; print(collections.Counter(t['warehouse'] for t in json.load(open('server/data/transactions.json'))))"
# Counter({'A': 27, 'B': 19, 'C': 10})
```

### Decision needed

Rewrite the 56 records to use full warehouse names (consistent with everything else), or
introduce an explicit code-to-name mapping in the backend. The first is simpler and removes
the ambiguity rather than encoding it.

---

## BUG-008

**20 order records share 10 ids, making 10 orders unreachable**

- **Severity:** Medium — silent data loss through the single-order endpoint
- **Status:** open
- **Area:** Data integrity

### What's wrong

`orders.json` holds 250 records but only 240 distinct `id` values. Ids `201` through `210`
each appear twice, and the duplicated pairs are genuinely different orders — different
customer, status, date, and value:

| id | order_number | customer | status | value |
|----|--------------|----------|--------|-------|
| 201 | ORD-2025-0201 | PowerTech Solutions | Delivered | $4,747.50 |
| 201 | ORD-2025-0201 | Dynamic Systems Ltd | Shipped | $31,154.00 |

`order_number` is duplicated identically, so neither field can disambiguate.

`GET /api/orders/{id}` resolves with `next((o for o in orders if o["id"] == order_id), None)`
— it returns the first match and the second order is unreachable through the API. Totals and
list views are unaffected because they iterate the full list.

This also means `:key="order.id"` in any `v-for` over orders produces duplicate keys, which
Vue warns about and which can cause incorrect DOM reuse.

### Reproduce

```bash
python3 -c "
import json,collections
o=json.load(open('server/data/orders.json'))
print('records:',len(o),'distinct ids:',len({x[\"id\"] for x in o}))
print([i for i,n in collections.Counter(x['id'] for x in o).items() if n>1])"
# records: 250 distinct ids: 240
```

### Decision needed

Renumber the 10 duplicates to unique ids and order numbers. Straightforward, but check
nothing else references those ids first.

---

## Lower-priority observations

Real and tracked, but not broken behavior.

### OBS-001

**`Reports.vue` bypasses `api.js` and hardcodes the base URL**

- **Severity:** Low · **Status:** open · **Area:** Frontend consistency

Every other view imports `api` from `api.js`. `Reports.vue` imports `axios` directly
(`:128`) and hardcodes `http://localhost:8001` twice (`:156`, `:162`). The two reports
endpoints are the only ones absent from the central client, so a future base-URL change
(env config, deploy) would miss them.

### OBS-002

**Some dashboard figures are hardcoded, not derived**

- **Severity:** Low · **Status:** open · **Area:** Frontend / demo data

`client/src/views/Dashboard.vue` holds literals that sit beside genuinely computed metrics
and do not respond to filters:

- `:340` — `ordersData = ref({ fulfilled: 187, goal: 200 })`
- `:341` — `fillRate = ref(96.8)`
- `:345` — `monthlyGoal = 800000` (→ $9.6M for a full year)

May well be intentional for a demo. Flagged because the visual treatment is identical to
the live metrics, so a viewer can't tell which numbers respond to the filter bar.

### OBS-003

**No production hardening**

- **Severity:** Info · **Status:** open · **Area:** Security / scope

Listed for orientation, not as a defect — the README states the demo scope explicitly.

- `server/main.py` — CORS `allow_origins=["*"]` together with `allow_credentials=True`
- No authentication or authorization; `useAuth.js` hardcodes `isAuthenticated = true`, and
  `logout()` raises an `alert()`
- No rate limiting
- No pagination on `/api/orders` (250 records returned in full)
- API base URL hardcoded in `api.js` rather than environment-driven

---

## Architectural constraints

Context that affects how several of the above can be fixed.

**Data is read-only for the life of the process.** `server/mock_data.py` reads
`server/data/*.json` at import time into module-level Python lists. There is no database and
no write path. Any fix that needs to persist user actions (BUG-001 tasks, BUG-002 purchase
orders) has to either accept in-memory-only writes that reset on restart, write back to the
JSON files, or introduce real storage. That's a scope decision, not an implementation
detail.

See [`docs/architecture.html`](architecture.html) for the full system overview — layer diagram,
tech stack, data flow, and the full API surface.

---

## Adding a new entry

Copy this template, take the next free ID, and add a row to the summary table.

```markdown
## BUG-00N

**One-line title**

- **Severity:** High | Medium | Low | Info
- **Status:** open
- **Area:**

### What's wrong

Description, with `file.ext:line` references.

### Reproduce

Exact commands or steps, and the observed result.

### Decision needed

What has to be settled before this can be fixed. Omit if it's obvious.
```
