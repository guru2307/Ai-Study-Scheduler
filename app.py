"""
AI Study Scheduler - Flask backend.

Architecture:
    Frontend (HTML/CSS/JS)
        -> Flask backend (this file + helper modules)
        -> AI API (Anthropic Claude, via ai_service.py, key from env var)
        -> Flask backend
        -> Frontend

The AI API key is NEVER exposed to the frontend - all AI calls happen
server-side in ai_service.py.
"""
import os
import json
import datetime
import traceback
import socket

from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

import db
import ai_service
import document_processor
import scheduler

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
MAX_UPLOAD_MB = 10

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)

db.init_db()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def error_response(message, status=400):
    return jsonify({"success": False, "error": message}), status

def ok_response(data, status=200):
    payload = {"success": True}
    payload.update(data)
    return jsonify(payload), status

@app.errorhandler(413)
def too_large(e):
    return error_response(f"File is too large. Max size is {MAX_UPLOAD_MB} MB.", 413)

@app.errorhandler(500)
def internal_error(e):
    return error_response("An unexpected server error occurred. Please try again.", 500)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/manifest.json")
def manifest():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "manifest.json", mimetype="application/manifest+json")

@app.route("/sw.js")
def service_worker():
    response = send_from_directory(os.path.join(BASE_DIR, "static"), "sw.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(BASE_DIR, "static", "icons"), "favicon-32.png", mimetype="image/png")

@app.route("/api/mobile-info", methods=["GET"])
def mobile_info():
    ip = get_local_ip()
    port = request.host.split(":")[-1] if ":" in request.host else "5000"
    return ok_response({
        "local_ip": ip,
        "mobile_url": f"http://{ip}:{port}"
    })

@app.route("/api/analyze-subject", methods=["POST"])
def analyze_subject():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    topic = (data.get("topic") or "").strip()
    deadline = (data.get("deadline") or "").strip()
    knowledge_level = (data.get("knowledge_level") or "").strip()
    difficulty = (data.get("difficulty") or "Auto Detect").strip()
    estimated_hours = data.get("estimated_hours")
    notes = (data.get("notes") or "").strip()

    if not name or not topic or not deadline or not knowledge_level:
        return error_response("Subject name, topic, deadline, and knowledge level are required.")

    try:
        datetime.date.fromisoformat(deadline)
    except ValueError:
        return error_response("Deadline must be a valid date (YYYY-MM-DD).")

    try:
        estimated_hours_val = float(estimated_hours) if estimated_hours not in (None, "") else None
    except (ValueError, TypeError):
        return error_response("Estimated hours must be a number.")

    analysis = ai_service.analyze_subject(
        subject=name, topic=topic, deadline=deadline, knowledge_level=knowledge_level,
        difficulty=difficulty, estimated_hours=estimated_hours_val, notes=notes,
    )

    try:
        with db.db_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO subjects
                   (name, topic, deadline, knowledge_level, difficulty, difficulty_reason,
                    estimated_hours, hours_reason, priority_score, priority_level, priority_reason,
                    study_techniques, study_tip, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    name, topic, deadline, knowledge_level,
                    analysis["difficulty"], analysis.get("difficulty_reason", ""),
                    analysis["estimated_hours"], analysis.get("hours_reason", ""),
                    analysis["priority_score"], analysis["priority_level"], analysis.get("priority_reason", ""),
                    json.dumps(analysis.get("study_techniques", [])), analysis.get("study_tip", ""),
                    notes,
                ),
            )
            new_id = cur.lastrowid
    except Exception:
        traceback.print_exc()
        return error_response("Could not save the subject to the database.", 500)

    subject = _get_subject_dict(new_id)
    return ok_response({
        "subject": subject,
        "ai_used": analysis.get("ai_used", False),
        "warning": None if analysis.get("ai_used") else "AI was unavailable, so this analysis was estimated automatically.",
    })

