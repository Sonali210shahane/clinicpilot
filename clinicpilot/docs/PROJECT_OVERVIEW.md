# ClinicPilot: AI Front Desk for a 7-Day GP Clinic

**Domain:** Healthcare · **Category:** Automation, Innovation & New Ideas · **Type:** Python application with a web interface, a batch automation script and automated tests

> Demo only. "Harbourview 7-Day Medical" is a fictional clinic and all patients are examples. The tool routes requests and does not give medical advice. Phone numbers use the ACMA fictitious number range.

## The problem
A busy 7-day GP clinic receives hundreds of calls and online requests every day, and reception handles them by hand:
- Requests arrive as unstructured text, so staff must read and interpret each one.
- Urgency is judged differently by each receptionist.
- A patient with a serious symptom can sit in the same queue as a routine request.
- Simple admin (repeat scripts, certificates) takes in-person slots that sick patients need.
- Sorting a backlog of requests by hand each morning is slow and repetitive.

## The solution
ClinicPilot reads each request and, in a fraction of a second:
1. Decides **how urgent** it is.
2. Chooses the **right booking type** (standard, long, telehealth, nurse or pharmacist).
3. Writes a **plain-English message** for the patient.
4. Writes a **short clinical summary** for reception.
5. Places it in a **queue sorted by urgency**, so the sickest patients are seen first.

It does this in two ways:

| Mode | Who uses it | What it does |
|---|---|---|
| **Web app** (`python app.py`) | Patients and reception | Live intake form, prioritised reception queue, clinic FAQ chatbot |
| **Batch automation** (`python batch_triage.py requests.csv`) | Practice manager | Turns a spreadsheet of requests into a colour-coded Excel report with a summary sheet, in seconds |

## Features
| Feature | Description |
|---|---|
| Safety rules engine | Written in Python. Detects 9 red flags in ticked boxes and in free text, plus rules for age, pregnancy, severity, duration and long-term conditions |
| AI layer | Google Gemini adds natural-language understanding, patient messages and reception summaries, and can raise urgency |
| Guardrail | AI can raise urgency but never lower it; invalid or missing AI output falls back to the rules |
| Explainable results | Every decision lists its reasons, tagged RULE, AI or GUARD |
| Reception queue | Sorted by urgency, then severity, then wait time. Can be filtered, marked done and exported as CSV |
| Clinic assistant | Chatbot that answers only from clinic information: hours, fees, bulk billing, telehealth and parking |
| Excel report | Colour-coded triage queue, a summary with counts per level and booking type, and a "Needs review" sheet for bad rows |
| Privacy | API key kept on the server; patient names are never sent to the AI |

## Urgency levels
| Level | Meaning | Target |
|---|---|---|
| Emergency | Possible threat to life | Call 000 now; booking blocked |
| Same-day | Needs a GP today | Within 4 hours |
| Routine | Standard GP visit | Within 1-3 days |
| Telehealth | Admin or stable follow-up | Next phone or video slot |
| Self-care | Minor, short-lived symptoms | Pharmacist today; GP if not better in 3-5 days |

## Safety design
- **Never diagnoses.** The tool only decides where a request should go.
- **Red flags always win.** The nine red flags are:
  - chest pain
  - breathing difficulty
  - stroke signs
  - collapse or seizure
  - heavy bleeding
  - severe allergic reaction
  - meningococcal signs
  - sudden severe headache
  - self-harm
- **Self-harm language** shows 000, Lifeline 13 11 14 and 13YARN.
- **The AI can escalate but never downgrade.** This is enforced in Python code, not only in the prompt.
- **Fails safe.** If the AI is unavailable or returns invalid output, the rules result is used.
- **Conservative.** When unsure, the more urgent level is chosen.

## AI tools used
| Tool | Role | Why |
|---|---|---|
| Claude (Anthropic) | Designed the product, wrote the code and tests, found and fixed bugs, wrote documentation | Handles long, careful code well and can run tests in its own workspace |
| Google Gemini API | Runs inside the app: urgency reasoning, patient messages, reception summaries, chatbot | Free tier, fast, built-in JSON output mode |

## Results
- **60 automated pytest tests, all passing.** They cover:
  - routing scenarios
  - bad input
  - the AI guardrail, using a fake AI client
  - the web API
  - the Excel report
- **Sample run:** the 24-row sample spreadsheet was processed in under a second, with these results:
  - 4 emergencies
  - 8 same-day
  - 4 routine
  - 5 telehealth
  - 2 self-care
  - 1 row flagged for review
- **A real safety bug was found by testing and fixed.** Chest pain spreading to the left arm was first routed as "same-day" instead of "000".

## Known limitations
- Keyword matching is deliberately cautious, so "no chest pain" still triggers the chest-pain flag.
- The queue is stored in a JSON file, which suits a demo. A clinic would need a database and logins.
- The rules have not been reviewed by clinicians.

## Next steps
1. Handle negation ("no chest pain") in the safety screen.
2. Store the queue in a database and add staff logins.
3. Send SMS confirmations to patients.
4. Connect to practice software (e.g. Best Practice, MedicalDirector, HotDoc).
5. Offer intake in more languages.
6. Have clinicians review the rules against the Australasian Triage Scale.
