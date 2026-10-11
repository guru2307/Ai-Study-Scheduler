"""
scheduler.py - builds a day-by-day study schedule from prioritized subjects
and the student's study preferences.
"""
import datetime
import math

SESSION_LENGTH_MINUTES = {
    "30 minutes": 30,
    "1 hour": 60,
    "1.5 hours": 90,
    "2 hours": 120,
}

BREAK_MINUTES = 15

PREFERRED_TIME_START = {
    "Morning": (9, 0),
    "Afternoon": (14, 0),
    "Evening": (18, 0),
}

PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

def _fmt_time(hour, minute):
    dt = datetime.time(hour % 24, minute)
    return dt.strftime("%I:%M %p").lstrip("0")

def _add_minutes(hour, minute, delta):
    total = hour * 60 + minute + delta
    total %= 24 * 60
    return total // 60, total % 60

def generate_schedule(subjects, preferences):
    """
    subjects: list of dicts (from DB) with remaining hours to schedule.
    preferences: dict with hours_per_day, session_length, start_date, preferred_time.

    Returns a list of session dicts (not yet saved to DB), ordered by date/time.
    """
    if not subjects:
        return []

    session_len = SESSION_LENGTH_MINUTES.get(preferences.get("session_length", "1 hour"), 60)
    hours_per_day = float(preferences.get("hours_per_day", 4))
    minutes_per_day = int(hours_per_day * 60)
    preferred_time = preferences.get("preferred_time", "Morning")
    start_hour, start_minute = PREFERRED_TIME_START.get(preferred_time, (9, 0))

    try:
        start_date = datetime.date.fromisoformat(preferences.get("start_date") or "") 
    except (ValueError, TypeError):
        start_date = datetime.date.today()

    def sort_key(s):
        prio = PRIORITY_ORDER.get(s.get("priority_level", "MEDIUM"), 2)
        try:
            deadline = datetime.date.fromisoformat(s.get("deadline", ""))
        except (ValueError, TypeError):
            deadline = datetime.date.max
        return (prio, deadline)

    sorted_subjects = sorted(subjects, key=sort_key)

    remaining = []
    for s in sorted_subjects:
        total_minutes = int(float(s.get("estimated_hours", 1)) * 60)
        done_minutes = int(float(s.get("completed_hours", 0)) * 60)
        left = max(total_minutes - done_minutes, 0)
        if left > 0:
            remaining.append({"subject": s, "minutes_left": left})

    sessions = []
    current_date = start_date
    safety_days = 0
    max_days = 120

    while remaining and safety_days < max_days:
        day_minutes_used = 0
        cur_hour, cur_minute = start_hour, start_minute
        try:
            day_str = current_date.strftime("%A, %B %d").replace(" 0", " ")
        except Exception:
            day_str = str(current_date)

        made_progress_today = False

        while remaining and day_minutes_used < minutes_per_day:
            progressed_this_pass = False
            i = 0
            while i < len(remaining) and day_minutes_used < minutes_per_day:
                item = remaining[i]
                s = item["subject"]

                try:
                    deadline = datetime.date.fromisoformat(s.get("deadline", ""))
                    if current_date > deadline:
                        i += 1
                        continue
                except (ValueError, TypeError):
                    pass

                chunk = min(session_len, item["minutes_left"], minutes_per_day - day_minutes_used)
                if chunk <= 0:
                    i += 1
                    continue

                end_hour, end_minute = _add_minutes(cur_hour, cur_minute, chunk)

                sessions.append({
                    "date": current_date.isoformat(),
                    "date_label": day_str,
                    "start_time": _fmt_time(cur_hour, cur_minute),
                    "end_time": _fmt_time(end_hour, end_minute),
                    "subject_id": s.get("id"),
                    "subject_name": s["name"],
                    "topic": s["topic"],
                    "duration_minutes": chunk,
                    "priority_level": s.get("priority_level", "MEDIUM"),
                    "technique": _pick_technique(s),
                    "is_break": False,
                })

                item["minutes_left"] -= chunk
                day_minutes_used += chunk
                made_progress_today = True
                progressed_this_pass = True
                cur_hour, cur_minute = end_hour, end_minute

                more_to_schedule_today = (item["minutes_left"] > 0) or any(
                    r is not item and r["minutes_left"] > 0 for r in remaining
                )
                if day_minutes_used < minutes_per_day and more_to_schedule_today:
                    b_end_hour, b_end_minute = _add_minutes(cur_hour, cur_minute, BREAK_MINUTES)
                    sessions.append({
                        "date": current_date.isoformat(),
                        "date_label": day_str,
                        "start_time": _fmt_time(cur_hour, cur_minute),
                        "end_time": _fmt_time(b_end_hour, b_end_minute),
                        "subject_id": None,
                        "subject_name": "Break",
                        "topic": "",
                        "duration_minutes": BREAK_MINUTES,
                        "priority_level": "",
                        "technique": "",
                        "is_break": True,
                    })
                    cur_hour, cur_minute = b_end_hour, b_end_minute
                    day_minutes_used += BREAK_MINUTES

                if item["minutes_left"] <= 0:
                    remaining.pop(i)
                else:
                    i += 1

            if not progressed_this_pass:
                break

        current_date += datetime.timedelta(days=1)
        safety_days += 1
        if not made_progress_today and day_minutes_used == 0:
            if safety_days > 30:
                break

    return sessions

