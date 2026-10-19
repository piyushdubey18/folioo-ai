# FOLIOO — AI Portfolio Builder

A beginner-friendly Flask prototype for creating, editing, previewing and downloading personal portfolios. The interface is responsive and uses a dark, gradient-accented design.

## Included features
- Login-first homepage and account registration
- Password hashing, CSRF protection, login/generation rate limits and security headers
- Private dashboard with saved portfolios
- AI-assisted content generation using Gemini (demo fallback works without an API key)
- 12 responsive design themes: Midnight, Minimal, Creative, Ocean Blue, Sunset Glow, Forest, Editorial, Terminal, Bold Brutalist, Lavender, Monochrome and Rose Quartz
- Edit personal details, headline, summary, About, skills, experience, achievements and profile links
- Add, edit and remove project cards; up to 8 projects per portfolio
- Undo unsaved edits by reloading the last saved version (confirmation shown)
- Save draft (save and stay in editor) or Save & Preview (save and open preview)
- Download a standalone HTML snapshot
- Portfolio edit/preview/download routes check login and ownership

## Run on Windows with VS Code / PowerShell
1. Install Python 3.11+ and VS Code. Open this project folder in VS Code.
2. In the VS Code terminal, run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

3. Paste the generated random value into `SECRET_KEY=` in `.env`. Optionally add your Gemini API key to `GEMINI_API_KEY=`. Keep `.env` private and never upload it to GitHub. If PowerShell blocks virtualenv activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.
4. Start the server:

```powershell
python app.py
```

5. Open `http://127.0.0.1:5000`, create an account and test the full flow. Without a Gemini key, the app uses clearly generic demo content.

## Main routes
- `/` — login
- `/register` — create account
- `/dashboard` — your portfolio library
- `/create` — create a portfolio
- `/p/<slug>` — private preview
- `/p/<slug>/edit` — private editor
- `/p/<slug>/download` — download HTML

## Deploying a demo
For a simple Render-style deployment, build command: `pip install -r requirements.txt`; start command: `gunicorn app:app`. Set a strong random `SECRET_KEY`, optionally `GEMINI_API_KEY` and `GEMINI_MODEL=gemini-2.5-flash`, and `COOKIE_SECURE=true` when served over HTTPS. Do not enable debug mode in production. Check the hosting provider's current free-tier limits before deploying.

## Important prototype limitations
- **This has not been fully runtime-tested in this environment** because Flask dependencies are not installed here. Python syntax compilation passed, but install dependencies and test registration, login, generation, editing, saving and download locally before relying on it.
- SQLite is suitable for a local prototype, not a robust multi-user production deployment. Some free hosts use ephemeral filesystems, so local SQLite data may disappear after restarts or redeployments. Move to managed PostgreSQL with backups before public launch.
- Rate limiting currently uses in-memory storage; use shared storage (for example Redis) for multiple workers.
- Add email verification, password reset, account deletion, privacy policy, data retention controls, monitoring, backup/recovery testing and an independent security review before collecting real user data.
- Generated HTML is a downloadable snapshot; this prototype does not publish a portfolio to a public URL.
- AI-generated text must be reviewed. Do not publish invented qualifications, experience, metrics or achievements.
- Do not promise user capacity until load testing is performed. AI response time and quotas depend on the external AI provider.

## Before launch checklist
- [ ] Install requirements and run locally
- [ ] Test create/edit/add/remove/undo/save draft/save & preview/download on desktop and mobile
- [ ] Test two accounts to verify portfolios cannot be accessed across accounts
- [ ] Set production secrets and HTTPS cookie settings
- [ ] Use persistent PostgreSQL and shared rate-limit storage
- [ ] Add privacy, deletion, recovery and monitoring workflows
- [ ] Perform security and load testing


## Profession-specific layouts (v6)
The builder now asks for a profession category and filters recommended design themes for Software/AI/Data, Student/Graduate, Designer/Creative, Business/Marketing/Sales, Freelancer/Consultant, Photographer/Artist, Writer/Content Creator, Teacher/Researcher, Healthcare/Wellness, and Finance/Legal. Preview section headings adapt to the selected category. Users can still switch between available designs. Existing portfolios without this field default to Software, AI & Data.


## Branding
The included logo asset is `static/folioo-logo.png`.
