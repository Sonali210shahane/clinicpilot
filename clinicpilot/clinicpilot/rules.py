import re
from dataclasses import dataclass, field, asdict

LEVELS = {
    "emergency": {"rank": 0, "title": "Call 000 now", "short": "Emergency",
                  "wait": "Now. Do not wait for a GP appointment."},
    "urgent": {"rank": 1, "title": "See a GP today", "short": "Same-day",
               "wait": "Same-day slot, within 4 hours"},
    "routine": {"rank": 2, "title": "Routine GP appointment", "short": "Routine",
                "wait": "Within 1-3 days"},
    "telehealth": {"rank": 3, "title": "Telehealth is suitable", "short": "Telehealth",
                   "wait": "Next phone or video slot"},
    "selfcare": {"rank": 4, "title": "Pharmacist first", "short": "Self-care",
                 "wait": "Pharmacist today; book a GP if not better in 3-5 days"},
}

APPOINTMENTS = {
    "none": "No booking - call 000",
    "pharmacist": "Pharmacist, no GP booking",
    "standard15": "Standard 15 min",
    "long30": "Long 30 min",
    "telehealth15": "Telehealth 15 min",
    "nurse": "Nurse 20 min",
}

REQUEST_TYPES = {
    "new": "New problem",
    "followup": "Follow-up",
    "script": "Repeat script",
    "results": "Test results",
    "certificate": "Med certificate",
    "referral": "Referral",
    "vaccine": "Vaccination",
}

DURATIONS = {
    "lt24": "<24 h",
    "1to3": "1-3 days",
    "4to7": "4-7 days",
    "gt7": ">1 week",
    "na": "n/a",
}

ADMIN_TYPES = {"script", "results", "certificate", "referral"}

RED_FLAGS = [
    ("chest", "Chest pain, pressure or tightness",
     r"chest[^.]{0,25}(pain|pressure|tight|heav)|(pain|pressure|tight\w*|heav\w*)[^.]{0,25}chest"
     r"|crushing|(down|in) (my )?left arm"),
    ("breath", "Struggling to breathe",
     r"can'?t breathe|cannot breathe|struggling to breathe|severe(ly)? short(ness)? of breath"
     r"|gasping|blue lips"),
    ("stroke", "Face drooping, arm weakness or slurred speech",
     r"face droop|slurr|arm weakness|stroke|numb(ness)? (on )?one side"),
    ("conscious", "Fainted, collapsed or had a seizure",
     r"faint|passed out|unconscious|collapse|seizure|fitting"),
    ("bleed", "Heavy bleeding that won't stop",
     r"bleeding (heavily|a lot|won'?t stop)|heavy bleeding|cough(ing)? (up )?blood|vomit(ing)? blood"),
    ("allergy", "Swelling of face, lips or throat",
     r"anaphyla|throat (is )?(swelling|closing|tight)|swollen (tongue|throat|lips)"),
    ("meningo", "Fever with stiff neck or a rash that doesn't fade",
     r"stiff neck|rash (that )?(doesn'?t|does not|won'?t) fade|purple rash"),
    ("headache", "Sudden, worst-ever headache",
     r"worst headache|thunderclap|sudden(,)? severe headache"),
    ("selfharm", "Thoughts of suicide or self-harm",
     r"suicid|kill myself|end my life|end(ing)? it all|don'?t want to (live|be here)"
     r"|self[- ]?harm|hurt(ing)? myself|overdos"),
]
RED_FLAGS = [(key, label, re.compile(pattern, re.I)) for key, label, pattern in RED_FLAGS]
RED_FLAG_IDS = {key for key, _, _ in RED_FLAGS}

URGENT_WORDS = re.compile(
    r"fever|temperature|vomit|diarrh|infect|burn|\bcut\b|wound|asthma|wheez|ear ?ache|ear pain"
    r"|painful ear|urin|\buti\b|abdominal pain|stomach pain|tummy pain|swollen|sprain|fracture"
    r"|broken|dehydrat", re.I)
