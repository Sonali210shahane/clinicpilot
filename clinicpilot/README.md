# ClinicPilot

ClinicPilot is a Python healthcare automation tool for a busy 7-day GP clinic. It reads appointment requests written in plain words and decides how urgent each one is. It then picks the right booking type, writes a message for the patient and a short summary for reception, and puts everything in a queue sorted by urgency.

It works in two ways:
- **Web app:** patients fill in a form, and reception sees a live, prioritised queue.
- **Batch script:** it takes a spreadsheet of hundreds of requests and turns it into a colour-coded Excel report in seconds.

Safety rules always run first. Google Gemini AI is an optional second layer that can raise the urgency of a request but never lower it.

> Demo only. "Harbourview 7-Day Medical" is a fictional clinic and every patient is an example. The tool routes requests and does not give medical advice.

More detail: [Project overview](docs/PROJECT_OVERVIEW.md) · [Architecture](docs/ARCHITECTURE.md) · [Testing](TESTING.md)

## Quick start
You need Python 3.9 or newer.

```bash
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

Run the batch automation on the sample spreadsheet:
```bash
python batch_triage.py sample_data/appointment_requests.csv
```
This creates `triage_report.xlsx`.

Run the tests:
```bash
pytest -v
```

## Turning on AI (optional)
1. Get a free key at https://aistudio.google.com/apikey
2. Copy `.env.example` to a new file called `.env` and paste your key after `GEMINI_API_KEY=`
3. Restart `python app.py`. The badge at the top of the page changes to **Rules + Gemini**.

The batch script uses AI when you add `--ai`:
```bash
python batch_triage.py sample_data/appointment_requests.csv --ai
```

The key stays on the server and is never sent to the browser. Patient names are never sent to the AI.

## Urgency levels
| Level | Meaning | Booking |
|---|---|---|
| Emergency | Possible threat to life | Call 000, no booking |
| Same-day | Needs a GP today | Standard or long consult |
| Routine | GP within 1-3 days | Standard, long or nurse |
| Telehealth | Admin or stable follow-up | Phone or video |
| Self-care | Minor, short-lived symptoms | Pharmacist first |

## Project structure
```
ClinicPilot_Code/
├── app.py                     Flask web server and JSON API
├── batch_triage.py            Spreadsheet in, colour-coded Excel report out
├── clinicpilot/
│   ├── rules.py               Safety rules engine (red flags, urgency, booking type)
│   ├── ai.py                  Gemini client, triage prompt, AI + rules merge
│   ├── clinic.py              Clinic information and the FAQ assistant
│   ├── queue_store.py         Reception queue saved to a JSON file
│   └── settings.py            Reads the .env file
├── static/index.html          Web interface (HTML, CSS, JavaScript)
├── sample_data/
│   └── appointment_requests.csv   24 example requests
├── tests/                     60 automated tests (pytest)
├── docs/                      Project overview and architecture
├── requirements.txt
├── .env.example
├── README.md
└── TESTING.md
```

## How it works
1. **Intake.** The web form or a spreadsheet row provides age, request type, description, duration, severity (0-10), red-flag ticks, pregnancy and long-term conditions.
2. **Safety rules** (`rules.py`). The description and ticks are checked for 9 red flags:
   - chest pain
   - breathing difficulty
   - stroke signs
   - collapse
   - heavy bleeding
   - severe allergy
   - meningococcal signs
   - sudden severe headache
   - self-harm

   Rules for age, pregnancy, severity, duration and keywords then set the level and booking.
3. **AI layer** (`ai.py`, optional). Gemini receives the form and the rules result and returns JSON with urgency, booking, reasons, a patient message and a reception summary.
4. **Merge.** The more urgent of the two levels is kept. If the AI is unavailable or returns something invalid, the rules result is used.
5. **Output.** The result goes to the web queue, or into the Excel report.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/config` | Levels, red flags, clinic info, AI status |
| POST | `/api/triage` | Triage one request |
| POST | `/api/chat` | Ask the clinic assistant |
| GET / POST / DELETE | `/api/queue` | List, add to or clear the queue |
| DELETE | `/api/queue/<id>` | Mark one request as done |
| POST | `/api/queue/examples` | Reload the example requests |
| GET | `/api/queue.csv` | Download the queue as CSV |

## Deploying online (free)
On Render, create a **Web Service** from the GitHub repository and use these settings:
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app`
- To turn on AI, add `GEMINI_API_KEY` under **Environment**.

## Tech stack
- **Language:** Python 3.
- **Libraries:**
  - Flask: web server and API
  - requests: Gemini API calls
  - openpyxl: Excel reports
  - pytest: tests
- **AI:** Google Gemini (`gemini-2.5-flash`) with JSON output mode, at temperature 0.2.
- **Interface:** HTML, CSS and JavaScript, with no framework.

## Known limitations
- "No chest pain" still triggers the chest-pain flag. This is a deliberate choice, because a false alarm is safer than a missed emergency.
- The queue is stored in a JSON file, which suits a demo. A real clinic would need a database and logins.
- The rules have not been reviewed by clinicians.