def _get_subject_dict(subject_id):
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
        row = db.row_to_dict(cur.fetchone())
    if row:
        row["study_techniques"] = db.json_loads_safe(row.get("study_techniques"))
    return row

@app.route("/api/subjects", methods=["GET"])
def get_subjects():
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM subjects ORDER BY priority_score DESC, deadline ASC")
        rows = db.rows_to_list(cur.fetchall())
    for r in rows:
        r["study_techniques"] = db.json_loads_safe(r.get("study_techniques"))
    return ok_response({"subjects": rows})

@app.route("/api/subjects/<int:subject_id>", methods=["DELETE"])
def delete_subject(subject_id):
    try:
        with db.db_cursor(commit=True) as cur:
            cur.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
            cur.execute("DELETE FROM sessions WHERE subject_id = ?", (subject_id,))
        return ok_response({"deleted_id": subject_id})
    except Exception:
        traceback.print_exc()
        return error_response("Could not delete the subject.", 500)

@app.route("/api/preferences", methods=["GET"])
def get_preferences():
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM preferences WHERE id = 1")
        row = db.row_to_dict(cur.fetchone())
    return ok_response({"preferences": row})

@app.route("/api/preferences", methods=["POST"])
def set_preferences():
    data = request.get_json(silent=True) or {}
    hours_per_day = data.get("hours_per_day")
    session_length = data.get("session_length")
    start_date = data.get("start_date")
    preferred_time = data.get("preferred_time")

    try:
        hours_per_day = float(hours_per_day)
        if not (1 <= hours_per_day <= 16):
            raise ValueError
    except (ValueError, TypeError):
        return error_response("Study hours per day must be a number between 1 and 16.")

    if session_length not in ("30 minutes", "1 hour", "1.5 hours", "2 hours"):
        return error_response("Invalid session length.")
    if preferred_time not in ("Morning", "Afternoon", "Evening"):
        return error_response("Invalid preferred study time.")
    try:
        datetime.date.fromisoformat(start_date)
    except (ValueError, TypeError):
        return error_response("Start date must be a valid date (YYYY-MM-DD).")

    with db.db_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE preferences SET hours_per_day=?, session_length=?, start_date=?, preferred_time=?
               WHERE id = 1""",
            (hours_per_day, session_length, start_date, preferred_time),
        )
    return ok_response({"message": "Preferences saved."})

@app.route("/api/generate-schedule", methods=["POST"])
def generate_schedule():
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM subjects ORDER BY priority_score DESC, deadline ASC")
        subjects = db.rows_to_list(cur.fetchall())
        cur.execute("SELECT * FROM preferences WHERE id = 1")
        prefs = db.row_to_dict(cur.fetchone())

    if not subjects:
        return error_response("Add at least one subject before generating a schedule.")

    for s in subjects:
        s["study_techniques"] = db.json_loads_safe(s.get("study_techniques"))

    conflicts = scheduler.check_conflicts(subjects, prefs)

    try:
        sessions = scheduler.generate_schedule(subjects, prefs)
    except Exception:
        traceback.print_exc()
        return error_response("Could not generate a schedule with the current subjects and preferences.", 500)

    if not sessions:
        return error_response(
            "No sessions could be scheduled. Check that deadlines are in the future.",
            status=409 if conflicts else 400,
        )

    try:
        with db.db_cursor(commit=True) as cur:
            cur.execute("DELETE FROM sessions")
            cur.execute("UPDATE subjects SET completed_hours = 0")
            for s in sessions:
                cur.execute(
                    """INSERT INTO sessions
                       (subject_id, date, start_time, end_time, subject_name, topic,
                        duration_minutes, priority_level, technique, is_break, completed)
                       VALUES (?,?,?,?,?,?,?,?,?,?,0)""",
                    (
                        s["subject_id"], s["date"], s["start_time"], s["end_time"],
                        s["subject_name"], s["topic"], s["duration_minutes"],
                        s["priority_level"], s["technique"], int(s["is_break"]),
                    ),
                )
    except Exception:
        traceback.print_exc()
        return error_response("Could not save the generated schedule.", 500)

    return ok_response({
        "message": "Schedule generated successfully.",
        "session_count": len(sessions),
        "conflicts": conflicts,
        "has_conflicts": len(conflicts) > 0,
    })

@app.route("/api/schedule", methods=["GET"])
def get_schedule():
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM sessions ORDER BY date ASC, id ASC")
        rows = db.rows_to_list(cur.fetchall())

    days = {}
    for r in rows:
        d = r["date"]
        if d not in days:
            days[d] = {"date": d, "sessions": [], "total_minutes": 0, "session_count": 0, "completed_count": 0}
        days[d]["sessions"].append(r)
        if not r["is_break"]:
            days[d]["total_minutes"] += r["duration_minutes"]
            days[d]["session_count"] += 1
            if r["completed"]:
                days[d]["completed_count"] += 1

    ordered_days = [days[d] for d in sorted(days.keys())]
    for d in ordered_days:
        d["total_hours"] = round(d["total_minutes"] / 60, 2)

    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM subjects")
        subjects = db.rows_to_list(cur.fetchall())
        cur.execute("SELECT * FROM preferences WHERE id = 1")
        prefs = db.row_to_dict(cur.fetchone())
    for s in subjects:
        s["study_techniques"] = db.json_loads_safe(s.get("study_techniques"))
    conflicts = scheduler.check_conflicts(subjects, prefs) if subjects and prefs else []

    return ok_response({"days": ordered_days, "conflicts": conflicts, "has_conflicts": len(conflicts) > 0})

@app.route("/api/sessions/<int:session_id>/complete", methods=["POST"])
def complete_session(session_id):
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = db.row_to_dict(cur.fetchone())

    if not session:
        return error_response("Session not found.", 404)
    if session["is_break"]:
        return error_response("Breaks cannot be marked as completed.")

    new_state = 0 if session["completed"] else 1

    with db.db_cursor(commit=True) as cur:
        cur.execute("UPDATE sessions SET completed = ? WHERE id = ?", (new_state, session_id))

        if session["subject_id"] is not None:
            hours_delta = session["duration_minutes"] / 60.0
            hours_delta = hours_delta if new_state == 1 else -hours_delta
            cur.execute(
                "UPDATE subjects SET completed_hours = MAX(0, completed_hours + ?) WHERE id = ?",
                (hours_delta, session["subject_id"]),
            )

    return ok_response({"session_id": session_id, "completed": bool(new_state)})

@app.route("/api/upload-notes", methods=["POST"])
def upload_notes():
    if "file" not in request.files:
        return error_response("No file was uploaded.")

    file = request.files["file"]
    subject_name = (request.form.get("subject_name") or "").strip()
    topic = (request.form.get("topic") or "").strip()
    subject_id = request.form.get("subject_id")

    if file.filename == "":
        return error_response("No file was selected.")
    if not document_processor.allowed_file(file.filename):
        return error_response("Unsupported file type. Please upload a PDF, DOCX, or TXT file.")

    filename = secure_filename(file.filename)
    unique_name = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    filepath = os.path.join(UPLOAD_DIR, unique_name)

    try:
        file.save(filepath)
    except Exception:
        traceback.print_exc()
        return error_response("Could not save the uploaded file.", 500)

    try:
        text = document_processor.extract_text(filepath)
    except document_processor.DocumentProcessingError as e:
        return error_response(str(e))
    except Exception:
        traceback.print_exc()
        return error_response("An unexpected error occurred while reading the document.", 500)

    analysis = ai_service.analyze_document(text, subject_name, topic)

    try:
        with db.db_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO documents
                   (subject_id, subject_name, topic, filename, extracted_text,
                    important_topics, key_definitions, important_facts, revision_areas, analysis_error)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    subject_id or None, subject_name, topic, filename, text,
                    json.dumps(analysis.get("important_topics", [])),
                    json.dumps(analysis.get("key_definitions", [])),
                    json.dumps(analysis.get("important_facts", [])),
                    json.dumps(analysis.get("revision_areas", [])),
                    analysis.get("error"),
                ),
            )
            doc_id = cur.lastrowid
    except Exception:
        traceback.print_exc()
        return error_response("Could not save document analysis to the database.", 500)

    return ok_response({
        "document_id": doc_id,
        "filename": filename,
        "important_topics": analysis.get("important_topics", []),
        "key_definitions": analysis.get("key_definitions", []),
        "important_facts": analysis.get("important_facts", []),
        "revision_areas": analysis.get("revision_areas", []),
        "ai_used": analysis.get("ai_used", False),
        "warning": analysis.get("error"),
    })

@app.route("/api/documents", methods=["GET"])
def get_documents():
    with db.db_cursor() as cur:
        cur.execute("SELECT id, subject_id, subject_name, topic, filename, important_topics, "
                     "key_definitions, important_facts, revision_areas, analysis_error, created_at "
                     "FROM documents ORDER BY created_at DESC")
        rows = db.rows_to_list(cur.fetchall())
    for r in rows:
        r["important_topics"] = db.json_loads_safe(r.get("important_topics"))
        r["key_definitions"] = db.json_loads_safe(r.get("key_definitions"))
        r["important_facts"] = db.json_loads_safe(r.get("important_facts"))
        r["revision_areas"] = db.json_loads_safe(r.get("revision_areas"))
    return ok_response({"documents": rows})

@app.route("/api/generate-mcq", methods=["POST"])
def generate_mcq():
    data = request.get_json(silent=True) or {}
    document_id = data.get("document_id")
    num_questions = data.get("num_questions")

    if num_questions not in (5, 10, 20):
        return error_response("num_questions must be 5, 10, or 20.")
    if not document_id:
        return error_response("document_id is required.")

    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        doc = db.row_to_dict(cur.fetchone())

    if not doc:
        return error_response("Document not found.", 404)
    if not doc.get("extracted_text"):
        return error_response("This document has no extracted text to generate questions from.")

    result = ai_service.generate_mcqs(doc["extracted_text"], doc["subject_name"], doc["topic"], num_questions)

    if not result.get("questions"):
        return error_response(result.get("error") or "Could not generate questions from this document.", 502)

    try:
        with db.db_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO mock_tests (document_id, subject_name, topic, num_questions, questions)
                   VALUES (?,?,?,?,?)""",
                (document_id, doc["subject_name"], doc["topic"], len(result["questions"]),
                 json.dumps(result["questions"])),
            )
            test_id = cur.lastrowid
    except Exception:
        traceback.print_exc()
        return error_response("Could not save the generated mock test.", 500)

    return ok_response({
        "mock_test_id": test_id,
        "num_questions": len(result["questions"]),
        "requested_questions": result.get("requested", num_questions),
        "insufficient_material": result.get("insufficient_material", False),
        "ai_used": result.get("ai_used", False),
        "warning": result.get("error") if result.get("insufficient_material") else None,
    })

