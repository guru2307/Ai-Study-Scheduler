"""
ai_service.py - All AI/LLM interaction lives here.

The rest of the app never talks to the AI API directly. Every public
function in this module returns a plain Python dict/list and NEVER
raises - on any failure (missing key, network error, invalid JSON from
the model) it returns a safe fallback plus an "ai_used": False flag so
the frontend can show a clear message instead of crashing.
"""
import os
import json
import re
import time
import requests

AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic").strip().lower()
AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini": "gemini-flash-lite-latest",
}
AI_MODEL = os.environ.get("AI_MODEL", "").strip() or _DEFAULT_MODELS.get(AI_PROVIDER, "claude-sonnet-4-6")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REQUEST_TIMEOUT = 20

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 529}
_MAX_RETRIES = 1
_RETRY_BACKOFF_SECONDS = [1]

class AIError(Exception):
    pass

def _post_with_retry(url, headers, payload, provider_label):
    """
    POSTs to an AI provider, automatically retrying a couple of times (with
    a short backoff) on transient errors like 503 "overloaded" or 429 "rate
    limited" - these clear up on their own within seconds and shouldn't be
    shown to the student as a failure. Any other error (bad key -> 401/403,
    bad request -> 400, network failure) is raised immediately, no retry.
    """
    last_status = None
    last_body = None
    last_network_error = None

    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            last_network_error = e
        else:
            if resp.status_code == 200:
                return resp
            if resp.status_code not in _RETRYABLE_STATUS_CODES:
                raise AIError(f"{provider_label} API returned status {resp.status_code}: {resp.text[:300]}")
            last_status, last_body = resp.status_code, resp.text[:300]

        if attempt < _MAX_RETRIES:
            time.sleep(_RETRY_BACKOFF_SECONDS[attempt])

    if last_status is not None:
        raise AIError(
            f"{provider_label} is temporarily overloaded (status {last_status}) and didn't recover after "
            f"{_MAX_RETRIES + 1} attempts. This is usually momentary - please try again in a minute."
        )
    raise AIError(f"Could not reach the {provider_label} API: {last_network_error}")

def _call_ai(system_prompt, user_prompt, max_tokens=2000):
    """
    Low-level call to whichever AI provider is configured (AI_PROVIDER).
    Returns the raw text content from the model.
    Raises AIError on any failure - callers must catch it.
    """
    if not AI_API_KEY:
        raise AIError("AI_API_KEY is not configured on the server.")

    if AI_PROVIDER == "gemini":
        return _call_gemini(system_prompt, user_prompt, max_tokens)
    elif AI_PROVIDER == "anthropic":
        return _call_anthropic(system_prompt, user_prompt, max_tokens)
    else:
        raise AIError(f"Unknown AI_PROVIDER '{AI_PROVIDER}'. Use 'anthropic' or 'gemini'.")

def _call_anthropic(system_prompt, user_prompt, max_tokens):
    headers = {
        "x-api-key": AI_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": AI_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        resp = _post_with_retry(ANTHROPIC_URL, headers, payload, "Anthropic")
    except AIError:
        raise

    try:
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks).strip()
    except (ValueError, KeyError) as e:
        raise AIError(f"Unexpected Anthropic API response format: {e}")

def _call_gemini(system_prompt, user_prompt, max_tokens):
    candidate_models = [AI_MODEL]
    for alt in ["gemini-flash-lite-latest", "gemini-3.8-flash"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    last_error = None
    for model_name in candidate_models:
        url = GEMINI_URL_TEMPLATE.format(model=model_name)
        headers = {
            "x-goog-api-key": AI_API_KEY,
            "content-type": "application/json",
        }
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }

        try:
            resp = _post_with_retry(url, headers, payload, f"Gemini ({model_name})")
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                feedback = data.get("promptFeedback", {})
                block_reason = feedback.get("blockReason")
                if block_reason:
                    raise AIError(f"Gemini blocked this request ({block_reason}).")
                raise AIError("Gemini returned no candidates.")

            finish_reason = candidates[0].get("finishReason")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(p.get("text", "") for p in parts if "text" in p).strip()

            if not text and finish_reason and finish_reason not in ("STOP", "MAX_TOKENS"):
                raise AIError(f"Gemini did not return usable content (finishReason: {finish_reason}).")
            return text
        except Exception as e:
            last_error = e
            continue

    if last_error:
        raise last_error
    raise AIError("Gemini API call failed with all candidate models.")

