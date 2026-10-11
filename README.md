# AI Study Scheduler

An AI-powered study planner that helps students organize their studying: it analyzes subjects and deadlines, generates a prioritized day-by-day study schedule, tracks progress, and turns uploaded notes into AI-generated mock tests.

## Purpose

Students juggle multiple subjects, each with different deadlines, difficulty, and personal familiarity. AI Study Scheduler takes that information, has an AI model estimate difficulty/effort and compute a priority score per subject, and builds a realistic day-by-day schedule around the student's available time. It also lets students upload their own notes, extracts the important material with AI, and generates multiple-choice mock tests based **only** on that material so students can self-test.

## Features

- **Planner** — Add subjects with topic, deadline, current knowledge level, difficulty, and optional hour estimate. AI analyzes each one and returns difficulty, estimated hours, a 1–100 priority score, priority level (LOW/MEDIUM/HIGH/CRITICAL), recommended study techniques, and a personalized tip. Subjects are listed in priority order.
- **Schedule** — One click ("Generate AI Study Schedule") builds a full day-by-day plan from your subjects and study preferences (hours/day, session length, preferred time of day), with short breaks between sessions. Click any session to mark it complete — this immediately updates progress.
- **Study Notes** — Upload a PDF, DOCX, or TXT file per subject/topic. The backend extracts the text and AI identifies important topics, key definitions, important facts, and revision focus areas.
- **Mock Tests** — Generate a 5/10/20-question multiple-choice test from an analyzed document (AI is instructed to use *only* that document, not outside knowledge). Take the test, navigate between questions, submit, and see your score, percentage, performance rating, and a question-by-question breakdown with explanations.
- **Progress** — Subject-by-subject completion bars, total/completed/remaining hours, completed sessions, and mock test scores.
- **Analytics** — Aggregate stats (planned vs. completed hours, priority distribution, subject-wise hours, mock test performance) plus AI-generated study insights.

## Technology Stack

- **Frontend:** HTML, CSS, vanilla JavaScript (no framework, single-page app feel via client-side view switching)
- **Backend:** Python 3 + Flask
- **Database:** SQLite (file-based, persists across restarts)
- **AI:** Anthropic Claude API, called server-side only, via an API key stored in an environment variable
- **Document parsing:** `pypdf` (PDF), `python-docx` (DOCX), built-in file reading (TXT)

## Project Structure

```
ai-study-scheduler/
│
├── app.py                  # Flask app: all API routes
├── db.py                   # SQLite schema + connection helpers
├── ai_service.py           # All AI/LLM calls live here (with safe fallbacks)
├── document_processor.py   # PDF/DOCX/TXT text extraction
├── scheduler.py            # Day-by-day schedule generation algorithm
├── requirements.txt
├── .env                    # Your real environment variables (not committed)
├── .env.example             # Template showing required variables
├── .gitignore
│
├── database/
│   └── database.db         # Created automatically on first run
│
├── templates/
│   └── index.html          # Single-page app shell (all 6 sections)
│
├── static/
│   ├── style.css
│   └── script.js            # All frontend logic + API calls
│
├── uploads/                 # Uploaded study documents are stored here
└── README.md
```

## Architecture

```
Frontend (HTML/CSS/JS)
      │  fetch() calls to /api/...
      ▼
Flask Backend (app.py)
      │  calls ai_service.py functions
      ▼
AI API (Anthropic Claude, via requests + AI_API_KEY env var)
      │  returns structured JSON
      ▼
Flask Backend  →  SQLite (persists everything)
      │
      ▼
Frontend (renders JSON as UI)
```

The AI API key is **never** sent to or exposed in the frontend. All AI calls happen inside `ai_service.py`, on the server, using the key from the environment.

## Installation

1. **Clone or download the project**, then move into the folder:
   ```bash
   cd ai-study-scheduler
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # on Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Environment Variable Setup

The app supports **either Anthropic Claude or Google Gemini** as its AI provider — pick one with `AI_PROVIDER`. No code changes needed either way.

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` and set the provider + your real API key:

   **Using Anthropic (default):**
   ```
   AI_PROVIDER=anthropic
   AI_API_KEY=your_actual_anthropic_key
   AI_MODEL=claude-sonnet-4-6
   ```
   Get a key at https://console.anthropic.com

   **Using Gemini:**
   ```
   AI_PROVIDER=gemini
   AI_API_KEY=your_actual_gemini_key
   AI_MODEL=gemini-2.5-flash
   ```
   Get a key at https://aistudio.google.com/apikey

   Leave `AI_MODEL` blank to use the sensible default for whichever provider you picked (`claude-sonnet-4-6` for Anthropic, `gemini-2.5-flash` for Gemini).

   **If `AI_API_KEY` is missing, the provider is unreachable, or the AI call fails for any reason**, the app does not crash — subject analysis and document analysis fall back to a simple built-in heuristic (with a warning shown in the UI), and mock-test generation returns a clear error explaining that AI is required for that feature. You can check which provider is active and whether a key is configured by hitting `GET /api/health`.