@app.route("/api/mock-tests", methods=["GET"])
def get_mock_tests():
    with db.db_cursor() as cur:
        cur.execute(
            """SELECT mt.id, mt.subject_name, mt.topic, mt.num_questions, mt.created_at,
                      d.filename as source_filename
               FROM mock_tests mt
               LEFT JOIN documents d ON mt.document_id = d.id
               ORDER BY mt.created_at DESC"""
        )
        rows = db.rows_to_list(cur.fetchall())
    return ok_response({"mock_tests": rows})

@app.route("/api/mock-tests/<int:test_id>", methods=["GET"])
def get_mock_test(test_id):
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM mock_tests WHERE id = ?", (test_id,))
        test = db.row_to_dict(cur.fetchone())

    if not test:
        return error_response("Mock test not found.", 404)

    questions = db.json_loads_safe(test.get("questions"))
    questions_for_test = [
        {"question": q["question"], "options": q["options"], "related_topic": q.get("related_topic", "")}
        for q in questions
    ]
    return ok_response({
        "id": test["id"], "subject_name": test["subject_name"], "topic": test["topic"],
        "num_questions": test["num_questions"], "questions": questions_for_test,
    })

@app.route("/api/submit-test", methods=["POST"])
def submit_test():
    data = request.get_json(silent=True) or {}
    test_id = data.get("mock_test_id")
    answers = data.get("answers")

    if not test_id or not isinstance(answers, list):
        return error_response("mock_test_id and answers (array) are required.")

    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM mock_tests WHERE id = ?", (test_id,))
        test = db.row_to_dict(cur.fetchone())

    if not test:
        return error_response("Mock test not found.", 404)

    questions = db.json_loads_safe(test.get("questions"))
    if len(answers) != len(questions):
        return error_response("Number of answers does not match number of questions.")

    results = []
    correct_count = 0
    for q, user_answer in zip(questions, answers):
        is_correct = user_answer is not None and user_answer == q["correct_answer"]
        if is_correct:
            correct_count += 1
        results.append({
            "question": q["question"],
            "options": q["options"],
            "user_answer": user_answer,
            "correct_answer": q["correct_answer"],
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
            "related_topic": q.get("related_topic", ""),
            "source_reference": q.get("source_reference", ""),
        })

    total = len(questions)
    wrong = total - correct_count
    percentage = round((correct_count / total) * 100, 1) if total else 0

    if percentage >= 85:
        performance = "Excellent"
    elif percentage >= 70:
        performance = "Good"
    elif percentage >= 50:
        performance = "Fair"
    else:
        performance = "Needs Improvement"

    try:
        with db.db_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO test_results
                   (mock_test_id, subject_name, topic, total_questions, correct_answers,
                    wrong_answers, score, percentage, performance, answers)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    test_id, test["subject_name"], test["topic"], total, correct_count,
                    wrong, correct_count, percentage, performance, json.dumps(results),
                ),
            )
            result_id = cur.lastrowid
    except Exception:
        traceback.print_exc()
        return error_response("Could not save the test result.", 500)

    return ok_response({
        "result_id": result_id,
        "total_questions": total,
        "correct_answers": correct_count,
        "wrong_answers": wrong,
        "score": correct_count,
        "percentage": percentage,
        "performance": performance,
        "results": results,
    })