def _extract_json(text):
    """
    Pull the first valid JSON object/array out of a model response,
    tolerating stray markdown fences or preamble text.
    """
    if not text:
        raise AIError("Empty AI response.")

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned.strip())
    cleaned = re.sub(r"```$", "", cleaned.strip())
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for open_ch, close_ch in [("{", "}"), ("[", "]")]:
        start = cleaned.find(open_ch)
        end = cleaned.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise AIError("Could not parse JSON from AI response.")

_KNOWLEDGE_WEIGHT = {"Beginner": 1.0, "Somewhat Familiar": 0.75, "Intermediate": 0.5, "Advanced": 0.25}
_DIFFICULTY_HOURS = {"Easy": 3, "Medium": 5, "Hard": 8, "Expert": 12}
_DIFFICULTY_WEIGHT = {"Easy": 0.3, "Medium": 0.55, "Hard": 0.8, "Expert": 1.0}

def _fallback_subject_analysis(subject, topic, deadline, knowledge_level, difficulty, estimated_hours):
    import datetime
    difficulty = difficulty if difficulty and difficulty != "Auto Detect" else "Medium"
    hours = estimated_hours if estimated_hours else _DIFFICULTY_HOURS.get(difficulty, 5)

    try:
        days_left = max((datetime.date.fromisoformat(deadline) - datetime.date.today()).days, 0)
    except (ValueError, TypeError):
        days_left = 14

    urgency = max(0, 1 - (days_left / 30))
    knowledge_factor = _KNOWLEDGE_WEIGHT.get(knowledge_level, 0.6)
    difficulty_factor = _DIFFICULTY_WEIGHT.get(difficulty, 0.55)

    score = (urgency * 40) + (difficulty_factor * 30) + (knowledge_factor * 30)
    score = int(max(1, min(100, round(score))))

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "difficulty": difficulty,
        "difficulty_reason": "Estimated automatically (AI unavailable) based on provided difficulty or topic defaults.",
        "estimated_hours": hours,
        "hours_reason": "Estimated automatically (AI unavailable) using standard difficulty benchmarks.",
        "priority_score": score,
        "priority_level": level,
        "priority_reason": f"Based on {days_left} day(s) until deadline, {difficulty.lower()} difficulty, and your self-rated knowledge level.",
        "study_techniques": ["Active Recall", "Spaced Repetition", "Practice Problems"],
        "study_tip": "Break this topic into smaller chunks and review it across multiple short sessions rather than one long one.",
        "ai_used": False,
    }

def _fallback_document_analysis(text):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    top_sentences = [s.strip() for s in sentences if len(s.strip()) > 25][:6]
    return {
        "important_topics": top_sentences[:5] if top_sentences else ["General content of the uploaded document"],
        "key_definitions": [],
        "important_facts": top_sentences[5:6],
        "revision_areas": top_sentences[:3],
        "ai_used": False,
    }

def analyze_subject(subject, topic, deadline, knowledge_level, difficulty, estimated_hours, notes):
    system_prompt = (
        "You are an expert academic study planner. You analyze a student's subject/topic "
        "and return ONLY a single valid JSON object, with no markdown, no commentary, no code fences. "
        "The JSON object must have exactly these keys: "
        "difficulty (one of Easy, Medium, Hard, Expert), "
        "difficulty_reason (string), "
        "estimated_hours (number), "
        "hours_reason (string), "
        "priority_score (integer 1-100), "
        "priority_level (one of LOW, MEDIUM, HIGH, CRITICAL), "
        "priority_reason (string), "
        "study_techniques (array of 2-4 short strings), "
        "study_tip (a short personalized, actionable string)."
    )
    user_prompt = json.dumps({
        "subject": subject,
        "topic": topic,
        "deadline": deadline,
        "current_knowledge_level": knowledge_level,
        "difficulty_hint": difficulty,
        "estimated_hours_hint": estimated_hours,
        "student_notes": notes,
        "instructions": (
            "Consider deadline proximity, subject difficulty, the student's current knowledge level, "
            "and required study hours when computing priority_score. "
            "If difficulty_hint is 'Auto Detect' or empty, determine difficulty yourself. "
            "If estimated_hours_hint is empty, estimate it yourself."
        ),
    })

    try:
        raw = _call_ai(system_prompt, user_prompt, max_tokens=800)
        result = _extract_json(raw)
        required_keys = {"difficulty", "estimated_hours", "priority_score", "priority_level"}
        if not required_keys.issubset(result.keys()):
            raise AIError("AI response missing required fields.")
        result["priority_score"] = int(max(1, min(100, round(float(result["priority_score"])))))
        result["estimated_hours"] = float(result["estimated_hours"])
        result.setdefault("study_techniques", ["Active Recall", "Spaced Repetition"])
        result.setdefault("study_tip", "")
        result.setdefault("difficulty_reason", "")
        result.setdefault("hours_reason", "")
        result.setdefault("priority_reason", "")
        result["ai_used"] = True
        return result
    except AIError:
        return _fallback_subject_analysis(subject, topic, deadline, knowledge_level, difficulty, estimated_hours)
    except (ValueError, TypeError, KeyError):
        return _fallback_subject_analysis(subject, topic, deadline, knowledge_level, difficulty, estimated_hours)

