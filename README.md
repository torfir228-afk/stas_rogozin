# Telegram-бот воронки «Диагностика шеи»

Бот на [aiogram 3](https://docs.aiogram.dev/) реализует воронку:

1. `/start` → приветственное сообщение с кнопкой «Забрать диагностику бесплатно».
2. Проверка подписки на канал. Если пользователь не подписан — бот просит подписаться
   и присылает кнопку «Я подписался, открыть доступ».
3. Как только подписка подтверждена — бот сразу выдаёт лид-магнит (ссылку и/или файл).
4. Если пользователь не подписался, автоматически включаются два дожимных напоминания:
   через 10 минут и через 120 минут (интервалы настраиваются). Как только пользователь
   подписывается и получает материал, оставшиеся напоминания отменяются.

Все тексты сообщений лежат в `bot/texts.py`, ссылки и тайминги настраиваются через `.env`
(см. `.env.example`) — редактировать код не нужно.

Расписание напоминаний хранится в SQLite (`data/jobs.sqlite3`), состояние пользователей —
тоже в SQLite (`data/bot.sqlite3`). Это значит, что после перезапуска бота (обновление,
падение контейнера, перезагрузка сервера) уже запланированные напоминания и статусы
пользователей не теряются.

## Почему бот работает без включённого компьютера

Бот использует long polling (никакого домена/SSL не нужно) и рассчитан на то, чтобы
крутиться на сервере (VPS) или в облаке 24/7, а не на вашем ноутбуке. Ниже — три варианта
запуска на постоянку.

## 1. Подготовка

1. Создайте бота через [@BotFather](https://t.me/BotFather) и получите `BOT_TOKEN`.
2. Создайте (или используйте существующий) канал, добавьте туда бота **администратором**
   — без этого бот не сможет проверять подписки через `getChatMember`.
3. Узнайте `CHANNEL_ID` — это может быть публичный `@username` канала, либо числовой ID
   вида `-1001234567890` (для закрытых каналов). Узнать числовой ID проще всего, переслав
   любое сообщение из канала боту вроде `@JsonDumpBot` или `@getidsbot`.
4. Скопируйте `.env.example` в `.env` и заполните все значения:

   ```bash
   cp .env.example .env
   ```

## 2. Локальный запуск (для теста)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 3. Запуск в Docker (рекомендуется для сервера)

```bash
docker compose up -d --build
```

- Контейнер поднимается с `restart: always` — переживёт перезагрузку сервера.
- Папка `./data` монтируется как volume, поэтому база данных и расписание напоминаний
  сохраняются между обновлениями образа.
- Логи: `docker compose logs -f bot`.
- Обновить бота после правок кода: `docker compose up -d --build`.

## 4. Деплой на VPS

Подойдёт любой недорогой VPS (Timeweb Cloud, Selectel, Hetzner, Aeza и т.п.) с Ubuntu/Debian:

```bash
# на сервере
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
git clone <ваш_репозиторий>
cd stas_rogozin
cp .env.example .env   # заполните значения
docker compose up -d --build
```

Бот будет работать постоянно, независимо от того, включён ли ваш компьютер.

### Альтернатива без Docker — systemd

Если не хотите использовать Docker, можно запустить бота как системный сервис:

```bash
sudo useradd -r -s /bin/false botuser
sudo mkdir -p /opt/telegram-bot
sudo cp -r . /opt/telegram-bot
cd /opt/telegram-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo chown -R botuser:botuser /opt/telegram-bot

sudo cp deploy/telegram-bot.service /etc/systemd/system/telegram-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bot
sudo systemctl status telegram-bot
```

Логи: `journalctl -u telegram-bot -f`.

## 5. Настройка контента

- `bot/texts.py` — все тексты сообщений (можно менять формулировки).
- `.env` — ссылки на канал и лид-магнит, тайминги напоминаний.
- Рекомендуется закрепить пост с лид-магнитом в канале и указать ссылку на него
  в `LEAD_MAGNET_URL`, либо положить файл на сервер и указать путь в
  `LEAD_MAGNET_FILE_PATH` — тогда бот пришлёт файл документом вместе со ссылкой.

## Структура проекта

```
main.py                 — точка входа, запуск polling и планировщика
bot/config.py           — загрузка настроек из .env
bot/database.py         — состояние пользователей (SQLite)
bot/scheduler.py        — персистентные напоминания (APScheduler + SQLite)
bot/texts.py            — тексты сообщений и клавиатуры
bot/handlers.py         — обработчики /start и колбэков
Dockerfile / docker-compose.yml — контейнеризация
deploy/telegram-bot.service      — systemd-юнит для запуска без Docker
```
