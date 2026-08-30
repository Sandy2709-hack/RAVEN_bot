# Raven Sprint 2.6 — Railway Deployment

This guide deploys Raven as one continuously running Railway service. Telegram
long polling, attendance reminders and the AKTU notice scheduler can remain
active while the developer PC is switched off.

Raven uses Groq in Railway. Ollama remains available only as an optional local
development provider.

## 1. Test the project locally

Keep the existing `.env` and `raven_memory.db`, copy the Sprint 2.6 files over
the project, and run:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -u bot.py
```

The expected test result is `Ran 43 tests` followed by `OK`.

## 2. Create a Groq API key

1. Sign in to <https://console.groq.com/>.
2. Open **API Keys** and create a key for Raven.
3. Copy it once and keep it private.
4. Never place the real key in `.env.example`, Git, screenshots or chat.

The default cloud model is `llama-3.3-70b-versatile`. It is configurable so a
currently supported Groq model can be substituted without editing Python.

## 3. Push Sprint 2.6 to GitHub

Stop every locally running Raven process with `CTRL+C`. Only one polling
process should use a Telegram bot token.

Commit the new files and push the branch that the Raven repository actually
uses:

```bash
git add .
git commit -m "Add Sprint 2.6 Railway and Groq deployment"
git push
```

Do not add `.env` or `raven_memory.db`; `.gitignore` already excludes them.

## 4. Create the Railway service

1. Open <https://railway.com/> and choose **New Project**.
2. Choose **Deploy from GitHub repo**.
3. Select Raven's repository and the correct branch.
4. Let Railway detect the Python project with Railpack.

The included `railway.json` starts `python -u bot.py`, restarts Raven
automatically and disables deployment overlap so two polling copies do not run
simultaneously. A public domain is not required because Telegram long polling
makes outbound requests.

## 5. Add Railway variables

Open the Raven service, select **Variables**, and add exactly:

```text
TELEGRAM_BOT_TOKEN=<the token from BotFather>
AI_PROVIDER=groq
GROQ_API_KEY=<the key from Groq>
GROQ_MODEL=llama-3.3-70b-versatile
```

Do not add quotation marks and do not add Ollama variables on Railway.

## 6. Attach persistent storage before using Raven

1. On the Railway project canvas, attach a volume to the Raven service.
2. Set its mount path to `/data`.
3. Redeploy the service if Railway requests it.

Railway exposes the mount through `RAILWAY_VOLUME_MOUNT_PATH`. Raven detects it
automatically and stores the database at `/data/raven_memory.db`.

Without the volume, the bot can still run, but its SQLite data can disappear on
a redeploy. Use only one Raven replica because SQLite and Telegram long polling
are both intended to have one active bot process in this prototype.

## 7. Verify the deployment

Open Railway's deployment logs. A successful start contains:

```text
Raven Sprint 2.6 Cloud Deployment is online
AI provider: Groq (...)
Database initialized
```

Then send `/start`, `/attendance` and a normal chat message to Raven. The normal
message should create a `Groq model=... total=...s` log entry without requiring
Ollama or the developer PC.

If Railway logs a Telegram `Conflict` error, another copy of `bot.py` is still
running locally or in another deployment. Stop the other copy and restart the
Railway service.

## 8. Optional: move the current local database

Raven can start with a clean Railway database. To preserve the existing local
profiles, memory and attendance instead, install and log in to the Railway CLI,
link the Raven project, stop the service temporarily, then upload:

```bash
railway volume files upload ./raven_memory.db /raven_memory.db --overwrite
```

Restart the service afterwards. Keep a local backup before replacing any
remote database.

To download a later backup:

```bash
railway volume files download /raven_memory.db ./raven_memory_backup.db --overwrite
```

## 9. Trial usage

Watch Railway's usage page during the trial. Groq handles model inference, so
Railway only runs the lightweight Python bot, scheduler and SQLite database.
Before the trial credit or remaining days expire, download a database backup
and decide whether to continue, migrate or temporarily return to local use.

## Local Ollama mode

For local offline development, the private `.env` may instead contain:

```text
TELEGRAM_BOT_TOKEN=<token>
AI_PROVIDER=ollama
OLLAMA_MODEL=qwen3:1.7b
OLLAMA_URL=http://localhost:11434/api/chat
```

No Groq key is required when `AI_PROVIDER=ollama`.
