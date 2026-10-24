# UK day-ahead wind forecast check

A small web app for an energy buyer who has to buy UK day-ahead power. It shows the wind forecast the buyer actually had when the decision had to be made, compares it with what the wind farms really delivered, and puts numbers on the error. The data is national level wind from Elexon BMRS, for delivery days in January 2026.

## Links

- Live app: https://cygazvpg.vercel.app/
- API health check: https://project-tau-seven-51.vercel.app/api/health
- Demo video (unlisted YouTube): https://youtu.be/lJlibISP4fM

## How to start

### With Docker (one command)

You need Docker Desktop running. From the repo root:

    docker compose up --build

Then open http://localhost:8080. The first build takes a few minutes. Stop it with Ctrl+C.

### Without Docker

Backend (Python 3.12), in one terminal:

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --port 8000

Frontend (Node 22 or newer), in a second terminal:

    cd frontend
    npm install
    npm run dev

Then open http://localhost:5173. In dev mode the frontend calls the backend on port 8000.

### Refreshing the data (optional)

The January data is saved in `backend/data/`, so the app does not depend on Elexon being up. To download it again:

    python3 backend/fetch_data.py

## What the app shows

1. A delivery day view: which forecast was used, forecast against actual for each hour, and the error for that day.
2. A January view: average error, bias, a worst-case number, and error for every day and for every hour of the day.
3. A cutoff control, so the buyer can change the decision time and see how the result moves.

## How the decision-time forecast is picked

This is the part that matters most. Elexon publishes many forecasts for the same target hour. A buyer buying on day D-1 can only use forecasts published before the auction cutoff, so for every hour of delivery day D the app takes the newest forecast published at or before the cutoff on D-1. It does not use the latest forecast overall, because that one is only known after the decision.

Other choices:

- Forecasts (WINDFOR) are hourly and actuals (FUELHH, fuel type WIND) are half-hourly. I average the two half-hours of each hour to get an hourly actual, so the comparison is fair.
- Error = forecast minus actual. Positive means the forecast was too high, which is the risky direction for a buyer.
- All times are UTC. January in the UK is GMT, so UTC is also London time and there is no daylight saving to handle.
- The code picks the latest publish at or before the cutoff and does not hardcode a publish time. On 1 January I saw 8 publishes (around 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30 and 22:30 UTC), each covering about 3 days ahead, but these times can shift.
- Forecasts published from 30 December 2025 are included, because they cover 1 January.

## Findings for January 2026

All 744 delivery hours matched, none skipped. With the default 09:00 UTC cutoff:

- Average error (MAE): 2,142 MW, which is 18.5% of average wind output (11,581 MW)
- RMSE: 2,612 MW
- Bias: +1,852 MW (about 16%). The forecast was too high in 85.1% of hours and on 27 of 31 days
- In 9 out of 10 hours the forecast was too high by no more than 4,300 MW
- Worst day: 28 January. Average actual wind was about 5,760 MW and the forecast was about 5,375 MW too high, nearly double
- Error is largest from about 00:00 to 07:00 (around 2.5 GW) and smallest in the afternoon (around 1.4 GW)

The cutoff time barely matters. Moving it between 03:00 and 10:00 UTC kept average error between about 2,120 and 2,200 MW. A forecast made only about 2.6 hours before delivery was still too high by about 1,600 MW on average, so the bias is not just caused by the forecast being old.

I do not know why the forecast is biased high. The two datasets may not measure exactly the same thing, or wind may have been curtailed, but I have not checked either of these. It is the first thing I would investigate next.

## Files and directories

    .
    ├── README.md
    ├── docker-compose.yml        starts backend and frontend together
    ├── .gitignore
    ├── backend/
    │   ├── main.py               FastAPI app and the API endpoints
    │   ├── analysis.py           decision-time forecast logic and error metrics
    │   ├── fetch_data.py         downloads January data from Elexon into data/
    │   ├── explore.py            small script I used to look at the WINDFOR publish pattern
    │   ├── sanity_check.py       checks I used to test the bias result
    │   ├── requirements.txt
    │   ├── Dockerfile
    │   ├── .dockerignore
    │   └── data/
    │       ├── wind_actuals.json     half-hourly actual wind, January 2026
    │       └── wind_forecasts.json   every WINDFOR forecast published 30 Dec to 31 Jan
    └── frontend/
        ├── index.html
        ├── package.json
        ├── package-lock.json
        ├── vite.config.js
        ├── eslint.config.js
        ├── nginx.conf            serves the built app and forwards /api to the backend (Docker)
        ├── vercel.json           forwards /api to the backend on Vercel
        ├── Dockerfile
        ├── .dockerignore
        ├── public/               favicon and icons
        └── src/
            ├── main.jsx
            ├── App.jsx           the whole dashboard
            ├── App.css
            ├── index.css
            ├── api.js            the calls to the backend
            └── assets/

## API

All endpoints take an optional `cutoff` in HH:MM (UTC, applied to the day before delivery). The default is 09:00.

- GET /api/health
- GET /api/config
- GET /api/day?date=2026-01-15
- GET /api/summary
- GET /api/hourly-profile

## Deployment

Both parts run on Vercel as two projects from this repo. The backend (root folder `backend`) is the FastAPI app as a Vercel function. The frontend (root folder `frontend`) is the built React app, and `frontend/vercel.json` forwards `/api/...` to the backend. Vercel does not run the Dockerfiles. Docker is for running everything locally with one command.

## Assumptions and limits

- I assumed the buyer decides at 09:00 UTC on the day before delivery. I did not take this from Elexon. It is a setting in the app, and the findings above hardly change with it.
- The data is a saved copy of January 2026, not live data.
- Only national level wind from Elexon is used, as asked. No other weather or market data.
- There are no automated tests yet. I checked the logic with `backend/sanity_check.py` and by confirming that the local app, the Docker app and the Vercel app all give the same numbers.
- The bias result is measured but unexplained, as described above.

## AI tools

I used Claude (Anthropic's AI assistant) while building this, for planning, writing code and writing this README. I ran and tested everything myself.
