import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from clinicpilot.ai import GeminiClient, triage_with_ai
from clinicpilot.clinic import CLINIC_NAME, CLINIC_PHONE, answer_question, knowledge_base
from clinicpilot.queue_store import QueueStore
from clinicpilot.rules import APPOINTMENTS, DURATIONS, LEVELS, RED_FLAGS, REQUEST_TYPES, Intake
from clinicpilot.settings import load_env_file

BASE_DIR = Path(__file__).resolve().parent


def create_app(client=None, queue_path=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.json.sort_keys = False

    client = client or GeminiClient()
    queue = QueueStore(queue_path or BASE_DIR / "data" / "queue.json")

    @app.get("/")
    def index():
        return send_from_directory(BASE_DIR / "static", "index.html")

    @app.get("/api/config")
    def config():
        return jsonify(
            ai_enabled=client.enabled,
            model=client.model,
            clinic={"name": CLINIC_NAME, "phone": CLINIC_PHONE, "knowledge_base": knowledge_base()},
            levels=LEVELS,
            appointments=APPOINTMENTS,
            request_types=REQUEST_TYPES,
            durations=DURATIONS,
            red_flags=[{"id": key, "label": label} for key, label, _ in RED_FLAGS],
        )

    @app.post("/api/triage")
    def run_triage():
        data = request.get_json(silent=True) or {}
        try:
            intake = Intake.from_dict(data)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        result = triage_with_ai(intake, client)
        return jsonify(intake={"name": intake.name, "age": intake.age, "request_type": intake.request_type,
                               "severity": intake.severity},
                       result=result.to_dict())

    @app.post("/api/chat")
    def chat():
        data = request.get_json(silent=True) or {}
        question = (data.get("message") or "").strip()
        if not question:
            return jsonify(error="Type a question first."), 400
        return jsonify(answer_question(question, data.get("history"), client))

    @app.get("/api/queue")
    def list_queue():
        return jsonify(queue.all())

    @app.post("/api/queue")
    def add_to_queue():
        try:
            entry = queue.add(request.get_json(silent=True) or {})
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(entry), 201

    @app.delete("/api/queue/<entry_id>")
    def remove_from_queue(entry_id):
        if not queue.remove(entry_id):
            return jsonify(error="Request not found."), 404
        return "", 204

    @app.delete("/api/queue")
    def clear_queue():
        queue.clear()
        return "", 204

    @app.post("/api/queue/examples")
    def reload_examples():
        queue.reload_examples()
        return jsonify(queue.all())

    @app.get("/api/queue.csv")
    def export_queue():
        return Response(queue.to_csv(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=reception_queue.csv"})

    return app


load_env_file()
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    if os.getenv("GEMINI_API_KEY"):
        mode = "AI mode: rules + Gemini"
    else:
        mode = "Rules only. Add GEMINI_API_KEY to a .env file to turn on AI"
    print(f"\nClinicPilot is running. Open http://127.0.0.1:{port} in your browser.\n{mode}\n")
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=port, debug=False)