@app.route("/api/progress", methods=["GET"])
def get_progress():
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM subjects ORDER BY priority_score DESC")
        subjects = db.rows_to_list(cur.fetchall())
        cur.execute("SELECT * FROM sessions WHERE is_break = 0")
        sessions = db.rows_to_list(cur.fetchall())
        cur.execute("SELECT * FROM test_results ORDER BY created_at DESC")
        test_results = db.rows_to_list(cur.fetchall())

    subject_progress = []
    total_planned = 0
    total_completed = 0
    for s in subjects:
        planned = float(s["estimated_hours"])
        completed = min(float(s["completed_hours"]), planned) if planned else float(s["completed_hours"])
        total_planned += planned
        total_completed += completed
        pct = round((completed / planned) * 100) if planned else 0
        subject_progress.append({
            "id": s["id"], "name": s["name"], "topic": s["topic"],
            "planned_hours": planned, "completed_hours": round(completed, 2),
            "remaining_hours": round(max(planned - completed, 0), 2),
            "completion_percentage": min(pct, 100),
            "priority_level": s["priority_level"],
        })

    completed_sessions = sum(1 for sess in sessions if sess["completed"])

    return ok_response({
        "subject_progress": subject_progress,
        "overall": {
            "total_planned_hours": round(total_planned, 2),
            "total_completed_hours": round(total_completed, 2),
            "completion_percentage": round((total_completed / total_planned) * 100) if total_planned else 0,
            "total_sessions": len(sessions),
            "completed_sessions": completed_sessions,
        },
        "mock_test_results": test_results,
    })