## How to Run Locally

```bash
python app.py
```

The app will start on **http://localhost:5000**. Open that URL in your browser. The SQLite database (`database/database.db`) is created automatically on first run, and your data persists across restarts and page refreshes.

## How to Upload Notes

1. Go to the **Study Notes** tab.
2. Enter the subject name and topic the document belongs to.
3. Choose a `.pdf`, `.docx`, or `.txt` file and click **Analyze Document**.
4. The backend extracts the text and AI returns important topics, key definitions, important facts, and revision focus areas — shown directly on the page.
5. Click **Generate Mock Test** on any analyzed document to create a 5/10/20-question test from it.

## How AI Scheduling Works

1. For each subject you add, AI (or the fallback heuristic, if AI is unavailable) scores **priority (1–100)** based on deadline proximity, difficulty, your self-rated knowledge level, and required study hours, and buckets it into LOW / MEDIUM / HIGH / CRITICAL.
2. When you click **Generate AI Study Schedule**, the scheduler:
   - Sorts subjects by priority (CRITICAL → LOW), then by nearer deadline.
   - Fills each day up to your **Study Hours Per Day** limit, using your chosen **session length** and **preferred time of day** as the daily start time.
   - Splits large subjects across multiple sessions/days as needed, inserting a 15-minute break between sessions.
   - Never schedules a subject past its deadline.
3. The generated sessions are saved to the database and shown grouped by date on the **Schedule** page. Marking a session complete updates that subject's completed hours everywhere (Progress, Analytics).

## How MCQ Generation Works

1. You select an analyzed document and choose 5, 10, or 20 questions.
2. The extracted document text (and only that text) is sent to the AI with an instruction to generate multiple-choice questions **based solely on the provided content** — no outside knowledge.
3. Each question is validated to have exactly 4 options, a correct answer, an explanation, and a related topic before being saved.
4. During the test, only questions and options are shown (correct answers are withheld until submission).
5. On submission, the backend grades it server-side and returns your score, percentage, a performance label, and a full question-by-question breakdown with explanations.

## Notes on Reliability

- The app never crashes on: a missing/invalid AI key, an unreachable AI API, an invalid/empty uploaded document, invalid AI JSON output, no subjects, no schedule, or an incomplete form — each case shows a clear, specific error message in the UI instead.
- All state (subjects, preferences, schedule, documents, mock tests, results) is stored in SQLite, not in browser memory, so refreshing the page never loses your data.

## Mobile App & APK Usage (Progressive Web App)

AI Study Scheduler is built as an **Installable PWA (Progressive Web App)** that looks, feels, and operates as a native mobile application.

### 1. Using on Mobile via Local Wi-Fi (Instant)
1. Start the Flask server on your computer:
   ```bash
   python app.py
   ```
2. In the web interface, click the **"Open on Mobile"** button at the bottom of the sidebar.
3. A modal appears showing your Wi-Fi address (e.g., `http://192.168.0.11:5000`) and a **QR Code**.
4. Scan the QR code with your mobile camera (or type the address in your phone's browser).

### 2. Installing to Phone Home Screen (Like a Native App)
- **Android (Chrome / Edge):** A prompt will appear saying **"Install AI Study Scheduler"** — tap **Install**. Alternatively, tap `⋮` (browser menu) → **Install app** or **Add to Home Screen**.
- **iOS (Safari):** Tap the **Share** button (box with upward arrow) → scroll down and tap **"Add to Home Screen"**.

Once installed:
- It launches full-screen with no browser address bar.
- It displays the custom AI Study Scheduler mascot launcher icon on your home screen.
- Features a native-like mobile bottom navigation bar (Planner, Quests, Notes, Quizzes, Stats).

### 3. Converting to a Standalone Android APK File
If you want to create an installable `.apk` file for distribution:
1. Deploy the Flask app to a cloud host (such as Render, Railway, or PythonAnywhere).
2. Visit **[PWABuilder.com](https://www.pwabuilder.com)** (Microsoft's free open-source PWA to APK tool).
3. Enter your deployed URL and click **Start**.
4. Click **Package for Stores** → **Android (APK)** to download your signed `.apk` file directly.

