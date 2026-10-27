import json
import os
import re

import requests

from .rules import APPOINTMENTS, DURATIONS, LEVELS, REQUEST_TYPES, more_urgent, triage

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"

TRIAGE_PROMPT = """You are the intake assistant for Harbourview 7-Day Medical, an Australian general practice. You help reception staff route appointment requests. You do NOT diagnose, name possible conditions, or recommend medicines.

You receive a JSON intake form and the result of the clinic's rule-based safety screen.

Choose exactly one urgency level:
- "emergency": possible threat to life. Patient must call 000.
- "urgent": should see a GP today.
- "routine": GP appointment within 1-3 days.
- "telehealth": can be handled by phone or video (admin requests, stable follow-ups).
- "selfcare": minor, short-lived symptoms that a pharmacist can help with first.

Rules:
1. Never choose a less urgent level than the safety screen's level. You may escalate if the free text suggests a risk the screen missed; say why in reasons.
2. If anything suggests suicide or self-harm, choose "emergency" and mention 000 and Lifeline 13 11 14 in patient_message.
3. When unsure between two levels, choose the more urgent one.
4. patient_message: warm, plain English at a Year 8 reading level, max 60 words, no diagnosis, Australian spelling.
5. reception_summary: max 45 words in clinical shorthand for staff: age, key symptoms, duration, severity, flags, booking.
6. reasons: 1-3 short phrases explaining the decision.

Return only JSON matching:
{"urgency":"emergency|urgent|routine|telehealth|selfcare","appointment":"none|standard15|long30|telehealth15|nurse","reasons":["..."],"patient_message":"...","reception_summary":"...","escalated":true|false}"""


class AIError(Exception):
    pass


class GeminiClient:
    def __init__(self, api_key=None, model=None, timeout=20):
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    @property
    def enabled(self):
        return bool(self.api_key)

    def generate(self, system, contents, json_mode=False):
        if not self.enabled:
            raise AIError("No Gemini API key set")

        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.2},
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        try:
            resp = requests.post(
                GEMINI_URL.format(model=self.model),
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                json=body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AIError(f"Could not reach Gemini: {exc.__class__.__name__}") from exc

        if resp.status_code != 200:
            try:
                detail = resp.json().get("error", {}).get("message", "")
            except ValueError:
                detail = ""
            raise AIError(f"Gemini returned {resp.status_code}" + (f": {detail}" if detail else ""))

        try:
            parts = resp.json()["candidates"][0]["content"]["parts"]
        except (ValueError, KeyError, IndexError) as exc:
            raise AIError("Gemini returned an unexpected response") from exc

        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise AIError("Gemini returned an empty answer")
        return text


def parse_triage_answer(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise AIError("AI answer was not JSON")
    try:
        answer = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AIError("AI answer was not valid JSON") from exc
    if answer.get("urgency") not in LEVELS:
        raise AIError("AI chose an unknown urgency level")
    if answer.get("appointment") not in APPOINTMENTS:
        answer["appointment"] = None
    return answer


def build_ai_input(intake, rules_result):
    return {
        "form": {
            "age": intake.age,
            "request_type": REQUEST_TYPES[intake.request_type],
            "description": intake.symptoms,
            "duration": DURATIONS[intake.duration],
            "severity_0_to_10": intake.severity,
            "pregnant": intake.pregnant,
            "ongoing_condition": intake.chronic,
            "ticked_red_flags": intake.flags,
        },
        "safety_screen": {
            "level": rules_result.level,
            "reasons": [r["text"] for r in rules_result.reasons],
        },
    }


def merge(rules_result, answer):
    """Combine the rules result with the AI answer. The AI may raise urgency but never lower it."""
    result = rules_result
    result.source = "ai"
    ai_level = answer["urgency"]
    final = more_urgent(rules_result.level, ai_level)

    if LEVELS[ai_level]["rank"] > LEVELS[rules_result.level]["rank"]:
        result.add(f"AI suggested {LEVELS[ai_level]['short']}, kept {LEVELS[rules_result.level]['short']} "
                   f"because the safety rules rank it higher", "guard")

    for reason in (answer.get("reasons") or [])[:3]:
        result.add(str(reason), "ai")

    if final != rules_result.level:
        result.level = final
        result.escalated = True

    if result.level == "emergency":
        result.appointment = "none"
    elif result.level == "selfcare":
        result.appointment = "pharmacist"
    elif answer.get("appointment") not in (None, "none", "pharmacist") and final == ai_level:
        result.appointment = answer["appointment"]
    elif result.appointment in ("none", "pharmacist"):
        result.appointment = "standard15"

    message = answer.get("patient_message")
    if message and (rules_result.level != "emergency" or "000" in message):
        result.message = str(message)
    if result.crisis and not re.search(r"13 ?11 ?14", result.message):
        result.message += " Lifeline: 13 11 14. Emergency: 000."

    if answer.get("reception_summary"):
        result.summary = str(answer["reception_summary"])
        if result.flags:
            result.summary += f" [FLAGS: {', '.join(result.flags).upper()}]"
    return result


def triage_with_ai(intake, client):
    result = triage(intake)
    if not client or not client.enabled:
        return result
    try:
        prompt = json.dumps(build_ai_input(intake, result))
        text = client.generate(TRIAGE_PROMPT, [{"role": "user", "parts": [{"text": prompt}]}], json_mode=True)
        return merge(result, parse_triage_answer(text))
    except AIError as exc:
        result.notice = f"AI unavailable ({exc}). Showing the rules result."
        return result
