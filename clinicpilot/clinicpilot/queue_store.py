import csv
import io
import json
import threading
import time
import uuid
from pathlib import Path

from .rules import APPOINTMENTS, LEVELS, REQUEST_TYPES

EXAMPLES = [
    {"name": "Ken W.", "age": 79, "request_type": "new", "level": "urgent", "appointment": "standard15",
     "severity": 6, "source": "rules", "minutes_ago": 48,
     "summary": '79y. New problem. "Burning when passing urine, confused this morning per daughter". '
                "Dur 1-3 days, sev 6/10. -> SAME-DAY, Standard 15 min."},
    {"name": "Aisha N.", "age": 31, "request_type": "new", "level": "routine", "appointment": "long30",
     "severity": 4, "source": "ai", "minutes_ago": 35,
     "summary": "31y. Low mood and poor sleep 6 wks, no self-harm thoughts. Requests mental health care plan. "
                "-> ROUTINE, Long 30 min."},
    {"name": "Tom B.", "age": 45, "request_type": "certificate", "level": "telehealth",
     "appointment": "telehealth15", "severity": 2, "source": "rules", "minutes_ago": 22,
     "summary": '45y. Med certificate. "Gastro yesterday, better now, need a certificate for work". '
                "Dur 1-3 days, sev 2/10. -> TELEHEALTH, Telehealth 15 min."},
    {"name": "Lily P. (infant)", "age": 0, "request_type": "new", "level": "urgent", "appointment": "standard15",
     "severity": 5, "source": "rules", "minutes_ago": 12,
     "summary": '0y. New problem. "Temperature 38.2, 9 months old, unsettled". Dur <24 h, sev 5/10. '
                "-> SAME-DAY, Standard 15 min."},
    {"name": "Ray D.", "age": 52, "request_type": "vaccine", "level": "routine", "appointment": "nurse",
     "severity": 0, "source": "rules", "minutes_ago": 6,
     "summary": '52y. Vaccination. "Flu shot". Dur n/a, sev 0/10. -> ROUTINE, Nurse 20 min.'},
]

FIELDS = ("name", "age", "request_type", "level", "appointment", "severity", "summary", "source")


def priority_key(entry):
    return (LEVELS[entry["level"]]["rank"], -int(entry.get("severity", 0)), entry["received"])


class QueueStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write(self._examples())

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _write(self, entries):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _examples():
        now = time.time()
        entries = []
        for ex in EXAMPLES:
            entry = {k: ex[k] for k in FIELDS}
            entry.update(id=uuid.uuid4().hex[:12], received=now - ex["minutes_ago"] * 60, example=True)
            entries.append(entry)
        return entries

    def all(self):
        with self.lock:
            return sorted(self._read(), key=priority_key)

    def add(self, data):
        level = data.get("level")
        appointment = data.get("appointment")
        if level not in LEVELS or appointment not in APPOINTMENTS:
            raise ValueError("Queue entry needs a valid level and appointment.")
        entry = {k: data.get(k, "") for k in FIELDS}
        entry["severity"] = int(data.get("severity") or 0)
        entry.update(id=uuid.uuid4().hex[:12], received=time.time(), example=False)
        with self.lock:
            entries = self._read()
            entries.append(entry)
            self._write(entries)
        return entry

    def remove(self, entry_id):
        with self.lock:
            entries = self._read()
            kept = [e for e in entries if e["id"] != entry_id]
            self._write(kept)
            return len(kept) < len(entries)

    def clear(self):
        with self.lock:
            self._write([])

    def reload_examples(self):
        with self.lock:
            entries = [e for e in self._read() if not e.get("example")]
            self._write(entries + self._examples())

    def to_csv(self):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["priority", "received", "patient", "age", "request", "booking", "source", "summary"])
        for e in self.all():
            writer.writerow([
                LEVELS[e["level"]]["short"],
                time.strftime("%Y-%m-%d %H:%M", time.localtime(e["received"])),
                e["name"], e["age"], REQUEST_TYPES.get(e["request_type"], e["request_type"]),
                APPOINTMENTS[e["appointment"]], e["source"], e["summary"],
            ])
        return out.getvalue()