def _build_progress_chart(sessions):
    """
    Single-dataset: CUMULATIVE completed study hours per date.

    One data point per scheduled date.  The Y value is the running total of
    all hours the student has marked as complete up to and including that
    date.  Dates where nothing was completed yet still appear on the X-axis
    (carrying the previous cumulative total forward) so the line spans the
    whole schedule period.

    Returns has_data=False when no sessions have been completed at all so
    the frontend can show the empty state instead of a flat-zero graph.
    """
    if not sessions:
        return {"labels": [], "actual": [], "has_data": False}

    completed_by_date = {}
    for s in sessions:
        if s["completed"]:
            d = s["date"]
            completed_by_date[d] = completed_by_date.get(d, 0) + s["duration_minutes"]

    if not completed_by_date:
        return {"labels": [], "actual": [], "has_data": False}

    all_dates = sorted(set(s["date"] for s in sessions))

    labels, actual_cum = [], []
    running = 0.0
    for d in all_dates:
        running += completed_by_date.get(d, 0) / 60.0
        try:
            import datetime as _dt
            dt_obj = _dt.date.fromisoformat(d)
            label = dt_obj.strftime("%b") + " " + str(dt_obj.day)
        except ValueError:
            label = d[5:]
        labels.append(label)
        actual_cum.append(round(running, 2))

    return {"labels": labels, "actual": actual_cum, "has_data": True}