FEVER_WORDS = re.compile(r"fever|temperature|hot to touch|3[89](\.\d)?\s*°?c?", re.I)
COLD_WORDS = re.compile(r"\bcold\b|runny nose|sore throat|sneez|cough|hay ?fever|blocked nose|sniffl", re.I)
MENTAL_WORDS = re.compile(r"anxi|depress|stress|low mood|panic|can'?t sleep|insomnia|mental health"
                          r"|burn ?out|grief", re.I)
CHRONIC_WORDS = re.compile(r"diabet|blood pressure|hypertension|heart|copd|kidney|asthma|epilep", re.I)
PREGNANCY_RISK_WORDS = re.compile(r"bleed|abdominal|stomach|tummy|cramp|pain|baby (isn'?t|not) moving", re.I)

MESSAGES = {
    "urgent": "We'd like a GP to see you today. Reception will offer you the next same-day slot. "
              "If you get much worse before then, call 000.",
    "routine": "A regular GP appointment in the next few days is right for this. "
               "If anything changes or gets worse, contact us sooner.",
    "telehealth": "This can be done by phone or video, so you don't need to come in. "
                  "We'll offer you the next telehealth slot.",
    "selfcare": "This sounds mild. A pharmacist can help today with simple remedies. "
                "If you're not improving in 3-5 days, or feel worse, book a GP.",
    "emergency": "What you've described could be serious. Please call 000 now or go to the nearest "
                 "emergency department. Don't wait for a GP appointment.",
    "crisis": "Thank you for telling us. Your safety matters most right now. If you might act on these "
              "thoughts, call 000 now. You can also talk to Lifeline any time on 13 11 14.",
}


@dataclass
class Intake:
    age: int
    symptoms: str
    request_type: str = "new"
    duration: str = "1to3"
    severity: int = 3
    name: str = ""
    flags: list = field(default_factory=list)
    pregnant: bool = False
    chronic: bool = False

    @classmethod
    def from_dict(cls, data):
        try:
            age = int(data.get("age"))
        except (TypeError, ValueError):
            raise ValueError("Age is required and must be a whole number.")
        if not 0 <= age <= 120:
            raise ValueError("Age must be between 0 and 120.")

        try:
            severity = int(data.get("severity", 3))
        except (TypeError, ValueError):
            raise ValueError("Severity must be a number from 0 to 10.")
        severity = max(0, min(10, severity))

        request_type = data.get("request_type") or data.get("type") or "new"
        if request_type not in REQUEST_TYPES:
            raise ValueError(f"Unknown request type: {request_type}")

        duration = data.get("duration") or "na"
        if duration not in DURATIONS:
            raise ValueError(f"Unknown duration: {duration}")

        flags = [f for f in (data.get("flags") or []) if f in RED_FLAG_IDS]
        symptoms = (data.get("symptoms") or "").strip()
        if not symptoms and not flags:
            raise ValueError("Describe the symptoms or request.")

        return cls(
            age=age,
            symptoms=symptoms,
            request_type=request_type,
            duration=duration,
            severity=severity,
            name=(data.get("name") or "").strip() or "Unnamed patient",
            flags=flags,
            pregnant=bool(data.get("pregnant")),
            chronic=bool(data.get("chronic")),
        )


@dataclass
class TriageResult:
    level: str
    appointment: str
    message: str = ""
    summary: str = ""
    reasons: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    crisis: bool = False
    source: str = "rules"
    escalated: bool = False
    notice: str = ""

    def add(self, text, source="rule"):
        self.reasons.append({"text": text, "source": source})

    def to_dict(self):
        data = asdict(self)
        info = LEVELS[self.level]
        data.update(title=info["title"], short=info["short"], wait=info["wait"],
                    appointment_label=APPOINTMENTS[self.appointment])
        return data


def more_urgent(a, b):
    return a if LEVELS[a]["rank"] <= LEVELS[b]["rank"] else b


def find_red_flags(intake):
    found = []
    for key, label, pattern in RED_FLAGS:
        ticked = key in intake.flags
        if ticked or pattern.search(intake.symptoms):
            found.append((key, label, ticked))
    return found


