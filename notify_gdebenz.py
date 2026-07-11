#!/usr/bin/env python3
"""
Консольный запуск бота ГдеБЕНЗ.

Настройки читаются из config.json (его удобнее редактировать через
gdebenz_gui.py, чем руками). Если config.json ещё нет — при первом
запуске GUI он создастся автоматически со значениями по умолчанию.

Режимы:
  python3 notify_gdebenz.py --test   — тестовое сообщение
  python3 notify_gdebenz.py --once   — одна проверка карты
  python3 notify_gdebenz.py          — постоянный цикл (Ctrl+C для остановки)
"""

import sys
import time

import gdebenz_core as core


def main():
    args = sys.argv[1:]
    config = core.load_config()

    if "--test" in args:
        ok, msg = core.send_test_message(config)
        print(msg if ok else f"[!] {msg}")
        return

    if "--once" in args:
        checked, notified, log_lines = core.check_once(config)
        for line in log_lines:
            print(line)
        print(f"Проверено станций: {checked}. Отправлено уведомлений: {notified}.")
        return

    interval = config.get("check_interval_seconds", 60)
    print(f"Бот запущен. Проверка каждые {interval} сек. Остановить — Ctrl+C.")
    while True:
        try:
            config = core.load_config()  # перечитываем на случай правок в GUI
            checked, notified, log_lines = core.check_once(config)
            for line in log_lines:
                print(line)
            print(f"[{time.strftime('%H:%M:%S')}] Проверено: {checked}, уведомлений: {notified}.")
        except Exception as e:
            print(f"[!] Ошибка при проверке: {e}", file=sys.stderr)
        time.sleep(config.get("check_interval_seconds", 60))


if __name__ == "__main__":
    main()
