## How to Run (GPT-Enabled Version)

This project **must** be run with GPT narration enabled.  
All game logic (suspicion, win/lose conditions) is implemented in Python, and GPT is used only to generate natural-language narration.

### 1. Prerequisites

- Python 3.8+ installed
- `pip` available
- An OpenAI account and **API key**
- Internet connection

Project layout (all files in the same project folder):

- `app.py`
- `game_state.py`
- `logic.py`
- `templates/`
  - `index.html`
- `static/`
  - `main.js`

All commands below assume you are in this **project root folder** (the same folder as `app.py`).

---

### 2. Install Python Dependencies

In a terminal opened in the project folder, run:

```bash
pip install flask openai

### 3. Install Python Dependencies
$env:OPENAI_API_KEY = "sk-PASTE-YOUR-KEY-HERE"
python app.py


