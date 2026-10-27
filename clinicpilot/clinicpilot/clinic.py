import re

from .ai import AIError
from .rules import RED_FLAGS

CLINIC_NAME = "Harbourview 7-Day Medical"
CLINIC_PHONE = "(07) 5550 4123"

KNOWLEDGE_BASE = [
    ("Opening hours",
     r"hour|open|close|weekend|saturday|sunday|public holiday|christmas|time",
     "We're open 7am to 10pm, 7 days a week, including public holidays (9am-5pm on Christmas Day)."),
    ("Location and parking",
     r"where|address|location|park|find you|bus|train",
     "12 Esplanade, Harbourview QLD 4217. Free 2-hour parking behind the building, entry from Pier Lane. "
     "Bus stop 50 m away."),
    ("Fees and bulk billing",
     r"fee|cost|price|bulk|bill|medicare|pay|charge|concession|gap|how much",
     "Children under 16 and concession card holders are bulk billed (no fee). Other standard consults are $95; "
     "the Medicare rebate is paid straight back to your account on the day."),
    ("Booking and cancelling",
     r"book|appointment|cancel|reschedul|walk.?in|wait",
     f"Book online, by phone on {CLINIC_PHONE}, or walk in. Same-day appointments are kept free each day for "
     "urgent problems. Please cancel at least 2 hours ahead."),
    ("Telehealth",
     r"tele|video|phone consult|online consult|remote",
     "Phone and video consults are available for repeat scripts, results, certificates, referrals and stable "
     "follow-ups. You need to have seen one of our GPs in the last 12 months."),
    ("Prescriptions and certificates",
     r"script|prescription|repeat|medication|certificate|sick note|med cert",
     "Repeat scripts and medical certificates need a short consult (telehealth is fine). eScripts are sent to "
     "your phone by SMS."),
    ("Vaccinations",
     r"vaccin|flu shot|immunis|jab|travel",
     "Our nurses give flu, childhood and travel vaccines. Book a nurse appointment; flu shots are free for "
     "eligible groups."),
    ("After hours",
     r"after.?hours|night|late|midnight|closed",
     "After 10pm call Healthdirect on 1800 022 222 for nurse advice, or 000 in an emergency."),
]
KNOWLEDGE_BASE = [(title, re.compile(pattern, re.I), answer) for title, pattern, answer in KNOWLEDGE_BASE]

SYMPTOM_WORDS = re.compile(r"pain|sick|hurt|fever|symptom|rash|cough|unwell", re.I)


def chat_prompt():
    facts = "\n".join(f"- {title}: {answer}" for title, _, answer in KNOWLEDGE_BASE)
    return f"""You are the front-desk assistant for {CLINIC_NAME}, an Australian GP clinic. Answer ONLY using the clinic information below. If the answer is not there, say you don't have that information and give the phone number {CLINIC_PHONE}.
Never give medical advice or diagnose. If the person describes symptoms, suggest they use the "Patient intake" tab or call reception. If they describe an emergency (chest pain, trouble breathing, stroke signs, severe bleeding, collapse) tell them to call 000 now. If they mention suicide or self-harm, give 000 and Lifeline 13 11 14 with kindness.
Keep answers under 80 words, friendly, Australian English, plain text without markdown.

CLINIC INFORMATION:
{facts}"""


def red_flag_in(text):
    for key, _, pattern in RED_FLAGS:
        if pattern.search(text):
            return key
    return None


def faq_answer(question):
    flag = red_flag_in(question)
    if flag == "selfharm":
        return ("I'm really glad you reached out. If you're in danger right now, please call 000. You can talk "
                f"to Lifeline any time on 13 11 14. Our GPs can also help, call us on {CLINIC_PHONE}."), True
    if flag:
        return "That could be an emergency. Please call 000 now or go to the nearest emergency department.", True

    hits = [answer for _, pattern, answer in KNOWLEDGE_BASE if pattern.search(question)]
    if hits:
        return "\n\n".join(hits[:2]), False
    if SYMPTOM_WORDS.search(question):
        return ("I can't give medical advice, but I can get you to the right appointment. Use the Patient intake "
                f"tab, or call reception on {CLINIC_PHONE}."), False
    return f"I don't have that information. Reception can help on {CLINIC_PHONE}.", False


def answer_question(question, history=None, client=None):
    alert = red_flag_in(question) is not None
    if client and client.enabled:
        contents = []
        for turn in (history or [])[-6:]:
            role = "model" if turn.get("role") in ("bot", "model", "assistant") else "user"
            if turn.get("text"):
                contents.append({"role": role, "parts": [{"text": str(turn["text"])}]})
        contents.append({"role": "user", "parts": [{"text": question}]})
        try:
            text = client.generate(chat_prompt(), contents)
            return {"answer": text, "source": "Gemini", "alert": alert}
        except AIError as exc:
            answer, alert = faq_answer(question)
            return {"answer": answer, "source": "Clinic FAQ", "alert": alert,
                    "notice": f"AI unavailable ({exc}). Answered from the clinic FAQ."}

    answer, alert = faq_answer(question)
    return {"answer": answer, "source": "Clinic FAQ", "alert": alert}


def knowledge_base():
    return [{"title": title, "answer": answer} for title, _, answer in KNOWLEDGE_BASE]