@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    with db.db_cursor() as cur:
        cur.execute("SELECT * FROM subjects")
        subjects = db.rows_to_list(cur.fetchall())
        cur.execute("SELECT * FROM sessions WHERE is_break = 0")
        sessions = db.rows_to_list(cur.fetchall())
        cur.execute("SELECT * FROM test_results ORDER BY created_at DESC")
        test_results = db.rows_to_list(cur.fetchall())

    total_planned_hours = sum(float(s["estimated_hours"]) for s in subjects)
    total_completed_hours = round(
        sum(s["duration_minutes"] / 60.0 for s in sessions if s["completed"]), 2
    )
    overall_pct = round((total_completed_hours / total_planned_hours) * 100) if total_planned_hours else 0

    priority_distribution = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    subject_hours = []
    for s in subjects:
        priority_distribution[s["priority_level"]] = priority_distribution.get(s["priority_level"], 0) + 1
        subject_hours.append({
            "name": s["name"], "topic": s["topic"],
            "planned_hours": float(s["estimated_hours"]),
            "completed_hours": round(min(float(s["completed_hours"]), float(s["estimated_hours"])), 2),
        })

    avg_score = None
    if test_results:
        avg_score = round(sum(r["percentage"] for r in test_results) / len(test_results), 1)

    progress_chart = _build_progress_chart(sessions)

    stats = {
        "total_planned_hours": round(total_planned_hours, 2),
        "total_completed_hours": round(total_completed_hours, 2),
        "overall_progress_percentage": overall_pct,
        "total_subjects": len(subjects),
        "critical_subjects": priority_distribution["CRITICAL"],
        "priority_distribution": priority_distribution,
        "subject_hours": subject_hours,
        "total_mock_tests_taken": len(test_results),
        "avg_test_score": avg_score,
        "total_sessions_completed": sum(1 for sess in sessions if sess["completed"]),
        "total_sessions": len(sessions),
        "progress_chart": progress_chart,
    }

    insights_result = ai_service.generate_insights(stats)
    stats["ai_insights"] = insights_result.get("insights", [])
    stats["insights_ai_used"] = insights_result.get("ai_used", False)

    return ok_response({"analytics": stats})

@app.route("/api/health", methods=["GET"])
def health():
    return ok_response({
        "status": "running",
        "ai_configured": bool(ai_service.AI_API_KEY),
        "ai_provider": ai_service.AI_PROVIDER,
        "ai_model": ai_service.AI_MODEL,
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
