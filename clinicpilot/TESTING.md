# Testing

ClinicPilot has **60 automated tests**, written in Python with pytest. They take under a second to run and need no internet or API key.

```bash
pip install -r requirements.txt
pytest -v
```
Expected last line: `60 passed`

Run one file: `pytest -v tests/test_rules.py`
Run tests by name: `pytest -v -k ai`

## Test files
| File | Tests | What it checks |
|---|---|---|
| `tests/test_rules.py` | 27 | The safety rules engine |
| `tests/test_ai.py` | 17 | The AI layer and guardrail (Gemini replaced with a fake client) |
| `tests/test_api.py` | 12 | The Flask web server and API |
| `tests/test_batch.py` | 4 | The batch script and Excel report |

## Rules engine (`test_rules.py`)
14 patient scenarios, each checked for the right urgency **and** booking type:

| Scenario | Expected |
|---|---|
| Chest tightness going down the left arm | Emergency, no booking |
| Face drooping, slurred speech | Emergency |
| Throat swelling after eating prawns | Emergency |
| Child with ear pain and fever | Same-day |
| Baby with a temperature | Same-day |
| Pregnant with cramping | Same-day |
| Age 80, moderate symptoms | Same-day |
| New problem under 24 hours, severity 6 | Same-day |
| Repeat blood pressure script | Telehealth |
| Follow-up of an improving rash | Telehealth |
| Runny nose and sore throat, age 29 | Self-care, pharmacist |
| Anxiety and poor sleep | Routine, long consult |
| Flu vaccination | Routine, nurse |
| Diabetes with a new problem | Routine, long consult |

The file also checks these cases:
- "I want to end it all" shows crisis lines (000 and Lifeline 13 11 14).
- A ticked red-flag box counts even when the description doesn't mention it.
- Babies, people over 75 and people with long-term conditions never get "self-care".
- Admin requests with high severity go to an in-person visit.
- The reception summary contains the key details.
- Bad input is rejected with a clear message (missing age, age 150, empty description, unknown request type).
- Severity above 10 is capped at 10.
- The known limitation: "no chest pain" still flags, on purpose.

## AI layer (`test_ai.py`)
Gemini is replaced by a `FakeClient` that returns a fixed answer, so these tests are free and give the same result every time.

| Test | What it proves |
|---|---|
| AI can escalate | A cold that the AI rates "routine" moves up from self-care |
| AI cannot downgrade | A child with fever stays same-day even if the AI says self-care; a GUARD reason is shown |
| AI cannot remove an emergency | Chest pain stays emergency and the message still says 000 |
| Crisis message | Lifeline 13 11 14 is always added for self-harm |
| Invalid AI answer | Plain text instead of JSON falls back to the rules result |
| API error | A Gemini error (e.g. rate limit) falls back to the rules result |
| Privacy | The patient's name is never sent to the AI |

The file also tests the JSON parser, the Gemini client's network errors and responses (using pytest's `monkeypatch`), and the chatbot with and without AI.

## Web API (`test_api.py`)
Uses Flask's test client, so no server needs to be running. It checks these behaviours:
- The home page loads.
- Config returns 9 red flags and 5 levels.
- Triage returns the right result, and bad input gets a 400 error.
- The queue starts with 5 examples, sorts a new emergency to the top, and can remove, clear and reload entries.
- An invalid queue entry is rejected.
- The CSV export has the right header and rows.
- The chatbot answers FAQs, sends emergencies to 000, and rejects empty messages.

## Batch script (`test_batch.py`)
- Runs on `sample_data/appointment_requests.csv` and checks the Excel report:
  - It has 3 sheets.
  - It triages 23 requests, with 4 emergencies, sorted by urgency.
  - The row with no age goes to "Needs review".
- Reads an `.xlsx` file as input as well as `.csv`.
- Returns an error code for a missing file.
- Accepts friendly labels such as "Repeat prescription", "More than a week" and "Yes".

## Bug found during testing
An early version routed *"Tightness across my chest... goes down my left arm"* as **same-day** instead of **emergency**. The pattern only matched when "chest" and "tight" were next to each other. It was widened, and the first scenario in `test_rules.py` now guards against it.
