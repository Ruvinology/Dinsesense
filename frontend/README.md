# DineSense AI — frontend

React 19 + Vite + Tailwind CSS 4 + Recharts + React Router.

## Running it

The backend must be running first (`uvicorn app.main:app --reload` in
`backend/`), because every page reads from it.

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

Demo logins (created by `backend/seed.py`):

| Role | Email | Password |
|---|---|---|
| Admin | admin@dinesense.ai | dinesense123 |
| Manager | manager@dinesense.ai | dinesense123 |

If your API is not on `http://127.0.0.1:8000`, copy `.env.example` to `.env`
and set `VITE_API_URL`.

## Pages

| Route | Access | What it does |
|---|---|---|
| `/` | Manager or admin | Dashboard — urgent alerts first, then stats, sentiment split, complaint aspects, trend, branch comparison |
| `/reviews` | Manager or admin | Searchable, filterable review list with CSV upload |
| `/analyse` | Public | Paste one review, see sentiment / aspects / urgency / recommended action |
| `/submit` | Public | The customer-facing feedback form |
| `/admin` | Admin only | Restaurants, branches, users, model metrics |
| `/login` | Public | Sign in |

## Structure

```
src/
├── api/client.js         one place that knows how to call the backend
├── auth/AuthContext.jsx  who is logged in, token handling
├── components/           Layout + shared UI pieces
├── charts/charts.jsx     all four charts
└── pages/                one file per route
```

## Design decisions worth knowing

**Positive is blue, not green.** Sentiment is a *diverging* scale — negative and
positive are opposite poles with neutral in between — so it gets two opposed
hues and a gray midpoint. Green was rejected because red/green is the single
worst colour pair for colour-blind readers (~8% of men cannot separate them).
Blue/red survives deuteranopia and protanopia. The palette was checked against
the light surface: all three colours clear 3:1 contrast, worst colour-blind
separation ΔE 8.4, worst normal-vision separation 18.1.

**Colour is never the only signal.** Every badge carries a word, urgency badges
carry an icon too, every chart has direct value labels, and the aspect data also
appears as a plain table. A reader who cannot see the colours loses nothing.

**Urgent complaints are the first thing on the dashboard**, above the stat
tiles. A manager needs to know somebody reported raw chicken before they need to
know the sentiment split. The spec listed alerts fifth; this is a deliberate
departure from it.

**The customer never sees the model's verdict.** The public form thanks them and
stops. Telling someone "we classified your complaint as negative, 91%
confident" is unsettling and invites arguing with a classifier.

**One hue for aspect counts.** That chart shows magnitude within a single
measure, so giving each bar its own colour would imply the categories differ in
kind. They do not.

**Light mode only**, deliberately — a single committed look rather than a dark
theme that was never designed or tested.

## Known limitations

- No frontend tests. The backend has 26 API tests; the React layer has none.
- The bundle is ~646 kB (192 kB gzipped), mostly Recharts. Fine for a dashboard
  behind a login; would want code-splitting for a public high-traffic page.
- CSV upload attaches rows to the *first* restaurant the user can see rather
  than offering a picker.
- Pagination is a fixed limit of 100 reviews, not real paging.
