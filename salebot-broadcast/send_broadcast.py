#!/usr/bin/env python3
"""CLI для запуска рассылки клиента через Salebot Broadcast API.

Использование:
    python3 send_broadcast.py --client "Имя клиента" --message "Текст рассылки"
    python3 send_broadcast.py --client "Имя клиента" --message "Текст" --group-id 12345
    python3 send_broadcast.py --client "Имя клиента" --message "Текст" --dry-run

Данные клиентов (group_id списка / api_key) берутся из clients.json рядом
со скриптом — см. clients.example.json для формата. Разные аудитории
(например, разные боты одного проекта) различаются по group_id — это ID
списка в Salebot, каждый список привязан к своей аудитории/боту.

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
            f"group_id/api_key для каждого получателя (список в Salebot -> ID списка)."
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def print_clients_list(clients: dict) -> None:
    if not clients:
        print("В clients.json пока ничего не настроено.")
        return
    print("Настроенные получатели рассылок:")
    for name, cfg in clients.items():
        username = cfg.get("telegram_username")
        username_part = f" ({username})" if username else ""
        print(f"  - {name}{username_part}  [group_id: {cfg.get('group_id')}]")


def parse_extra_params(pairs: list[str]) -> dict:
    extra = {}
    for pair in pairs:
        if "=" not in pair:
            sys.exit(f"Некорректный --param '{pair}', ожидается формат key=value")
        key, value = pair.split("=", 1)
        extra[key] = value
    return extra


def build_payload(message: str, group_id: str | None = None, send_time: str | None = None,
                   time_shift: str | None = None, extra: dict | None = None) -> dict:
    payload = {"message": message}
    if group_id:
        payload["group_id"] = group_id
    if send_time:
        payload["send_time"] = send_time
    if time_shift:
        payload["time_shift"] = time_shift
    payload.update(extra or {})
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
    parser.add_argument("--client", default=None, help="Имя получателя как в clients.json")
    parser.add_argument("--group-id", default=None,
                         help="ID списка (переопределяет group_id из clients.json)")
    parser.add_argument("--send-time", default=None, help="Дата и время отправки 'YYYY-MM-DD HH:MM:SS'")
    parser.add_argument("--time-shift", default=None, help="Отправить через N секунд от текущего момента")
    parser.add_argument("--param", action="append", default=[],
                         help="Доп. параметр key=value из документации Salebot")
    parser.add_argument("--dry-run", action="store_true", help="Показать, что будет отправлено, но не отправлять")
    parser.add_argument("--yes", action="store_true", help="Не спрашивать подтверждение перед отправкой")
    parser.add_argument("--list", action="store_true",
                         help="Показать всех настроенных получателей из clients.json и выйти")
    parser.add_argument("--message", default=None, help="Текст рассылки")
    args = parser.parse_args()

    clients = load_clients()

    if args.list:
        print_clients_list(clients)
        return

    if not args.client or not args.message:
        sys.exit("Нужны --client и --message (или используйте --list, чтобы увидеть доступных получателей).")

    client = clients.get(args.client)
    if not client:
        print_clients_list(clients)
        sys.exit(f"\nПолучатель '{args.client}' не найден в clients.json — см. список выше.")

    group_id = args.group_id or client.get("group_id")
    extra = parse_extra_params(args.param)
    payload = build_payload(args.message, group_id, args.send_time, args.time_shift, extra)

    username = client.get("telegram_username")
    print(f"Получатель: {args.client}" + (f" ({username})" if username else ""))
    print(f"Список (group_id): {group_id or '(не указан!)'}")
    print(f"Текст:\n{args.message}\n")
    print("⚠️  Проверьте, что получатель и список выше — тот самый, куда должна уйти именно эта рассылка.")

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