def check_conflicts(subjects, preferences):
    """
    Runs BEFORE schedule generation. For each subject, compares the hours
    still required against the hours actually available (hours_per_day x
    number of days from the preferences' start_date up to and including the
    subject's deadline).

    Returns a list of conflict dicts (empty if nothing conflicts):
        subject_id, subject_name, topic, deadline,
        required_hours, available_hours, missing_hours,
        days_available, current_hours_per_day, suggested_hours_per_day

    This never mutates preferences - it only reports the shortfall and a
    suggested fix so the caller can ask the student before changing anything.
    """
    hours_per_day = float(preferences.get("hours_per_day", 4))

    try:
        start_date = datetime.date.fromisoformat(preferences.get("start_date") or "")
    except (ValueError, TypeError):
        start_date = datetime.date.today()

    conflicts = []
    for s in subjects:
        planned = float(s.get("estimated_hours", 0) or 0)
        completed = float(s.get("completed_hours", 0) or 0)
        required_hours = round(max(planned - completed, 0), 2)
        if required_hours <= 0:
            continue

        try:
            deadline = datetime.date.fromisoformat(s.get("deadline", ""))
        except (ValueError, TypeError):
            continue

        days_available = max((deadline - start_date).days + 1, 0)
        available_hours = round(hours_per_day * days_available, 2)

        if required_hours > available_hours:
            missing_hours = round(required_hours - available_hours, 2)
            suggested_hours_per_day = None
            if days_available > 0:
                needed_per_day = required_hours / days_available
                suggested_hours_per_day = math.ceil(needed_per_day * 2) / 2
                suggested_hours_per_day = min(suggested_hours_per_day, 16)

            conflicts.append({
                "subject_id": s.get("id"),
                "subject_name": s["name"],
                "topic": s["topic"],
                "deadline": s["deadline"],
                "required_hours": required_hours,
                "available_hours": available_hours,
                "missing_hours": missing_hours,
                "days_available": days_available,
                "current_hours_per_day": hours_per_day,
                "suggested_hours_per_day": suggested_hours_per_day,
            })

    conflicts.sort(key=lambda c: c["missing_hours"], reverse=True)
    return conflicts

def _pick_technique(subject):
    techniques = subject.get("study_techniques")
    if isinstance(techniques, list) and techniques:
        return techniques[0]
    if isinstance(techniques, str) and techniques:
        return techniques
    return "Active Recall"