def triage(intake):
    text = intake.symptoms
    result = TriageResult(level="routine", appointment="standard15")

    red_flags = find_red_flags(intake)
    if red_flags:
        result.level = "emergency"
        result.appointment = "none"
        result.flags = [key for key, _, _ in red_flags]
        for _, label, ticked in red_flags:
            where = "ticked" if ticked else "found in description"
            result.add(f"Red flag: {label} ({where})")
        result.crisis = "selfharm" in result.flags
        result.message = MESSAGES["crisis" if result.crisis else "emergency"]
        result.summary = build_summary(intake, result)
        return result

    sev = intake.severity
    age = intake.age
    mental = bool(MENTAL_WORDS.search(text))
    chronic = intake.chronic or bool(CHRONIC_WORDS.search(text))

    if intake.request_type == "vaccine":
        result.appointment = "nurse"
        result.add("Vaccination goes to a nurse appointment")

    elif intake.request_type in ADMIN_TYPES:
        result.level = "telehealth"
        result.appointment = "telehealth15"
        result.add(f"{REQUEST_TYPES[intake.request_type]} can usually be handled by phone or video")
        if sev >= 5:
            result.level = "routine"
            result.appointment = "standard15"
            result.add(f"Severity {sev}/10 with symptoms, so an in-person visit is safer")

    else:
        if sev >= 8:
            result.level = "urgent"
            result.add(f"Severity {sev}/10")
        if age < 1 and FEVER_WORDS.search(text):
            result.level = "urgent"
            result.add("Baby under 12 months with a fever")
        if age >= 75 and sev >= 5:
            result.level = "urgent"
            result.add("Age 75+ with moderate or worse symptoms")
        if intake.pregnant and PREGNANCY_RISK_WORDS.search(text):
            result.level = "urgent"
            result.add("Pregnant with pain, bleeding or cramping")
        if URGENT_WORDS.search(text) and sev >= 5:
            result.level = "urgent"
            result.add(f"Symptoms that may need treatment today (e.g. infection, fever, injury) "
                       f"at severity {sev}/10")
        if intake.duration == "lt24" and sev >= 6 and result.level != "urgent":
            result.level = "urgent"
            result.add(f"New problem under 24 hours at severity {sev}/10")

        if result.level == "routine":
            minor = (COLD_WORDS.search(text) and sev <= 3 and intake.duration in ("lt24", "1to3")
                     and not chronic and not intake.pregnant and 2 <= age < 75)
            if minor:
                result.level = "selfcare"
                result.appointment = "pharmacist"
                result.add("Mild, short-lived cold-type symptoms in a low-risk age group")
            elif intake.request_type == "followup" and sev <= 4:
                result.level = "telehealth"
                result.appointment = "telehealth15"
                result.add("Stable follow-up at low severity")
            else:
                result.add("New or ongoing problem without urgent features")

        if mental and result.level != "selfcare":
            result.appointment = "telehealth15" if result.level == "telehealth" else "long30"
            result.add("Mental health concern: longer consult allows a proper conversation and care plan")
        elif chronic and intake.request_type == "new" and result.appointment == "standard15":
            result.appointment = "long30"
            result.add("Ongoing condition plus a new problem: longer consult")

    result.message = MESSAGES[result.level]
    result.summary = build_summary(intake, result)
    return result


def build_summary(intake, result):
    details = f"{intake.age}y"
    if intake.pregnant:
        details += " pregnant"
    if intake.chronic:
        details += " w/ chronic cond."
    flags = f" FLAGS: {', '.join(result.flags).upper()}." if result.flags else ""
    return (f'{details}. {REQUEST_TYPES[intake.request_type]}. "{intake.symptoms[:140]}". '
            f"Dur {DURATIONS[intake.duration]}, sev {intake.severity}/10.{flags} "
            f"-> {LEVELS[result.level]['short'].upper()}, {APPOINTMENTS[result.appointment]}.")
