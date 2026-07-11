#!/usr/bin/env python3
"""
gdebenz_gui.py — окно настроек бота ГдеБЕНЗ.

Запускать: python3 gdebenz_gui.py

Позволяет вписать токен/chat_id, выбрать город или координаты, задать
избранные заправки, интервал проверки — и запускать/останавливать
мониторинг кнопками, без редактирования кода.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

import gdebenz_core as core


class GdeBenzApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ГдеБЕНЗ — бот-уведомитель")
        self.root.geometry("560x680")

        self.config = core.load_config()
        self.monitor_thread = None
        self.stop_event = threading.Event()
        self.running = False

        self._build_ui()
        self._load_values_into_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        row = 0

        ttk.Label(frame, text="Telegram-бот", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad
        )
        row += 1

        ttk.Label(frame, text="Bot Token:").grid(row=row, column=0, sticky="w", **pad)
        self.token_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.token_var, width=42, show="•").grid(
            row=row, column=1, sticky="we", **pad
        )
        row += 1

        ttk.Label(frame, text="Chat ID:").grid(row=row, column=0, sticky="w", **pad)
        self.chat_id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.chat_id_var, width=42).grid(
            row=row, column=1, sticky="we", **pad
        )
        row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="we", pady=8)
        row += 1

        ttk.Label(frame, text="Город / зона поиска", font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", **pad
        )
        row += 1

        ttk.Label(frame, text="Быстрый выбор города:").grid(row=row, column=0, sticky="w", **pad)
        self.city_var = tk.StringVar()
        city_combo = ttk.Combobox(
            frame, textvariable=self.city_var,
            values=list(core.CITY_PRESETS.keys()), state="readonly", width=39
        )
        city_combo.grid(row=row, column=1, sticky="we", **pad)
        city_combo.bind("<<ComboboxSelected>>", self._on_city_selected)
        row += 1

        ttk.Label(frame, text="Широта (lat):").grid(row=row, column=0, sticky="w", **pad)
        self.lat_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.lat_var, width=42).grid(row=row, column=1, sticky="we", **pad)
        row += 1

        ttk.Label(frame, text="Долгота (lon):").grid(row=row, column=0, sticky="w", **pad)
        self.lon_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.lon_var, width=42).grid(row=row, column=1, sticky="we", **pad)
        row += 1

        ttk.Label(frame, text="Радиус, км:").grid(row=row, column=0, sticky="w", **pad)
        self.radius_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.radius_var, width=42).grid(row=row, column=1, sticky="we", **pad)
        row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="we", pady=8)
        row += 1

        ttk.Label(frame, text="Избранные заправки (osm_id, через запятую)."
                              " Пусто = следить за всеми в радиусе:",
                  wraplength=520, justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", **pad
        )
        row += 1

        self.favorites_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.favorites_var, width=60).grid(
            row=row, column=0, columnspan=2, sticky="we", **pad
        )
        row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="we", pady=8)
        row += 1

        ttk.Label(frame, text="Уведомлять при статусах:").grid(row=row, column=0, sticky="w", **pad)
        status_frame = ttk.Frame(frame)
        status_frame.grid(row=row, column=1, sticky="w", **pad)
        self.status_vars = {}
        for i, (code, label) in enumerate([
            ("yes", "Есть"), ("queue", "Очередь"), ("low", "Мало"), ("limit", "Лимит")
        ]):
            v = tk.BooleanVar()
            self.status_vars[code] = v
            ttk.Checkbutton(status_frame, text=label, variable=v).grid(row=0, column=i, padx=4)
        row += 1

        ttk.Label(frame, text="Интервал проверки, сек:").grid(row=row, column=0, sticky="w", **pad)
        self.interval_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.interval_var, width=42).grid(row=row, column=1, sticky="we", **pad)
        row += 1

        self.ssl_var = tk.BooleanVar()
        ttk.Checkbutton(
            frame, text="Отключить проверку SSL-сертификата (нужно для некоторых VPN)",
            variable=self.ssl_var
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="we", pady=8)
        row += 1

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(btn_frame, text="💾 Сохранить настройки", command=self.save_settings).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🧪 Тестовое сообщение", command=self.send_test).pack(side="left", padx=4)
        self.start_btn = ttk.Button(btn_frame, text="▶ Запустить мониторинг", command=self.start_monitoring)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="■ Остановить", command=self.stop_monitoring, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        row += 1

        self.status_label = ttk.Label(frame, text="Статус: остановлен", foreground="gray")
        self.status_label.grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        ttk.Label(frame, text="Журнал:").grid(row=row, column=0, sticky="w", **pad)
        row += 1

        self.log_widget = scrolledtext.ScrolledText(frame, height=14, width=68, state="disabled")
        self.log_widget.grid(row=row, column=0, columnspan=2, sticky="nsew", **pad)
        frame.rowconfigure(row, weight=1)
        frame.columnconfigure(1, weight=1)

    def _on_city_selected(self, event=None):
        city = self.city_var.get()
        if city in core.CITY_PRESETS:
            lat, lon = core.CITY_PRESETS[city]
            self.lat_var.set(str(lat))
            self.lon_var.set(str(lon))

    # ------------------------------------------------------------------
    # Загрузка/сохранение конфига
    # ------------------------------------------------------------------
    def _load_values_into_ui(self):
        c = self.config
        self.token_var.set(c.get("telegram_bot_token", ""))
        self.chat_id_var.set(str(c.get("telegram_chat_id", "")))
        self.lat_var.set(str(c.get("lat", "")))
        self.lon_var.set(str(c.get("lon", "")))
        self.radius_var.set(str(c.get("radius_km", "")))
        self.favorites_var.set(", ".join(c.get("favorites") or []))
        self.interval_var.set(str(c.get("check_interval_seconds", 60)))
        self.ssl_var.set(bool(c.get("disable_ssl_verify", False)))
        statuses = set(c.get("notify_statuses") or [])
        for code, var in self.status_vars.items():
            var.set(code in statuses)

    def _collect_config_from_ui(self):
        try:
            lat = float(self.lat_var.get())
            lon = float(self.lon_var.get())
            radius = float(self.radius_var.get())
            interval = int(self.interval_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Широта/долгота/радиус/интервал должны быть числами.")
            return None

        favorites_raw = self.favorites_var.get().strip()
        favorites = [x.strip() for x in favorites_raw.split(",") if x.strip()] if favorites_raw else []

        notify_statuses = [code for code, var in self.status_vars.items() if var.get()]

        return {
            "telegram_bot_token": self.token_var.get().strip(),
            "telegram_chat_id": self.chat_id_var.get().strip(),
            "lat": lat,
            "lon": lon,
            "radius_km": radius,
            "favorites": favorites,
            "notify_statuses": notify_statuses,
            "check_interval_seconds": interval,
            "disable_ssl_verify": self.ssl_var.get(),
        }

    def save_settings(self):
        config = self._collect_config_from_ui()
        if config is None:
            return
        self.config = config
        core.save_config(config)
        self._log("Настройки сохранены в config.json.")
        messagebox.showinfo("Готово", "Настройки сохранены.")

    # ------------------------------------------------------------------
    # Действия
    # ------------------------------------------------------------------
    def send_test(self):
        config = self._collect_config_from_ui()
        if config is None:
            return
        self._log("Отправляю тестовое сообщение...")
        ok, msg = core.send_test_message(config)
        self._log(("✅ " if ok else "❌ ") + msg)
        if not ok:
            messagebox.showerror("Ошибка отправки", msg)

    def start_monitoring(self):
        config = self._collect_config_from_ui()
        if config is None:
            return
        if not config["telegram_bot_token"] or not config["telegram_chat_id"]:
            messagebox.showerror("Ошибка", "Заполните Bot Token и Chat ID.")
            return

        self.config = config
        core.save_config(config)

        self.stop_event.clear()
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Статус: работает", foreground="green")

        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self._log("Мониторинг запущен.")

    def stop_monitoring(self):
        self.stop_event.set()
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Статус: остановлен", foreground="gray")
        self._log("Мониторинг остановлен.")

    def _monitor_loop(self):
        while not self.stop_event.is_set():
            try:
                config = core.load_config()
                checked, notified, log_lines = core.check_once(config)
                for line in log_lines:
                    self._log(line)
                self._log(f"[{time.strftime('%H:%M:%S')}] Проверено: {checked}, уведомлений: {notified}.")
            except Exception as e:
                self._log(f"[!] Ошибка проверки: {e}")

            interval = self.config.get("check_interval_seconds", 60)
            for _ in range(interval):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    def _log(self, text):
        def append():
            self.log_widget.config(state="normal")
            self.log_widget.insert("end", text + "\n")
            self.log_widget.see("end")
            self.log_widget.config(state="disabled")
        self.root.after(0, append)


def main():
    root = tk.Tk()
    app = GdeBenzApp(root)

    def on_close():
        app.stop_event.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