def analyze_document(text, subject_name, topic):
    if not text or not text.strip():
        return {
            "important_topics": [], "key_definitions": [], "important_facts": [],
            "revision_areas": [], "ai_used": False, "error": "The document appears to be empty.",
        }

    truncated = text[:15000]
    system_prompt = (
        "You are an academic assistant that extracts study material from a document. "
        "Return ONLY a single valid JSON object, no markdown, no commentary. "
        "Keys required: important_topics (array of strings), key_definitions (array of strings, "
        "each formatted as 'Term: definition'), important_facts (array of strings), "
        "revision_areas (array of strings describing what the student should review most)."
    )
    user_prompt = json.dumps({
        "subject": subject_name,
        "topic": topic,
        "document_text": truncated,
        "instructions": "Base your analysis ONLY on the provided document_text. Do not use outside knowledge.",
    })

    try:
        raw = _call_ai(system_prompt, user_prompt, max_tokens=1500)
        result = _extract_json(raw)
        result.setdefault("important_topics", [])
        result.setdefault("key_definitions", [])
        result.setdefault("important_facts", [])
        result.setdefault("revision_areas", [])
        result["ai_used"] = True
        return result
    except AIError:
        fb = _fallback_document_analysis(text)
        fb["error"] = "AI unavailable - showing a basic automatic summary instead."
        return fb
    except (ValueError, TypeError, KeyError):
        fb = _fallback_document_analysis(text)
        fb["error"] = "AI response could not be parsed - showing a basic automatic summary instead."
        return fb

_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her", "was", "one",
    "our", "out", "day", "get", "has", "him", "his", "how", "man", "new", "now", "old",
    "see", "two", "way", "who", "boy", "did", "its", "let", "put", "say", "she", "too",
    "use", "that", "with", "this", "from", "they", "have", "were", "been", "their",
    "what", "when", "where", "which", "there", "these", "those", "than", "then", "into",
    "such", "some", "each", "will", "would", "could", "should", "about", "also", "does",
    "based", "only", "must", "used", "using", "your",
}

def _significant_words(text):
    words = re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS}

def _is_traceable(question, doc_words, doc_text_lower):
    """
    Heuristic traceability check: a generated question is kept only if we
    can find real evidence it was grounded in the uploaded document, not
    invented from outside knowledge.

    Checks (in order of confidence):
    1. If the model gave a source_reference, that snippet (or most of its
       significant words) should actually appear in the document.
    2. Otherwise, the question + correct answer + explanation must share a
       meaningful number of distinct keywords with the document.
    """
    source_ref = (question.get("source_reference") or "").strip()
    if source_ref:
        ref_lower = source_ref.lower()
        if ref_lower in doc_text_lower:
            return True
        ref_words = _significant_words(source_ref)
        if ref_words:
            overlap = ref_words & doc_words
            if len(overlap) / len(ref_words) >= 0.6:
                return True

    combined = f"{question.get('question','')} {question.get('correct_answer','')} {question.get('explanation','')}"
    q_words = _significant_words(combined)
    if not q_words:
        return False
    overlap = q_words & doc_words
    return len(overlap) >= 3 or (len(overlap) / max(len(q_words), 1)) >= 0.35

