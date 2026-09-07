#!/usr/bin/env python3
"""CLI для запуска рассылки клиента через Salebot Broadcast API.

Использование:
    python3 send_broadcast.py --client "Имя клиента" --message "Текст рассылки"
    python3 send_broadcast.py --client "Имя клиента" --message "Текст" --group-id 12345
    python3 send_broadcast.py --client "Имя клиента" --message "Текст" --dry-run

Данные клиентов (bot_id / api_key / аудитория по умолчанию) берутся из
clients.json рядом со скриптом — см. clients.example.json для формата.
Скрипт не отправит ничего без вашего явного подтверждения (y/N в терминале),
если только явно не передан --yes.

Точный список поддерживаемых Salebot параметров см. в официальной
документации: https://docs.salebot.pro/rabota-s-api/api-konstruktora
(нужен тариф Бизнес/Инфобиз). Любые дополнительные поля можно передать через
--param key=value, не редактируя код.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "clients.json"
API_URL_TEMPLATE = "https://chatter.salebot.pro/api/{api_key}/broadcast"


def load_clients() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(
            f"Не найден {CONFIG_PATH}.\n"
            f"Скопируйте clients.example.json в clients.json и впишите реальные "
            f"bot_id/api_key для каждого клиента (берутся в настройках проекта в Salebot)."
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def parse_extra_params(pairs: list[str]) -> dict:
    extra = {}
    for pair in pairs:
        if "=" not in pair:
            sys.exit(f"Некорректный --param '{pair}', ожидается формат key=value")
        key, value = pair.split("=", 1)
        extra[key] = value
    return extra


def build_payload(bot_id: str, message: str, group_id: str | None, send_time: str | None,
                   time_shift: str | None, extra: dict) -> dict:
    payload = {"bot_id": bot_id, "message": message}
    if group_id:
        payload["group_id"] = group_id
    if send_time:
        payload["send_time"] = send_time
    if time_shift:
        payload["time_shift"] = time_shift
    payload.update(extra)
    return payload


def send_broadcast(api_key: str, payload: dict) -> dict:
    url = API_URL_TEMPLATE.format(api_key=api_key)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        sys.exit(f"Salebot вернул ошибку HTTP {e.code}: {body}")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw_response": body}


def main() -> None:
    parser = argparse.ArgumentParser(description="Отправить рассылку клиента через Salebot API")
    parser.add_argument("--client", required=True, help="Имя клиента как в clients.json")
    parser.add_argument("--message", required=True, help="Текст рассылки")
    parser.add_argument("--group-id", default=None,
                         help="ID списка/аудитории (по умолчанию — default_group_id из clients.json)")
    parser.add_argument("--send-time", default=None, help="Дата и время отправки 'YYYY-MM-DD HH:MM:SS'")
    parser.add_argument("--time-shift", default=None, help="Отправить через N секунд от текущего момента")
    parser.add_argument("--param", action="append", default=[],
                         help="Доп. параметр key=value из документации Salebot")
    parser.add_argument("--dry-run", action="store_true", help="Показать, что будет отправлено, но не отправлять")
    parser.add_argument("--yes", action="store_true", help="Не спрашивать подтверждение перед отправкой")
    args = parser.parse_args()

    clients = load_clients()
    client = clients.get(args.client)
    if not client:
        sys.exit(f"Клиент '{args.client}' не найден в clients.json. Доступные: {', '.join(clients) or '(пусто)'}")

    group_id = args.group_id or client.get("default_group_id")
    extra = parse_extra_params(args.param)
    payload = build_payload(client["bot_id"], args.message, group_id, args.send_time, args.time_shift, extra)

    print(f"Клиент: {args.client}")
    print(f"bot_id: {client['bot_id']}")
    print(f"Аудитория (group_id): {group_id or '(не указана — уйдёт по умолчанию согласно настройкам Salebot)'}")
    print(f"Текст:\n{args.message}\n")

    if args.dry_run:
        print("(dry-run, запрос не отправлен)")
        print("Payload:", json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if not args.yes:
        confirm = input("Отправить рассылку? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Отменено.")
            return

    result = send_broadcast(client["api_key"], payload)
    print("Ответ Salebot:", json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
