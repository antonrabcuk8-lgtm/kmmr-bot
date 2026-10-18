# Бот звернень КММР

Telegram-бот Київської Міської Молодіжної Ради для збору скарг, ідей і запитань від молоді Києва.

## Що вміє

- Діалог звернення: тип → район → тема → текст → чи потрібна відповідь
- Типи: скарга, ідея, побажання, питання
- «Мої звернення», адмінка, статуси, `/stats`, `/export`
- Автодайджест і нагадування про «нові» старше 7 днів
- **Webhook-режим** для Render (без платного Worker)

## Локально (polling)

```powershell
cd "c:\Users\LOQ\OneDrive\Desktop\кммр"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# заповни BOT_TOKEN і ADMIN_IDS
python run.py
```

У `.env` залиш `MODE=polling`. Перед деплоєм на Render **зупини** локальний `run.py`, інакше буде Conflict.

## Render (webhook)

Free Web Service «засинає» без запитів. Polling/Worker на безкоштовному плані не підходить.  
Webhook працює так: Telegram сам шле HTTPS-запит → сервіс прокидається → бот відповідає.

### 1. Залий код на GitHub

Репозиторій з цією папкою (без `.env` і `.venv`).

### 2. New Web Service на Render

- **Build:** `pip install -r requirements.txt`
- **Start:** `python run_webhook.py`
- **Health Check Path:** `/health`

Або підключи `render.yaml` (Blueprint).

### 3. Environment Variables

| Змінна | Приклад | Опис |
|---|---|---|
| `MODE` | `webhook` | обов’язково |
| `PYTHON_VERSION` | `3.12.10` | не 3.14 — інакше впаде збірка |
| `BOT_TOKEN` | токен BotFather | секрет |
| `ADMIN_IDS` | `5729118686` | можна кілька через кому |
| `WEBHOOK_BASE_URL` | `https://kmmr-bot.onrender.com` | можна не ставити: Render дає `RENDER_EXTERNAL_URL` |
| `WEBHOOK_SECRET` | випадковий рядок 16+ символів | захист webhook |
| `WEBHOOK_PATH` | `/webhook` | за замовчуванням ок |
| `DB_PATH` | `data/appeals.db` | шлях до SQLite |

`PORT` Render задає сам — у коді вже читається.

### 4. Після деплою

1. Відкрий `https://твій-сервіс.onrender.com/health` — має бути `{"ok": true, ...}`
2. У логах Render шукай рядок `Webhook встановлено`
3. У Telegram: `/start` у боті
4. Локальний `python run.py` має бути вимкнений

### Cold start і дайджест

- Перше повідомлення після сну може йти 10–30 сек — це нормально для free.
- Дайджест/overdue спрацьовують, коли сервіс прокинувся (оновлення від Telegram або запит на `/health`).
- Щоб рідше засинав — можна раз на 10 хв пінгувати `/health` з [cron-job.org](https://cron-job.org) (безкоштовно).

### База даних на free

Диск на free **ефемерний**: після redeploy SQLite може обнулитись.  
Перед важливими змінами роби `/export`. Для постійної бази — Persistent Disk (платний план) і `DB_PATH=/var/data/appeals.db`.

## Команди адміна

| Команда | Що робить |
|---|---|
| `/admin` | меню адмінки |
| `/inbox` | лише нові |
| `/stats` | статистика місяця |
| `/list` | останні 10 |
| `/get КММР-0001` | картка |
| `/reply КММР-0001 текст` | відповідь |
| `/export` | CSV |
| `/digest` | дайджест минулого місяця |
| `/overdue` | «нові» старші за 7 днів |
| `/backup` | повний JSON-бекап усіх звернень |
| `/restore` | відновити базу з JSON (статистика знову та сама) |
| `/admins` | список ADMIN_IDS |

На Render free база може обнулитись після redeploy. Тому бот **щодня** шле адмінам повний `.json` бекап. Збережи його на ПК. Після збою: `/restore` → надішли файл → `/stats` знову працює з тих самих даних.

## Важливо

Це канал звернень до Київської Міської Молодіжної Ради, а не заявка в міські служби.  
У публічних дайджестах не світи імена та Telegram користувачів.