def generate_mcqs(text, subject_name, topic, num_questions):
    if not text or not text.strip():
        return {"questions": [], "ai_used": False, "error": "No document text available to generate questions from."}

    truncated = text[:15000]
    doc_words = _significant_words(truncated)
    doc_text_lower = truncated.lower()

    system_prompt = (
        "You are an exam question writer. Generate multiple-choice questions using ONLY facts, "
        "definitions, and statements that are explicitly present in the provided document text. "
        "Do NOT use outside knowledge, and do NOT invent facts that aren't in the document, even if "
        "they are true in general. "
        "IMPORTANT: If the document does not contain enough distinct, substantive material to "
        "support the requested number of good questions, generate FEWER questions rather than "
        "inventing or padding content - quality and factual grounding matter more than hitting the count. "
        "Return ONLY a single valid JSON object with no markdown and no commentary. The JSON object "
        "must have exactly one key, 'questions', which is an array. Each item in the array must have "
        "exactly these keys: "
        "question (string), options (array of exactly 4 strings, NOT prefixed with A/B/C/D), "
        "correct_answer (string - the exact text of the correct option, matching one of the options exactly), "
        "explanation (string explaining why it's correct, referencing the document), "
        "related_topic (short string), "
        "source_reference (a short phrase or sentence COPIED OR CLOSELY PARAPHRASED from the document "
        "that directly supports this question - this is used to verify the question is grounded in the text)."
    )
    user_prompt = json.dumps({
        "subject": subject_name,
        "topic": topic,
        "document_text": truncated,
        "num_questions": num_questions,
        "instructions": (
            f"Generate up to {num_questions} multiple choice questions, each with 4 options. "
            "If the document only supports fewer good questions than that, return only that many."
        ),
    })

    try:
        raw = _call_ai(system_prompt, user_prompt, max_tokens=4500)
        result = _extract_json(raw)
        questions = result.get("questions", [])

        structurally_valid = []
        for q in questions:
            if not all(k in q for k in ("question", "options", "correct_answer")):
                continue
            options = q.get("options", [])
            if len(options) != 4:
                continue
            if q["correct_answer"] not in options:
                continue
            q.setdefault("explanation", "")
            q.setdefault("related_topic", topic)
            q.setdefault("source_reference", "")
            structurally_valid.append(q)

        traceable = [q for q in structurally_valid if _is_traceable(q, doc_words, doc_text_lower)]
        dropped_untraceable = len(structurally_valid) - len(traceable)

        final_questions = traceable[:num_questions]

        if not final_questions:
            raise AIError(
                "AI did not return any questions that could be verified against the document content."
            )

        insufficient = len(final_questions) < num_questions
        result_payload = {
            "questions": final_questions,
            "ai_used": True,
            "requested": num_questions,
            "generated": len(final_questions),
            "insufficient_material": insufficient,
        }
        if insufficient:
            result_payload["error"] = (
                f"The uploaded document only contained enough material to generate "
                f"{len(final_questions)} of the {num_questions} requested question(s), "
                f"all sourced directly from the document."
            )
        elif dropped_untraceable:
            result_payload["error"] = (
                f"{dropped_untraceable} generated question(s) could not be verified against the "
                f"document and were discarded."
            )
        return result_payload
    except AIError as e:
        return {"questions": [], "ai_used": False, "error": str(e), "requested": num_questions, "generated": 0}
    except (ValueError, TypeError, KeyError) as e:
        return {
            "questions": [], "ai_used": False, "error": f"Could not parse AI response: {e}",
            "requested": num_questions, "generated": 0,
        }

def generate_insights(stats):
    system_prompt = (
        "You are a supportive academic coach. Based on a JSON summary of a student's study "
        "progress, priorities, completed sessions, and mock test performance, generate 3-5 short, "
        "specific, encouraging insights/recommendations focused ONLY on studying. "
        "Return ONLY a valid JSON object with one key 'insights', an array of short strings (max ~20 words each). "
        "No markdown, no commentary."
    )
    user_prompt = json.dumps(stats)

    try:
        raw = _call_ai(system_prompt, user_prompt, max_tokens=600)
        result = _extract_json(raw)
        insights = result.get("insights", [])
        if not insights:
            raise AIError("No insights returned.")
        return {"insights": insights, "ai_used": True}
    except AIError:
        return {"insights": _fallback_insights(stats), "ai_used": False}
    except (ValueError, TypeError, KeyError):
        return {"insights": _fallback_insights(stats), "ai_used": False}

def _fallback_insights(stats):
    insights = []
    total = stats.get("total_planned_hours", 0)
    completed = stats.get("total_completed_hours", 0)
    if total > 0:
        pct = round((completed / total) * 100)
        insights.append(f"You've completed {pct}% of your planned study hours - keep the momentum going.")
    critical = stats.get("critical_subjects", 0)
    if critical:
        insights.append(f"You have {critical} critical-priority subject(s) - tackle these in your next session.")
    avg_score = stats.get("avg_test_score")
    if avg_score is not None:
        if avg_score < 60:
            insights.append("Your mock test average is below 60% - consider revisiting weak topics before your next test.")
        else:
            insights.append("Your mock test scores look solid - maintain regular practice tests to stay sharp.")
    if not insights:
        insights.append("Add subjects and generate a schedule to start receiving personalized study insights.")
    return insights
