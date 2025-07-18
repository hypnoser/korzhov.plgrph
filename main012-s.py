# Частина 1: Імпорти, конфігурація, допоміжні функції
# Для об’єднання: розмістіть цей код на початку файлу main011-s.py
# Залежності: tkinter, uuid, json, os, datetime, random, time, csv, statistics, scipy.stats, textwrap

import tkinter as tk
from tkinter import messagebox
import uuid
import json
import os
import datetime
import random
import time
import csv
import statistics
from scipy.stats import ttest_ind
import textwrap

def load_config():
    try:
        with open('config.json', encoding='utf-8') as f:
            config = json.load(f)
            bg_color = config.get("bg_color", "#000000")
            for lang in config.get("stroop_colors", {}):
                for color in config["stroop_colors"][lang].values():
                    if color.lower() == bg_color.lower():
                        raise ValueError(f"Color {color} in stroop_colors matches bg_color {bg_color}, causing invisibility")
            return config
    except Exception as e:
        messagebox.showerror("Помилка", f"Не вдалося прочитати config.json:\n{e}")
        exit(1)

def load_stimuli():
    try:
        with open('stimuli.txt', encoding='utf-8') as f:
            stimuli = [(row[0].strip(), row[1].strip()) for row in csv.reader(f) if row and len(row) >= 2]
            categories = [cat for _, cat in stimuli]
            if len([c for c in categories if c == "sensitive"]) < 5:
                raise ValueError("stimuli.txt must contain at least 5 sensitive stimuli")
            if len([c for c in categories if c == "neutral"]) < 5:
                raise ValueError("stimuli.txt must contain at least 5 neutral stimuli")
            if len([c for c in categories if c == "positive"]) < 5:
                raise ValueError("stimuli.txt must contain at least 5 positive stimuli")
            return stimuli
    except Exception as e:
        messagebox.showerror("Помилка", f"Не вдалося прочитати stimuli.txt:\n{e}")
        exit(1)

def safe_mkdir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def gen_uuid():
    return f"Respondent_{random.randint(1, 1000)}"  # ЗМІНА ВІД 17.07.2025: Спрощений UUID для звіту

def now():
    return datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S EEST")  # ЗМІНА ВІД 17.07.2025: Формат дати для звіту

def hide_cursor(widget):
    widget.config(cursor="none")

def show_cursor(widget):
    widget.config(cursor="")

class PsychoSemanticTestApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Психосемантичний тест")
        self.config = load_config()
        if "max_miss_attempts" not in self.config:
            self.log("WARNING", "Параметр max_miss_attempts не знайдено в config.json, використовується значення за замовчуванням: 5")
        self.stimuli_main = load_stimuli()
        self.session_id = None
        self.session_folder = None
        self.person_info = {}
        self.lang = 'ua'
        self.stage = None
        self.log_file = None
        self.report_file = None
        self.log_data = []
        self.results = {
            'preparation': [], 'calibration': [], 'calibration_repeat': [],
            'reference': [], 'reference_repeat': [], 'main': [], 'main_repeat': []
        }
        self.buffer_symbols = self.config.get("buffer_symbols", "01010010110010101001011010011001")
        self.test_start_time = None
        self.test_end_time = None
        self.last_pause_time = None
        self._setup_fonts_colors()
        self.show_personal_data_form()
        self.master.bind('<Escape>', lambda e: self._on_escape())
        self.missed_stimuli = {}
        self.press_time = None
        self.sequence_position = 0  # ЗМІНА ВІД 17.07.2025: Додано для аналізу послідовності (POS)

    def _setup_fonts_colors(self):
        cfg = self.config
        self.border_width = cfg.get("border_width", 20)
        self.border_color = cfg.get("border_color", "#FFD700")
        self.bg_color = "#000000"
        font_name = cfg.get("probe_font", "Arial")
        font_size = cfg.get("probe_font_size", 44)
        self.font_probe = (font_name, font_size, "bold")
        self.font_mask = (font_name, font_size, "bold")
        self.font_info = (cfg.get("info_font", "Arial"), cfg.get("info_font_size", 32), "bold")
        self.info_color = cfg.get("info_color", "#FFFFFF")

    def show_personal_data_form(self):
        self.clear_widgets()
        self.master.attributes('-fullscreen', True)
        self.master.configure(bg=self.bg_color)
        font_small = ("Arial", 22, "bold")
        font_input = ("Arial", 20)
        frm = tk.Frame(self.master, bg=self.bg_color)
        frm.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(frm, text="ПІБ респондента:", font=font_small, fg=self.info_color, bg=self.bg_color).grid(row=0, column=0, pady=(10,5), sticky="e")
        self.fio_var = tk.StringVar()
        tk.Entry(frm, font=font_input, textvariable=self.fio_var, justify="center", width=28).grid(row=0, column=1, pady=(10,5), padx=12)
        tk.Label(frm, text="Дата народження (ДД.ММ.РРРР):", font=font_small, fg=self.info_color, bg=self.bg_color).grid(row=1, column=0, pady=5, sticky="e")
        self.birth_var = tk.StringVar()
        tk.Entry(frm, font=font_input, textvariable=self.birth_var, justify="center", width=28).grid(row=1, column=1, pady=5, padx=12)
        tk.Label(frm, text="Оберіть мову тесту:", font=font_small, fg=self.info_color, bg=self.bg_color).grid(row=2, column=0, pady=5, sticky="e")
        self.lang_var = tk.StringVar(value='ua')
        langs = [("Українська", "ua"), ("Русский", "ru")]
        lang_frame = tk.Frame(frm, bg=self.bg_color)
        lang_frame.grid(row=2, column=1, pady=5, sticky="w")
        for (txt, val) in langs:
            tk.Radiobutton(lang_frame, text=txt, font=font_input, fg=self.info_color, bg=self.bg_color,
                           variable=self.lang_var, value=val, selectcolor=self.bg_color, anchor="w", width=13).pack(side="left", padx=4)
        self.consent_var = tk.BooleanVar()
        tk.Checkbutton(frm, text="Даю згоду на обробку своїх персональних даних", variable=self.consent_var,
                       font=font_input, fg=self.info_color, bg=self.bg_color, selectcolor=self.bg_color).grid(row=3, columnspan=2, pady=10)
        btn = tk.Button(frm, text="Почати тестування", font=font_small, width=20, height=2, command=self.validate_and_start)
        btn.grid(row=4, columnspan=2, pady=(16, 12))
        self.master.bind('<Return>', lambda e: self.validate_and_start())

    def validate_and_start(self):
        fio = self.fio_var.get().strip()
        birth = self.birth_var.get().strip()
        consent = self.consent_var.get()
        lang = self.lang_var.get()
        if not fio or not birth or not consent:
            messagebox.showwarning("Помилка", "Заповніть всі поля та дайте згоду на обробку даних.")
            return
        try:
            datetime.datetime.strptime(birth, "%d.%m.%Y")
        except:
            messagebox.showwarning("Помилка", "Введіть дату у форматі ДД.ММ.РРРР.")
            return
        self.person_info = {
            'fio': fio,
            'birth': birth,
            'lang': lang,
            'consent': True,
            'start_time': now(),
            'uuid': gen_uuid()
        }
        self.lang = lang
        self._start_session()
        self.show_instructions()

# Продовження в частині 2
    # Частина 2: Методи для показу інструкцій, адаптації, калібрування та основного тесту
# Для об’єднання: розмістіть цей код після частини 1 у файлі main011-s.py
# Залежності: методи з частини 1, tkinter, datetime, random

    def show_instructions(self):
        self.clear_widgets()
        self.master.configure(bg=self.bg_color)
        self.master.attributes("-fullscreen", True)
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        border = 5
        canvas = tk.Canvas(self.master, width=w, height=h, bg=self.bg_color, highlightthickness=0)
        canvas.place(x=0, y=0)
        canvas.create_rectangle(border, border, w-border, h-border, outline="#FFD700", width=border)
        frame = tk.Frame(self.master, bg=self.bg_color)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        lang = getattr(self, "lang_var", None)
        if lang:
            lang = lang.get()
        else:
            lang = self.config.get("languages", ["ua"])[0]
        instruct_text = self.config.get("instructions", {}).get(lang, "Немає інструкції для цієї мови.")
        font_title = ("Arial", 40, "bold")
        font_instr = ("Arial", 26)
        title = "Інструкція до тесту" if lang == "ua" else "Инструкция к тесту"
        tk.Label(frame, text=title, font=font_title, fg="#FFD700", bg=self.bg_color).pack(pady=(10,30))
        tk.Label(frame, text=instruct_text, font=font_instr, fg="white", bg=self.bg_color, justify="center", wraplength=int(w*0.7)).pack(padx=20)
        self.master.bind('<Return>', self.on_instruction_enter)

    def on_instruction_enter(self, event=None):
        self.master.unbind('<Return>')
        self.clear_widgets()
        self.show_countdown(3, self.start_adaptation)

    def show_countdown(self, seconds, callback):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        lbl = tk.Label(self.master, text=f"Підготовка...\n{seconds}", font=("Arial", 36, "bold"), fg="#FFD700", bg=self.bg_color)
        lbl.place(relx=0.5, rely=0.5, anchor="center")
        if seconds > 1:
            self.master.after(1000, lambda: self.show_countdown(seconds-1, callback))
        else:
            self.master.after(1000, callback)

    def start_adaptation(self):
        self.stage = "adaptation"
        self.test_start_time = time.perf_counter()
        self.last_pause_time = self.test_start_time
        self.log("INFO", "--- Адаптаційний блок ---")
        buf = self.buffer_symbols
        count = self.config.get("adaptation_buffer_count", 30)
        block = [buf] * count
        self._run_adaptation_block(block, next_callback=self.repeat_missed_adaptation)

    def repeat_missed_adaptation(self):
        self.stage = "adaptation_repeat"
        self.log("INFO", "--- Повторення пропущених адаптаційних стимулів ---")
        block = []
        max_attempts = self.config.get("max_miss_attempts", 5)
        for (stim, cat), data in self.missed_stimuli.items():
            if cat == "buffer" and data["valid_count"] < 3 and data["attempts"] < max_attempts:
                remaining = min(3 - data["valid_count"], max_attempts - data["attempts"])
                block.extend([stim] * remaining)
        random.shuffle(block)
        if block:
            self.log("INFO", f"Повторення адаптаційних стимулів: {len(block)}")
            self._run_adaptation_block(block, next_callback=self.after_adaptation)
        else:
            self.log("INFO", "Пропущені адаптаційні стимули відсутні або досягнуто 3 валідні реакції")
            self.missed_stimuli = {k: v for k, v in self.missed_stimuli.items() if v["valid_count"] < 3 and v["attempts"] < max_attempts}
            self.after_adaptation()

    def _run_adaptation_block(self, block, next_callback):
        self.clear_widgets()
        self.current_block = block
        self.block_results = []
        self.current_idx = 0
        self.block_next_callback = next_callback
        hide_cursor(self.master)
        self._next_adaptation_stimulus()

    def _next_adaptation_stimulus(self):
        current_time = time.perf_counter()
        pause_interval_sec = self.config.get("pause_interval_min", 5) * 60
        if self.test_start_time and (current_time - self.last_pause_time) >= pause_interval_sec:
            self._show_pause_screen()
            return
        if self.current_idx >= len(self.current_block):
            self.results[self.stage] = self.block_results
            show_cursor(self.master)
            self.block_next_callback()
            return
        stim = self.current_block[self.current_idx]
        self.current_idx += 1
        self.sequence_position += 1  # ЗМІНА ВІД 17.07.2025: Оновлення позиції для POS
        self._show_adaptation_stimulus(stim)

    def _show_adaptation_stimulus(self, stim):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        self.reaction_captured = False
        self.stimulus_shown_time = time.perf_counter()
        self.stimulus_value = stim
        self.stimulus_cat = "buffer"
        self.stimulus_logged = False
        self.master.bind("<space>", self._on_space_adaptation)
        self.master.bind("<KeyRelease-space>", self._on_space_release_adaptation)
        show_ts = datetime.datetime.now().isoformat(timespec='milliseconds')
        self.log("SHOW", f"{self.stage}|{stim}|buffer|start|{show_ts}")
        stim_dur = self._get_probe_duration("buffer")
        mask_dur = self.config.get("mask_duration_ms", 100)
        pause_ms = self.config.get("adaptation_pause_ms", 1000)
        self.stimulus_timer = self.master.after(stim_dur, lambda: self._show_mask_adaptation(stim))
        self.mask_timer = self.master.after(stim_dur + mask_dur, lambda: self._show_pause_adaptation(stim, pause_ms))
        self.pause_timer = self.master.after(stim_dur + mask_dur + pause_ms, lambda: self._close_reaction_adaptation(stim))

    def _show_mask_adaptation(self, stim):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        mask_txt = self._generate_mask()
        rect_pad = self.config.get("mask_frame", {}).get("pad", 32)
        rect_color = self.config.get("mask_frame", {}).get("color", "#FFFFFF")
        rect_width = self.config.get("mask_frame", {}).get("width", 8)
        text_id = canvas.create_text(w//2, h//2, text=mask_txt, fill="white", font=self.font_mask)
        bbox = canvas.bbox(text_id)
        if bbox:
            x0, y0, x1, y1 = bbox
            canvas.create_rectangle(x0-rect_pad, y0-rect_pad, x1+rect_pad, y1+rect_pad, outline=rect_color, width=rect_width)
            canvas.lift(text_id)

    def _show_pause_adaptation(self, stim, pause_ms):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)

    def _on_space_adaptation(self, event):
        if self.reaction_captured or self.stimulus_logged:
            return
        self.press_time = time.perf_counter()
        t_react = int((self.press_time - self.stimulus_shown_time) * 1000)
        react_ts = datetime.datetime.now().isoformat(timespec='milliseconds')
        stim_key = (self.stimulus_value, self.stimulus_cat)
        if stim_key not in self.missed_stimuli:
            self.missed_stimuli[stim_key] = {"valid_count": 0, "attempts": 0}
        self.missed_stimuli[stim_key]["attempts"] += 1
        if t_react < 50 or t_react > 2000:
            reason = "Передчасна реакція" if t_react < 50 else "Запізніла реакція"
            self.log("MISS", f"{self.stage}|{self.stimulus_value}|buffer|{t_react}|{reason}|{react_ts}")
            res = {"stimulus": self.stimulus_value, "category": "buffer", "reaction": None, "t": t_react, "miss": True, "reason": reason, "press_duration": None, "stage": self.stage, "sequence_position": self.sequence_position}  # ЗМІНА ВІД 17.07.2025: Додано sequence_position
        else:
            self.log("REACTION", f"{self.stage}|{self.stimulus_value}|buffer|{t_react}|OK|{react_ts}")
            res = {"stimulus": self.stimulus_value, "category": "buffer", "reaction": t_react, "miss": False, "press_duration": None, "stage": self.stage, "sequence_position": self.sequence_position}  # ЗМІНА ВІД 17.07.2025: Додано sequence_position
            self.missed_stimuli[stim_key]["valid_count"] += 1
        self.block_results.append(res)
        self.stimulus_logged = True
        self.reaction_captured = True
        self.master.unbind("<space>")

    def _on_space_release_adaptation(self, event):
        if not self.stimulus_logged:
            return
        release_time = time.perf_counter()
        if self.press_time:
            press_duration_ms = int((release_time - self.press_time) * 1000)
            for res in self.block_results[-1:]:
                if res["stimulus"] == self.stimulus_value and res["category"] == self.stimulus_cat:
                    res["press_duration"] = press_duration_ms
                    self.log("REACTION", f"{self.stage}|{self.stimulus_value}|buffer|press_duration={press_duration_ms}")
        self.press_time = None
        self.master.unbind("<KeyRelease-space>")

    def _close_reaction_adaptation(self, stim):
        self.reaction_captured = True
        self.master.unbind("<space>")
        self.master.unbind("<KeyRelease-space>")
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        if not self.stimulus_logged:
            stim_key = (self.stimulus_value, self.stimulus_cat)
            if stim_key not in self.missed_stimuli:
                self.missed_stimuli[stim_key] = {"valid_count": 0, "attempts": 0}
            self.missed_stimuli[stim_key]["attempts"] += 1
            self.log("MISS", f"{self.stage}|{self.stimulus_value}|buffer|no_response|Пропуск|{datetime.datetime.now().isoformat(timespec='milliseconds')}")
            res = {"stimulus": self.stimulus_value, "category": self.stimulus_cat, "reaction": None, "t": None, "miss": True, "reason": "no_response", "press_duration": None, "stage": self.stage, "sequence_position": self.sequence_position}  # ЗМІНА ВІД 17.07.2025: Додано sequence_position
            self.block_results.append(res)
        post_reaction_delay = self.config.get("post_reaction_delay_ms", 300)
        self.master.after(post_reaction_delay, self._next_adaptation_stimulus)

    def after_adaptation(self):
        block_data = self.results.get("adaptation", [])
        reacts = [d["reaction"] for d in block_data if d["reaction"] is not None]
        miss_count = len([d for d in block_data if d["reaction"] is None])
        n = len(block_data)
        miss_pct = (miss_count / n) * 100 if n else 100
        m = int(sum(reacts)/len(reacts)) if reacts else 0
        min_pause = 600
        if miss_pct <= 15 and m < 700:
            min_pause = 600
        elif miss_pct <= 15 and 700 <= m <= 950:
            min_pause = ((m + 300) // 100) * 100
        else:
            min_pause = max(1000, min(((m + 500) // 100) * 100, 1100))
        max_pause = min(min_pause + 500, 1100)
        self.config["pause_range_ms"] = {
            "default": [min_pause, max_pause],
            "neutral": [min_pause, max_pause],
            "sensitive": [min_pause + 100, max_pause],
            "cognitive": [min_pause + 200, max_pause]
        }
        self.log("INFO", f"Адаптація завершена: середній час={m} мс, пропуски={miss_pct:.1f}%, нова пауза={min_pause}-{max_pause} мс")
        self.start_preparation()

    def start_preparation(self):
        self.master.unbind("<Return>")
        self.log("INFO", "=== Початок тесту ===")
        self.stage = "preparation"
        block = []
        for w in self.config['relaxation_words'][self.lang]:
            block += [w] * self.config.get("preparation_repeats", 3)
        random.shuffle(block)
        self._run_simple_block(block, next_callback=self.start_calibration)

    def start_calibration(self):
        self.stage = "calibration"
        self.log("INFO", "--- Калібрування ---")
        buf = self.buffer_symbols
        block = []
        neutral_count = self.config.get("calibration_neutral_count", 6)
        buffer_per_neutral = self.config.get("calibration_buffer_per_neutral", 0.67)
        neutral_words = self.config['neutral_words'][self.lang][:neutral_count]
        for stim in neutral_words:
            if random.random() < buffer_per_neutral:
                block.append((buf, "buffer"))
            block.append((stim, "neutral"))
        random.shuffle(block)
        self.log("INFO", f"Калібрувальний блок: {len(neutral_words)} нейтральних, {len(block) - len(neutral_words)} буферних")
        self._run_stimulus_block(block, next_callback=self.repeat_missed_calibration)

    def repeat_missed_calibration(self):
        self.stage = "calibration_repeat"
        self.log("INFO", "--- Повторення пропущених калібрувальних стимулів ---")
        block = []
        max_attempts = self.config.get("max_miss_attempts", 5)
        for (stim, cat), data in self.missed_stimuli.items():
            if cat in ["neutral", "buffer"] and data["valid_count"] < 3 and data["attempts"] < max_attempts:
                remaining = min(3 - data["valid_count"], max_attempts - data["attempts"])
                block.extend([(stim, cat)] * remaining)
        random.shuffle(block)
        final_block = []
        buf = self.buffer_symbols
        for stim, cat in block:
            final_block.append((buf, "buffer"))
            final_block.append((stim, cat))
            final_block.append((buf, "buffer"))
        if final_block:
            self.log("INFO", f"Повторення калібрувальних стимулів: {len(block)}")
            self._run_stimulus_block(final_block, next_callback=self.start_reference)
        else:
            self.log("INFO", "Пропущені калібрувальні стимули відсутні або досягнуто 3 валідні реакції")
            self.missed_stimuli = {k: v for k, v in self.missed_stimuli.items() if v["valid_count"] < 3 and v["attempts"] < max_attempts}
            self.start_reference()

    def start_reference(self):
        self.stage = "reference"
        self.log("INFO", "--- Реперний блок ---")
        block = []
        words = []
        for cat in ["sensitive", "neutral", "cognitive"]:
            words += [(w, cat) for w in self.config["reference_words"][self.lang][cat]]
        n_rep = self.config.get("reference_test_config", {}).get("repetitions", 3)
        words = words * n_rep
        random.shuffle(words)
        buf = self.buffer_symbols
        for stim, cat in words:
            block.append((buf, "buffer"))
            block.append((stim, cat))
            block.append((buf, "buffer"))
        self.log("INFO", f"Реперний блок: {len(words)} стимулів, {len(block) - len(words)} буферних")
        self._run_stimulus_block(block, next_callback=self.repeat_missed_reference)

    def repeat_missed_reference(self):
        self.stage = "reference_repeat"
        self.log("INFO", "--- Повторення пропущених реперних стимулів ---")
        block = []
        max_attempts = self.config.get("max_miss_attempts", 5)
        for (stim, cat), data in self.missed_stimuli.items():
            if cat in ["sensitive", "neutral", "cognitive", "buffer"] and data["valid_count"] < 3 and data["attempts"] < max_attempts:
                remaining = min(3 - data["valid_count"], max_attempts - data["attempts"])
                block.extend([(stim, cat)] * remaining)
        random.shuffle(block)
        final_block = []
        buf = self.buffer_symbols
        for stim, cat in block:
            final_block.append((buf, "buffer"))
            final_block.append((stim, cat))
            final_block.append((buf, "buffer"))
        if final_block:
            self.log("INFO", f"Повторення реперних стимулів: {len(block)}")
            self._run_stimulus_block(final_block, next_callback=self.start_main)
        else:
            self.log("INFO", "Пропущені реперні стимули відсутні або досягнуто 3 валідні реакції")
            self.missed_stimuli = {k: v for k, v in self.missed_stimuli.items() if v["valid_count"] < 3 and v["attempts"] < max_attempts}
            self.start_main()

    def start_main(self):
        self.stage = "main"
        self.log("INFO", "--- Основний тест ---")
        block = []
        words = self.stimuli_main * self.config.get("test_repeats", 3)
        random.shuffle(words)
        buf = self.buffer_symbols
        for stim, cat in words:
            block.append((buf, "buffer"))
            block.append((stim, cat))
            block.append((buf, "buffer"))
        self.log("INFO", f"Основний блок: {len(words)} стимулів, {len(block) - len(words)} буферних")
        self._run_stimulus_block(block, next_callback=self.repeat_missed_main)

    def repeat_missed_main(self):
        self.stage = "main_repeat"
        self.log("INFO", "--- Повторення пропущених основних стимулів ---")
        block = []
        max_attempts = self.config.get("max_miss_attempts", 5)
        for (stim, cat), data in self.missed_stimuli.items():
            if cat in ["sensitive", "neutral", "positive", "buffer"] and data["valid_count"] < 3 and data["attempts"] < max_attempts:
                remaining = min(3 - data["valid_count"], max_attempts - data["attempts"])
                block.extend([(stim, cat)] * remaining)
        random.shuffle(block)
        final_block = []
        buf = self.buffer_symbols
        for stim, cat in block:
            final_block.append((buf, "buffer"))
            final_block.append((stim, cat))
            final_block.append((buf, "buffer"))
        if final_block:
            self.log("INFO", f"Повторення основних стимулів: {len(block)}")
            self._run_stimulus_block(final_block, next_callback=self.finish_test)
        else:
            self.log("INFO", "Пропущені основні стимули відсутні або досягнуто 3 валідні реакції")
            self.missed_stimuli = {k: v for k, v in self.missed_stimuli.items() if v["valid_count"] < 3 and v["attempts"] < max_attempts}
            self.finish_test()

# Продовження в частині 3
    # Частина 3: Методи обробки стимулів, аналізу даних і формування звіту
# Для об’єднання: розмістіть цей код після частини 2 у файлі main011-s.py
# Залежності: методи з частин 1 і 2, tkinter, datetime, random, statistics, scipy.stats

    def _run_simple_block(self, block, next_callback):
        self.clear_widgets()
        self.current_block = block
        self.block_results = []
        self.current_idx = 0
        self.block_next_callback = next_callback
        hide_cursor(self.master)
        self._next_simple_stimulus()

    def _next_simple_stimulus(self):
        if self.current_idx >= len(self.current_block):
            self.results[self.stage] += self.block_results
            show_cursor(self.master)
            self.block_next_callback()
            return
        stim = self.current_block[self.current_idx]
        self.current_idx += 1
        self._show_relax_stimulus(stim)

    def _show_relax_stimulus(self, stim):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        canvas.create_text(w//2, h//2, text=stim, fill="white", font=self.font_probe)
        self.log("SHOW", f"{self.stage}|{stim}|relax|start")
        stim_dur = self.config.get("preparation_probe_duration_ms", 60)
        self.master.after(stim_dur, lambda: self._show_relax_mask(stim))

    def _show_relax_mask(self, stim):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        mask_txt = self._generate_mask()
        rect_pad = self.config.get("mask_frame", {}).get("pad", 32)
        rect_color = self.config.get("mask_frame", {}).get("color", "#FFFFFF")
        rect_width = self.config.get("mask_frame", {}).get("width", 8)
        text_id = canvas.create_text(w//2, h//2, text=mask_txt, fill="white", font=self.font_mask)
        bbox = canvas.bbox(text_id)
        if bbox:
            x0, y0, x1, y1 = bbox
            canvas.create_rectangle(x0-rect_pad, y0-rect_pad, x1+rect_pad, y1+rect_pad, outline=rect_color, width=rect_width)
            canvas.lift(text_id)
        mask_ms = self.config.get("mask_duration_ms", 100)
        self.master.after(mask_ms, lambda: self._relax_pause())

    def _relax_pause(self):
        pause_ms = random.randint(*self.config.get("preparation_pause_range_ms", [1000, 2000]))
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        self.master.after(pause_ms, self._next_simple_stimulus)

    def _run_stimulus_block(self, block, next_callback):
        self.clear_widgets()
        self.current_block = block
        self.block_results = []
        self.current_idx = 0
        self.block_next_callback = next_callback
        hide_cursor(self.master)
        self._next_stimulus()

    def _next_stimulus(self):
        current_time = time.perf_counter()
        pause_interval_sec = self.config.get("pause_interval_min", 5) * 60
        if self.test_start_time and (current_time - self.last_pause_time) >= pause_interval_sec:
            self._show_pause_screen()
            return
        if self.current_idx >= len(self.current_block):
            self.results[self.stage] += self.block_results
            show_cursor(self.master)
            self.block_next_callback()
            return
        stim, cat = self.current_block[self.current_idx]
        self.current_idx += 1
        self.sequence_position += 1  # ЗМІНА ВІД 17.07.2025: Оновлення позиції для POS
        self._show_timed_stimulus(stim, cat)

    def _show_timed_stimulus(self, stim, cat):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        self.reaction_captured = False
        self.stimulus_shown_time = time.perf_counter()
        self.stimulus_value = stim
        self.stimulus_cat = cat
        self.stimulus_logged = False
        self.master.bind("<space>", self._on_space)
        self.master.bind("<KeyRelease-space>", self._on_space_release)
        show_ts = datetime.datetime.now().isoformat(timespec='milliseconds')
        fill_color = self.config.get("stroop_colors", {}).get(self.lang, {}).get(stim, "white") if cat == "cognitive" else "white"
        self.log("SHOW", f"{self.stage}|{stim}|{cat}|start|{show_ts}|color={fill_color}")
        canvas.create_text(w//2, h//2, text=stim, fill=fill_color, font=self.font_probe)
        self.stimulus_duration = self._get_probe_duration(cat)
        self.mask_duration = self.config.get("mask_duration_ms", 100)
        self.reaction_window_ms = self.config.get("reaction_window_ms", 2000)
        pause_range = self.config.get("pause_range_ms", {}).get(cat, self.config.get("pause_range_ms", {}).get("default", [500, 1500]))
        pause_ms = random.randint(*pause_range)
        self.pause_ms = pause_ms
        self.stimulus_timer = self.master.after(self.stimulus_duration, lambda: self._show_mask_after_stimulus(stim, cat))
        self.mask_timer = self.master.after(self.stimulus_duration + self.mask_duration, lambda: self._show_pause_after_mask(stim, cat))

    def _show_mask_after_stimulus(self, stim, cat):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        mask_txt = self._generate_mask()
        rect_pad = self.config.get("mask_frame", {}).get("pad", 32)
        rect_color = self.config.get("mask_frame", {}).get("color", "#FFFFFF")
        rect_width = self.config.get("mask_frame", {}).get("width", 8)
        text_id = canvas.create_text(w//2, h//2, text=mask_txt, fill="white", font=self.font_mask)
        bbox = canvas.bbox(text_id)
        if bbox:
            x0, y0, x1, y1 = bbox
            canvas.create_rectangle(x0-rect_pad, y0-rect_pad, x1+rect_pad, y1+rect_pad, outline=rect_color, width=rect_width)
            canvas.lift(text_id)

    def _show_pause_after_mask(self, stim, cat):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        self.pause_timer = self.master.after(self.pause_ms, lambda: self._close_reaction_window(stim, cat))

    def _show_pause_screen(self):
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        self.pause_canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        self.pause_canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        pause_text = "Пауза: {} сек" if self.lang == "ua" else "Перерыв: {} сек"
        self.pause_text_id = self.pause_canvas.create_text(w//2, h//2, text=pause_text.format(10), fill=self.info_color, font=self.font_info)
        self.log("INFO", "Пауза: початок (10 секунд)")
        self.last_pause_time = time.perf_counter()
        self.pause_remaining = 10
        self._update_pause_countdown()

    def _update_pause_countdown(self):
        if self.pause_remaining <= 0:
            self.log("INFO", "Пауза: кінець")
            self.clear_widgets()
            self._next_stimulus()
            return
        self.pause_canvas.itemconfig(self.pause_text_id, text=("Пауза: {} сек" if self.lang == "ua" else "Перерыв: {} сек").format(self.pause_remaining))
        self.pause_remaining -= 1
        self.master.after(1000, self._update_pause_countdown)

    def _close_reaction_window(self, stim, cat):
        self.reaction_captured = True
        self.master.unbind("<space>")
        self.master.unbind("<KeyRelease-space>")
        if hasattr(self, 'stimulus_timer') and self.stimulus_timer is not None:
            self.master.after_cancel(self.stimulus_timer)
            self.stimulus_timer = None
        if hasattr(self, 'mask_timer') and self.mask_timer is not None:
            self.master.after_cancel(self.mask_timer)
            self.mask_timer = None
        if hasattr(self, 'pause_timer') and self.pause_timer is not None:
            self.master.after_cancel(self.pause_timer)
            self.pause_timer = None
        self.clear_widgets()
        w, h = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        canvas = tk.Canvas(self.master, bg=self.bg_color, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        hide_cursor(self.master)
        if not self.stimulus_logged:
            stim_key = (self.stimulus_value, self.stimulus_cat)
            if stim_key not in self.missed_stimuli:
                self.missed_stimuli[stim_key] = {"valid_count": 0, "attempts": 0}
            self.missed_stimuli[stim_key]["attempts"] += 1
            self.log("MISS", f"{self.stage}|{self.stimulus_value}|{self.stimulus_cat}|no_response|Пропуск|{datetime.datetime.now().isoformat(timespec='milliseconds')}")
            res = {"stimulus": self.stimulus_value, "category": self.stimulus_cat, "reaction": None, "t": None, "miss": True, "reason": "no_response", "press_duration": None, "stage": self.stage, "sequence_position": self.sequence_position}  # ЗМІНА ВІД 17.07.2025: Додано sequence_position
            self.block_results.append(res)
        post_reaction_delay = self.config.get("post_reaction_delay_ms", 300)
        self.master.after(post_reaction_delay, self._next_stimulus)

    def _on_space(self, event):
        if self.reaction_captured or self.stimulus_logged:
            return
        self.press_time = time.perf_counter()
        t_react = int((self.press_time - self.stimulus_shown_time) * 1000)
        react_ts = datetime.datetime.now().isoformat(timespec='milliseconds')
        stim_key = (self.stimulus_value, self.stimulus_cat)
        if stim_key not in self.missed_stimuli:
            self.missed_stimuli[stim_key] = {"valid_count": 0, "attempts": 0}
        self.missed_stimuli[stim_key]["attempts"] += 1
        if t_react < 50:
            self.log("MISS", f"{self.stage}|{self.stimulus_value}|{self.stimulus_cat}|{t_react}|Передчасна реакція|{react_ts}")
            res = {"stimulus": self.stimulus_value, "category": self.stimulus_cat, "reaction": None, "t": t_react, "miss": True, "reason": "premature", "press_duration": None, "stage": self.stage, "sequence_position": self.sequence_position}  # ЗМІНА ВІД 17.07.2025: Додано sequence_position
        elif t_react > self.reaction_window_ms:
            self.log("MISS", f"{self.stage}|{self.stimulus_value}|{self.stimulus_cat}|{t_react}|Запізніла реакція|{react_ts}")
            res = {"stimulus": self.stimulus_value, "category": self.stimulus_cat, "reaction": None, "t": t_react, "miss": True, "reason": "late", "press_duration": None, "stage": self.stage, "sequence_position": self.sequence_position}  # ЗМІНА ВІД 17.07.2025: Додано sequence_position
        else:
            self.log("REACTION", f"{self.stage}|{self.stimulus_value}|{self.stimulus_cat}|{t_react}|OK|{react_ts}")
            res = {"stimulus": self.stimulus_value, "category": self.stimulus_cat, "reaction": t_react, "miss": False, "press_duration": None, "stage": self.stage, "sequence_position": self.sequence_position}  # ЗМІНА ВІД 17.07.2025: Додано sequence_position
            self.missed_stimuli[stim_key]["valid_count"] += 1
        self.block_results.append(res)
        self.stimulus_logged = True
        self.reaction_captured = True
        self.master.unbind("<space>")

    def _on_space_release(self, event):
        if not self.stimulus_logged:
            return
        release_time = time.perf_counter()
        if self.press_time:
            press_duration_ms = int((release_time - self.press_time) * 1000)
            for res in self.block_results[-1:]:
                if res["stimulus"] == self.stimulus_value and res["category"] == self.stimulus_cat:
                    res["press_duration"] = press_duration_ms
                    self.log("REACTION", f"{self.stage}|{self.stimulus_value}|{self.stimulus_cat}|press_duration={press_duration_ms}")
        self.press_time = None
        self.master.unbind("<KeyRelease-space>")

    def _get_probe_duration(self, cat):
        return self.config.get("probe_duration_ms", {}).get(cat, self.config.get("probe_duration_ms", {}).get("default", 60))

    def _generate_mask(self):
        return ''.join(random.choices("0123456789", k=32))

    def _on_escape(self):
        show_cursor(self.master)
        self.master.destroy()

    def _start_session(self):
        self.session_id = f"{self.person_info['uuid']}_{self.person_info['start_time'].replace(' ', '_').replace(':', '-')}"
        self.session_folder = os.path.join("results", self.session_id)
        safe_mkdir(self.session_folder)
        self.log_file = os.path.join(self.session_folder, f"log-{self.session_id}.txt")
        self.report_file = os.path.join(self.session_folder, f"report-{self.session_id}.txt")
        self.log("INFO", "Розпочато нову сесію тесту")
        with open(os.path.join(self.session_folder, "person.json"), "w", encoding='utf-8') as f:
            json.dump(self.person_info, f, ensure_ascii=False, indent=2)

    def log(self, type_, msg):
        ts = now()
        rec = f"{ts}|{type_}|{msg}"
        self.log_data.append(rec)
        try:
            with open(self.log_file, "a", encoding='utf-8') as f:
                f.write(rec + "\n")
        except Exception as e:
            self.log_data.append(f"{now()}|ERROR|Log write error: {e}")

    def clear_widgets(self):
        for widget in self.master.winfo_children():
            widget.destroy()

    def show_report_screen(self):
        self.clear_widgets()
        show_cursor(self.master)
        report_txt = self._generate_report()
        frame = tk.Frame(self.master, bg=self.bg_color)
        frame.pack(expand=True, fill="both")
        tk.Label(frame, text="Результати тесту:", font=self.font_info, fg=self.info_color, bg=self.bg_color).pack(pady=20)
        txt_box = tk.Text(frame, font=("Consolas", 14), bg="#111", fg="#fff", wrap="none", width=120, height=30)
        txt_box.pack(expand=True, fill="both", padx=30, pady=10)
        txt_box.insert("1.0", report_txt[:12000] + ("\n...\n[Скорочено]" if len(report_txt) > 12000 else ""))
        txt_box.config(state="disabled")
        tk.Button(frame, text="Завершити", font=self.font_info, command=self.master.quit).pack(pady=20)
        try:
            with open(self.report_file, "w", encoding='utf-8') as f:
                f.write(report_txt)
        except Exception as e:
            self.log("ERROR", f"Report write error: {e}")

    def finish_test(self):
        self.test_end_time = time.perf_counter()
        self.test_end_time_str = now()  # ЗМІНА ВІД 17.07.2025: Зберігаємо час завершення для звіту
        self.show_report_screen()

    def _analyze_respondent_state(self, all_data):
        state_stats = {}
        adaptation_cv = None
        for block in ["adaptation", "main"]:
            block_data = [d for d in all_data if d["stage"] in [block, f"{block}_repeat"]]
            reacts = [d["reaction"] for d in block_data if d["reaction"]]
            miss_count = len([d for d in block_data if d["miss"]])
            n = len(block_data)
            miss_pct = (miss_count / n * 100) if n else 0
            mean = statistics.mean(reacts) if reacts else 0
            sd = statistics.stdev(reacts) if len(reacts) > 1 else 0
            cv = (sd / mean * 100) if mean else 0
            conclusion = "Готовність" if block == "adaptation" and cv < 10 and miss_pct < 5 else "Стабільність" if block == "main" and cv < 15 and miss_pct < 5 else "Нестабільність"
            if block == "adaptation":
                adaptation_cv = cv
            fatigue = ""
            if block == "main" and adaptation_cv is not None and cv > adaptation_cv * 1.25:
                fatigue = "Попередження: можлива втома (CV зросло на >25%)"
            state_stats[block] = {"mean": mean, "cv": cv, "miss_pct": miss_pct, "conclusion": conclusion, "fatigue": fatigue}
        return state_stats

    def _analyze_by_category(self, all_data):
        if not all_data:
            self.log("WARNING", "Немає даних для аналізу за категоріями")
            return {}
        cats = set([d["category"] for d in all_data if d["category"]])
        neutral_reacts = [d["reaction"] for d in all_data if d["category"]=="neutral" and d["reaction"]]
        neutral_mean = statistics.mean(neutral_reacts) if neutral_reacts else 1
        neutral_sd = statistics.stdev(neutral_reacts) if len(neutral_reacts) > 1 else 0
        neutral_press_durations = [d["press_duration"] for d in all_data if d["category"]=="neutral" and d["press_duration"]]
        neutral_press_mean = statistics.mean(neutral_press_durations) if neutral_press_durations else 0
        cat_stats = {}
        for cat in cats:
            reacts = [d["reaction"] for d in all_data if d["category"]==cat and d["reaction"]]
            press_durations = [d["press_duration"] for d in all_data if d["category"]==cat and d["press_duration"]]
            miss_count = len([d for d in all_data if d["category"]==cat and d["miss"]])
            n = len([d for d in all_data if d["category"]==cat])
            if reacts:
                mean = statistics.mean(reacts)
                sd = statistics.stdev(reacts) if len(reacts) > 1 else 0
                reacts = [r for r in reacts if abs(r - mean) <= 3 * sd] if sd > 0 else reacts
            mean = statistics.mean(reacts) if reacts else 0
            sd = statistics.stdev(reacts) if len(reacts) > 1 else 0
            cv = (sd / mean * 100) if mean else 0
            if press_durations:
                press_mean = statistics.mean(press_durations)
                press_sd = statistics.stdev(press_durations) if len(press_durations) > 1 else 0
                press_durations = [p for p in press_durations if abs(p - press_mean) <= 3 * press_sd] if press_sd > 0 else press_durations
            press_mean = statistics.mean(press_durations) if press_durations else 0
            press_sd = statistics.stdev(press_durations) if len(press_durations) > 1 else 0
            press_effect = ((neutral_press_mean - press_mean) / neutral_press_mean * 100) if neutral_press_mean and press_mean else 0
            effect = ((neutral_mean - mean) / neutral_mean * 100) if neutral_mean else 0
            z = ((neutral_mean - mean) / neutral_sd) if neutral_sd and mean else 0
            t_stat, pval = ttest_ind(reacts, neutral_reacts, equal_var=False) if reacts and neutral_reacts else (0, 1)
            press_t_stat, press_pval = ttest_ind(press_durations, neutral_press_durations, equal_var=False) if press_durations and neutral_press_durations else (0, 1)
            after_reacts = []
            for i, d in enumerate(all_data):
                if d["category"] == cat and not d["miss"] and i + 1 < len(all_data):
                    next_d = all_data[i + 1]
                    if next_d["category"] == "buffer" and not next_d["miss"]:
                        after_reacts.append(next_d["reaction"])
            after_mean = statistics.mean(after_reacts) if after_reacts else 0
            after_sd = statistics.stdev(after_reacts) if len(after_reacts) > 1 else 0
            after_effect = ((after_mean - neutral_mean) / neutral_mean * 100) if neutral_mean and after_mean else 0
            z_after = ((after_mean - neutral_mean) / neutral_sd) if neutral_sd and after_mean else 0
            after_t_stat, after_pval = ttest_ind(after_reacts, neutral_reacts, equal_var=False) if after_reacts and neutral_reacts else (0, 1)
            cat_stats[cat] = {
                "mean": mean, "sd": sd, "cv": cv, "n": n, "miss": miss_count,
                "effect": effect, "z": z, "pval": pval,
                "after": {"mean": after_mean, "sd": after_sd, "effect": after_effect, "z": z_after, "pval": after_pval},
                "press_mean": press_mean, "press_sd": press_sd, "press_effect": press_effect, "press_pval": press_pval
            }
        return cat_stats

    def _calculate_recognition_metrics(self, stats, neutral_stats):
        # ЗМІНА ВІД 17.07.2025: Новий метод для розрахунку метрик впізнання (Смирнов, Костандов, Лурія)
        kz = stats["mean"] / neutral_stats.get("mean", 1) if neutral_stats.get("mean", 1) else 1  # Кз (Смирнов)
        kd = neutral_stats.get("mean", 1) / stats["mean"] if stats["mean"] else 1  # Кд (Костандов)
        kaz = stats["press_mean"] / neutral_stats.get("press_mean", 1) if neutral_stats.get("press_mean", 1) else 1  # КАЗ (Лурія)
        char = stats["miss"] / stats["n"] if stats["n"] else 0  # ЧАР (Лурія)
        delta_tmr = stats["after"]["mean"] - neutral_stats.get("mean", 0) if stats["after"]["mean"] else 0  # Післядія
        pos = stats.get("sequence_irregularity", 0)  # POS (аналіз послідовності)
        iv = (kz * 0.4 + (1/kd if kd else 0) * 0.3 + kaz * 0.2 + char * 0.1) * 100  # Композитний індекс (ІВ)
        
        # Відсоток впізнання
        smi_percent = 0
        if kz > 1.5:
            smi_percent = 90
        elif kz > 1.2:
            smi_percent = 80
        elif kz > 1.0:
            smi_percent = 50
        smi_interpret = "Високе впізнання" if smi_percent >= 80 else "Ймовірне впізнання" if smi_percent >= 50 else "Слабке впізнання" if smi_percent >= 20 else "Невпізнаний"
        
        kos_percent = 0
        if kd < 0.6:
            kos_percent = 90
        elif kd < 0.8:
            kos_percent = 80
        elif kd < 1.0:
            kos_percent = 50
        kos_interpret = "Високе впізнання" if kos_percent >= 80 else "Ймовірне впізнання" if kos_percent >= 50 else "Слабке впізнання" if kos_percent >= 20 else "Невпізнаний"
        
        lur_percent = 0
        if kaz > 1.5 or char > 0.2:
            lur_percent = 90
        elif kaz > 1.2 or char > 0.1:
            lur_percent = 80
        elif kaz > 1.0 or char > 0.05:
            lur_percent = 50
        lur_interpret = "Високе впізнання" if lur_percent >= 80 else "Ймовірне впізнання" if lur_percent >= 50 else "Слабке впізнання" if lur_percent >= 20 else "Невпізнаний"
        
        return {
            "kz": kz, "kd": kd, "kaz": kaz, "char": char, "delta_tmr": delta_tmr, "pos": pos, "iv": iv,
            "smi_percent": smi_percent, "smi_interpret": smi_interpret,
            "kos_percent": kos_percent, "kos_interpret": kos_interpret,
            "lur_percent": lur_percent, "lur_interpret": lur_interpret
        }

    def _analyze_by_stimulus(self, all_data, cat, neutral_stats):
        stims = set([d["stimulus"] for d in all_data if d["category"]==cat])
        neutral_reacts = [d["reaction"] for d in all_data if d["category"]=="neutral" and d["reaction"]]
        neutral_mean = neutral_stats.get("mean", 1)
        neutral_sd = neutral_stats.get("sd", 0)
        neutral_press_durations = [d["press_duration"] for d in all_data if d["category"]=="neutral" and d["press_duration"]]
        neutral_press_mean = statistics.mean(neutral_press_durations) if neutral_press_durations else 0
        stats = []
        for stim in stims:
            reacts = [d["reaction"] for d in all_data if d["category"]==cat and d["stimulus"]==stim and d["reaction"]]
            press_durations = [d["press_duration"] for d in all_data if d["category"]==cat and d["stimulus"]==stim and d["press_duration"]]
            miss_count = len([d for d in all_data if d["category"]==cat and d["stimulus"]==stim and d["miss"]])
            n = len([d for d in all_data if d["category"]==cat and d["stimulus"]==stim])
            miss_pct = (miss_count / n * 100) if n else 0
            consecutive_misses = 0
            max_consecutive_misses = 0
            sequence_positions = []
            for i, d in enumerate(all_data):
                if d["category"] == cat and d["stimulus"] == stim:
                    if d["miss"]:
                        consecutive_misses += 1
                        max_consecutive_misses = max(max_consecutive_misses, consecutive_misses)
                    else:
                        consecutive_misses = 0
                    sequence_positions.append(d.get("sequence_position", 0))
            if reacts:
                mean = statistics.mean(reacts)
                sd = statistics.stdev(reacts) if len(reacts) > 1 else 0
                reacts = [r for r in reacts if abs(r - mean) <= 3 * sd] if sd > 0 else reacts
            mean = statistics.mean(reacts) if reacts else 0
            sd = statistics.stdev(reacts) if len(reacts) > 1 else 0
            cv = (sd / mean * 100) if mean else 0
            if press_durations:
                press_mean = statistics.mean(press_durations)
                press_sd = statistics.stdev(press_durations) if len(press_durations) > 1 else 0
                press_durations = [p for p in press_durations if abs(p - press_mean) <= 3 * press_sd] if press_sd > 0 else press_durations
            press_mean = statistics.mean(press_durations) if press_durations else 0
            press_sd = statistics.stdev(press_durations) if len(press_durations) > 1 else 0
            press_effect = ((neutral_press_mean - press_mean) / neutral_press_mean * 100) if neutral_press_mean and press_mean else 0
            effect = ((neutral_mean - mean) / neutral_mean * 100) if neutral_mean else 0
            z = ((neutral_mean - mean) / neutral_sd) if neutral_sd and mean else 0
            t_stat, pval = ttest_ind(reacts, neutral_reacts, equal_var=False) if reacts and neutral_reacts else (0, 1)
            press_t_stat, press_pval = ttest_ind(press_durations, neutral_press_durations, equal_var=False) if press_durations and neutral_press_durations else (0, 1)
            after_reacts = []
            for i, d in enumerate(all_data):
                if d["category"] == cat and d["stimulus"] == stim and not d["miss"] and i + 1 < len(all_data):
                    next_d = all_data[i + 1]
                    if next_d["category"] == "buffer" and not next_d["miss"]:
                        after_reacts.append(next_d["reaction"])
            after_mean = statistics.mean(after_reacts) if after_reacts else 0
            after_sd = statistics.stdev(after_reacts) if len(after_reacts) > 1 else 0
            after_effect = ((after_mean - neutral_mean) / neutral_mean * 100) if neutral_mean and after_mean else 0
            z_after = ((after_mean - neutral_mean) / neutral_sd) if neutral_sd and after_mean else 0
            after_t_stat, after_pval = ttest_ind(after_reacts, neutral_reacts, equal_var=False) if after_reacts and neutral_reacts else (0, 1)
            sequence_irregularity = cv * 0.5 + miss_pct * 0.3 + max_consecutive_misses * 10
            stim_stats = {
                "stimulus": stim, "category": cat, "mean": mean, "sd": sd, "cv": cv, "n": n, "miss": miss_count, "miss_pct": miss_pct,
                "effect": effect, "z": z, "pval": pval,
                "after": {"mean": after_mean, "sd": after_sd, "effect": after_effect, "z": z_after, "pval": after_pval},
                "press_mean": press_mean, "press_sd": press_sd, "press_effect": press_effect, "press_pval": press_pval,
                "consecutive_misses": max_consecutive_misses, "sequence_irregularity": sequence_irregularity
            }
            stim_stats.update(self._calculate_recognition_metrics(stim_stats, neutral_stats))  # ЗМІНА ВІД 17.07.2025: Додано метрики впізнання
            stats.append(stim_stats)
            if miss_pct > 50:
                self.log("WARNING", f"Стимул {stim} ({cat}) має {miss_pct:.1f}% пропусків, позначено як невалідний")
        return stats

    def _format_table(self, headers, table_data, col_widths):
        # ЗМІНА ВІД 17.07.2025: Новий метод для форматування таблиць із динамічною шириною
        header_row = " | ".join(f"{headers[key]:<{col_widths[key]}}" for key in headers)
        rows = [header_row, "-" * len(header_row)]
        for data in table_data:
            row = " | ".join(f"{str(data[key])[:col_widths[key]]:<{col_widths[key]}}" for key in headers)
            rows.append(row)
        return rows

    def _generate_report(self):
        # ЗМІНА ВІД 17.07.2025: Додано таблиці значущості, розділено висновки та примітки
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("                   ЗВІТ ПРО ТЕСТУВАННЯ                    ")
        report_lines.append("=" * 60)
        report_lines.append("")

        # Блок 1: Інформація про тестування
        report_lines.append("1. Інформація про тестування")
        report_lines.append(f"UUID респондента: {self.person_info['uuid']}")
        report_lines.append(f"Дата і час початку тестування: {self.person_info['start_time']}")
        report_lines.append(f"Дата і час завершення тестування: {self.test_end_time_str}")
        report_lines.append("")

        # Блок 2: Результати тестування
        main_data = [d for d in sum([self.results.get(block, []) for block in ["main", "main_repeat"]], [])]
        neutral_stats = self._analyze_by_category(main_data).get("neutral", {})
        stats_by_stim = self._analyze_by_stimulus(main_data, "sensitive", neutral_stats)
        if not stats_by_stim:
            report_lines.append("Немає даних для сенситивних стимулів")
            return "\n".join(report_lines)

        # Основна таблиця (Композитний індекс впізнання)
        table_data_composite = []
        for st in stats_by_stim:
            if st["miss_pct"] > 50:
                continue
            table_data_composite.append({
                "stimulus": st["stimulus"],
                "params": f"Кз={st['kz']:.2f}, Кд={st['kd']:.2f}, КАЗ={st['kaz']:.2f}, ЧАР={st['char']:.2f}, ΔТМР={st['delta_tmr']:.2f}, POS={st['pos']:.1f}",
                "iv": f"{st['iv']:.1f}",
                "interpret": "Високе впізнання" if st["iv"] >= 80 else "Ймовірне впізнання" if st["iv"] >= 50 else "Слабке впізнання" if st["iv"] >= 20 else "Невпізнаний"
            })
        table_data_composite.sort(key=lambda x: float(x["iv"]), reverse=True)
        report_lines.append("2. Результати тестування (Композитний індекс впізнання)")
        report_lines.append("-" * 80)
        headers_composite = {"stimulus": "Сенситивний стимул", "params": "Параметри", "iv": "Відсоток впізнання (%)", "interpret": "Інтерпретація"}
        col_widths_composite = {key: len(str(value)) for key, value in headers_composite.items()}
        for data in table_data_composite:
            col_widths_composite["stimulus"] = max(col_widths_composite["stimulus"], len(str(data["stimulus"][:15])))
            col_widths_composite["params"] = max(col_widths_composite["params"], len(str(data["params"])))
            col_widths_composite["iv"] = max(col_widths_composite["iv"], len(str(data["iv"])))
            col_widths_composite["interpret"] = max(col_widths_composite["interpret"], len(str(data["interpret"])))
        report_lines.extend(self._format_table(headers_composite, table_data_composite, col_widths_composite))
        report_lines.append("-" * 80)
        report_lines.append("")

        # Таблиця Смирнова (впізнання)
        table_data_smirnov = []
        for st in stats_by_stim:
            if st["miss_pct"] > 50:
                continue
            table_data_smirnov.append({
                "stimulus": st["stimulus"],
                "params": f"Кз={st['kz']:.2f}",
                "percent": f"{st['smi_percent']:.1f}",
                "interpret": st["smi_interpret"]
            })
        table_data_smirnov.sort(key=lambda x: float(x["percent"]), reverse=True)
        report_lines.append("Результати тестування (Смирнов, впізнання)")
        report_lines.append("-" * 80)
        headers_smirnov = {"stimulus": "Сенситивний стимул", "params": "Параметри", "percent": "Відсоток впізнання (%)", "interpret": "Інтерпретація"}
        col_widths_smirnov = {key: len(str(value)) for key, value in headers_smirnov.items()}
        for data in table_data_smirnov:
            col_widths_smirnov["stimulus"] = max(col_widths_smirnov["stimulus"], len(str(data["stimulus"][:15])))
            col_widths_smirnov["params"] = max(col_widths_smirnov["params"], len(str(data["params"])))
            col_widths_smirnov["percent"] = max(col_widths_smirnov["percent"], len(str(data["percent"])))
            col_widths_smirnov["interpret"] = max(col_widths_smirnov["interpret"], len(str(data["interpret"])))
        report_lines.extend(self._format_table(headers_smirnov, table_data_smirnov, col_widths_smirnov))
        report_lines.append("-" * 80)
        report_lines.append("")

        # Таблиця Костандова (впізнання)
        table_data_kostandov = []
        for st in stats_by_stim:
            if st["miss_pct"] > 50:
                continue
            table_data_kostandov.append({
                "stimulus": st["stimulus"],
                "params": f"Кд={st['kd']:.2f}",
                "percent": f"{st['kos_percent']:.1f}",
                "interpret": st["kos_interpret"]
            })
        table_data_kostandov.sort(key=lambda x: float(x["percent"]), reverse=True)
        report_lines.append("Результати тестування (Костандов, впізнання)")
        report_lines.append("-" * 80)
        headers_kostandov = {"stimulus": "Сенситивний стимул", "params": "Параметри", "percent": "Відсоток впізнання (%)", "interpret": "Інтерпретація"}
        col_widths_kostandov = {key: len(str(value)) for key, value in headers_kostandov.items()}
        for data in table_data_kostandov:
            col_widths_kostandov["stimulus"] = max(col_widths_kostandov["stimulus"], len(str(data["stimulus"][:15])))
            col_widths_kostandov["params"] = max(col_widths_kostandov["params"], len(str(data["params"])))
            col_widths_kostandov["percent"] = max(col_widths_kostandov["percent"], len(str(data["percent"])))
            col_widths_kostandov["interpret"] = max(col_widths_kostandov["interpret"], len(str(data["interpret"])))
        report_lines.extend(self._format_table(headers_kostandov, table_data_kostandov, col_widths_kostandov))
        report_lines.append("-" * 80)
        report_lines.append("")

        # Таблиця Лурії (впізнання)
        table_data_luria = []
        for st in stats_by_stim:
            if st["miss_pct"] > 50:
                continue
            table_data_luria.append({
                "stimulus": st["stimulus"],
                "params": f"КАЗ={st['kaz']:.2f}, ЧАР={st['char']:.2f}",
                "percent": f"{st['lur_percent']:.1f}",
                "interpret": st["lur_interpret"]
            })
        table_data_luria.sort(key=lambda x: float(x["percent"]), reverse=True)
        report_lines.append("Результати тестування (Лурія, впізнання)")
        report_lines.append("-" * 80)
        headers_luria = {"stimulus": "Сенситивний стимул", "params": "Параметри", "percent": "Відсоток впізнання (%)", "interpret": "Інтерпретація"}
        col_widths_luria = {key: len(str(value)) for key, value in headers_luria.items()}
        for data in table_data_luria:
            col_widths_luria["stimulus"] = max(col_widths_luria["stimulus"], len(str(data["stimulus"][:15])))
            col_widths_luria["params"] = max(col_widths_luria["params"], len(str(data["params"])))
            col_widths_luria["percent"] = max(col_widths_luria["percent"], len(str(data["percent"])))
            col_widths_luria["interpret"] = max(col_widths_luria["interpret"], len(str(data["interpret"])))
        report_lines.extend(self._format_table(headers_luria, table_data_luria, col_widths_luria))
        report_lines.append("-" * 80)
        report_lines.append("")

        # Таблиця Смирнова (значущість) # ЗМІНА ВІД 17.07.2025
        table_data_smirnov_significance = []
        for st in stats_by_stim:
            if st["miss_pct"] > 50:
                continue
            smi_percent = 0
            if st["kz"] > 1.5:
                smi_percent = 90
            elif st["kz"] > 1.2:
                smi_percent = 80
            elif st["kz"] > 1.0:
                smi_percent = 50
            smi_interpret = "Висока значущість" if smi_percent >= 80 else "Ймовірна значущість" if smi_percent >= 50 else "Слабка значущість" if smi_percent >= 20 else "Незначущий"
            table_data_smirnov_significance.append({
                "stimulus": st["stimulus"],
                "params": f"Кз={st['kz']:.2f}",
                "percent": f"{smi_percent:.1f}",
                "interpret": smi_interpret
            })
        table_data_smirnov_significance.sort(key=lambda x: float(x["percent"]), reverse=True)
        report_lines.append("Результати тестування (Смирнов, значущість)")
        report_lines.append("-" * 80)
        headers_smirnov_significance = {"stimulus": "Сенситивний стимул", "params": "Параметри", "percent": "Відсоток значущості (%)", "interpret": "Інтерпретація"}
        col_widths_smirnov_significance = {key: len(str(value)) for key, value in headers_smirnov_significance.items()}
        for data in table_data_smirnov_significance:
            col_widths_smirnov_significance["stimulus"] = max(col_widths_smirnov_significance["stimulus"], len(str(data["stimulus"][:15])))
            col_widths_smirnov_significance["params"] = max(col_widths_smirnov_significance["params"], len(str(data["params"])))
            col_widths_smirnov_significance["percent"] = max(col_widths_smirnov_significance["percent"], len(str(data["percent"])))
            col_widths_smirnov_significance["interpret"] = max(col_widths_smirnov_significance["interpret"], len(str(data["interpret"])))
        report_lines.extend(self._format_table(headers_smirnov_significance, table_data_smirnov_significance, col_widths_smirnov_significance))
        report_lines.append("-" * 80)
        report_lines.append("")

        # Таблиця Костандова (значущість) # ЗМІНА ВІД 17.07.2025
        table_data_kostandov_significance = []
        for st in stats_by_stim:
            if st["miss_pct"] > 50:
                continue
            kos_percent = 0
            if st["kd"] < 0.6:
                kos_percent = 90
            elif st["kd"] < 0.8:
                kos_percent = 80
            elif st["kd"] < 1.0:
                kos_percent = 50
            kos_interpret = "Висока значущість" if kos_percent >= 80 else "Ймовірна значущість" if kos_percent >= 50 else "Слабка значущість" if kos_percent >= 20 else "Незначущий"
            table_data_kostandov_significance.append({
                "stimulus": st["stimulus"],
                "params": f"Кд={st['kd']:.2f}",
                "percent": f"{kos_percent:.1f}",
                "interpret": kos_interpret
            })
        table_data_kostandov_significance.sort(key=lambda x: float(x["percent"]), reverse=True)
        report_lines.append("Результати тестування (Костандов, значущість)")
        report_lines.append("-" * 80)
        headers_kostandov_significance = {"stimulus": "Сенситивний стимул", "params": "Параметри", "percent": "Відсоток значущості (%)", "interpret": "Інтерпретація"}
        col_widths_kostandov_significance = {key: len(str(value)) for key, value in headers_kostandov_significance.items()}
        for data in table_data_kostandov_significance:
            col_widths_kostandov_significance["stimulus"] = max(col_widths_kostandov_significance["stimulus"], len(str(data["stimulus"][:15])))
            col_widths_kostandov_significance["params"] = max(col_widths_kostandov_significance["params"], len(str(data["params"])))
            col_widths_kostandov_significance["percent"] = max(col_widths_kostandov_significance["percent"], len(str(data["percent"])))
            col_widths_kostandov_significance["interpret"] = max(col_widths_kostandov_significance["interpret"], len(str(data["interpret"])))
        report_lines.extend(self._format_table(headers_kostandov_significance, table_data_kostandov_significance, col_widths_kostandov_significance))
        report_lines.append("-" * 80)
        report_lines.append("")

        # Таблиця Лурії (значущість) # ЗМІНА ВІД 17.07.2025
        table_data_luria_significance = []
        for st in stats_by_stim:
            if st["miss_pct"] > 50:
                continue
            lur_percent = 0
            if st["kaz"] > 1.5 or st["char"] > 0.2:
                lur_percent = 90
            elif st["kaz"] > 1.2 or st["char"] > 0.1:
                lur_percent = 80
            elif st["kaz"] > 1.0 or st["char"] > 0.05:
                lur_percent = 50
            lur_interpret = "Висока значущість" if lur_percent >= 80 else "Ймовірна значущість" if lur_percent >= 50 else "Слабка значущість" if lur_percent >= 20 else "Незначущий"
            table_data_luria_significance.append({
                "stimulus": st["stimulus"],
                "params": f"КАЗ={st['kaz']:.2f}, ЧАР={st['char']:.2f}",
                "percent": f"{lur_percent:.1f}",
                "interpret": lur_interpret
            })
        table_data_luria_significance.sort(key=lambda x: float(x["percent"]), reverse=True)
        report_lines.append("Результати тестування (Лурія, значущість)")
        report_lines.append("-" * 80)
        headers_luria_significance = {"stimulus": "Сенситивний стимул", "params": "Параметри", "percent": "Відсоток значущості (%)", "interpret": "Інтерпретація"}
        col_widths_luria_significance = {key: len(str(value)) for key, value in headers_luria_significance.items()}
        for data in table_data_luria_significance:
            col_widths_luria_significance["stimulus"] = max(col_widths_luria_significance["stimulus"], len(str(data["stimulus"][:15])))
            col_widths_luria_significance["params"] = max(col_widths_luria_significance["params"], len(str(data["params"])))
            col_widths_luria_significance["percent"] = max(col_widths_luria_significance["percent"], len(str(data["percent"])))
            col_widths_luria_significance["interpret"] = max(col_widths_luria_significance["interpret"], len(str(data["interpret"])))
        report_lines.extend(self._format_table(headers_luria_significance, table_data_luria_significance, col_widths_luria_significance))
        report_lines.append("-" * 80)
        report_lines.append("")

        # Визначення ширини найдовшої таблиці
        composite_header = " | ".join(f"{headers_composite[key]:<{col_widths_composite[key]}}" for key in headers_composite)
        smirnov_header = " | ".join(f"{headers_smirnov[key]:<{col_widths_smirnov[key]}}" for key in headers_smirnov)
        kostandov_header = " | ".join(f"{headers_kostandov[key]:<{col_widths_kostandov[key]}}" for key in headers_kostandov)
        luria_header = " | ".join(f"{headers_luria[key]:<{col_widths_luria[key]}}" for key in headers_luria)
        smirnov_significance_header = " | ".join(f"{headers_smirnov_significance[key]:<{col_widths_smirnov_significance[key]}}" for key in headers_smirnov_significance)
        kostandov_significance_header = " | ".join(f"{headers_kostandov_significance[key]:<{col_widths_kostandov_significance[key]}}" for key in headers_kostandov_significance)
        luria_significance_header = " | ".join(f"{headers_luria_significance[key]:<{col_widths_luria_significance[key]}}" for key in headers_luria_significance)
        max_table_width = max(len(composite_header), len(smirnov_header), len(kostandov_header), len(luria_header),
                             len(smirnov_significance_header), len(kostandov_significance_header), len(luria_significance_header))  # ЗМІНА ВІД 17.07.2025: Додано ширину нових таблиць

        # Блок 3: Висновки
        report_lines.append("3. Висновки результатів тестування")
        report_lines.append("3.1. Висновок щодо впізнання")  # ЗМІНА ВІД 17.07.2025
        high_recognition = [st["stimulus"] for st in table_data_composite if float(st["iv"]) >= 80]
        probable_recognition = [st["stimulus"] for st in table_data_composite if 50 <= float(st["iv"]) < 80]
        recognition_conclusion = "Респондент демонструє "
        if high_recognition:
            recognition_conclusion += f"високе впізнання для стимулів: {', '.join(high_recognition)}. "
        if probable_recognition:
            recognition_conclusion += f"Ймовірне впізнання для стимулів: {', '.join(probable_recognition)}. "
        recognition_conclusion += "Емоційно значущі стимули мають вищі Кз, КАЗ та нижчі Кд, що свідчить про швидшу обробку (Костандов, 2004). "
        recognition_conclusion += "Високий ЧАР вказує на емоційну значущість (Лурія). "
        recognition_conclusion += "Композитний індекс (ІВ) підтверджує стабільність впізнання (Смирнов, 1995)."
        wrapped_recognition_conclusion = textwrap.wrap(recognition_conclusion, width=max_table_width)
        report_lines.extend(wrapped_recognition_conclusion)
        report_lines.append("")

        report_lines.append("3.2. Висновок щодо значущості")  # ЗМІНА ВІД 17.07.2025
        high_significance = [st["stimulus"] for st in table_data_composite if float(st["iv"]) >= 80]
        probable_significance = [st["stimulus"] for st in table_data_composite if 50 <= float(st["iv"]) < 80]
        significance_conclusion = "Респондент демонструє "
        if high_significance:
            significance_conclusion += f"високу значущість для стимулів: {', '.join(high_significance)}. "
        if probable_significance:
            significance_conclusion += f"Ймовірну значущість для стимулів: {', '.join(probable_significance)}. "
        significance_conclusion += "Високі значення Кз і КАЗ свідчать про емоційну значущість стимулів (Смирнов, 1995; Лурія). "
        significance_conclusion += "Низькі Кд вказують на швидшу обробку значущих стимулів (Костандов, 2004). "
        significance_conclusion += "Композитний індекс (ІВ) підтверджує стабільність оцінки значущості."
        wrapped_significance_conclusion = textwrap.wrap(significance_conclusion, width=max_table_width)
        report_lines.extend(wrapped_significance_conclusion)
        report_lines.append("")

        # Блок 4: Примітки
        report_lines.append("4. Примітки")
        report_lines.append("4.1. Параметри таблиць впізнання")  # ЗМІНА ВІД 17.07.2025
        report_lines.append("- Кз (Смирнов, 1995): Коефіцієнт значущості, відношення середнього часу реакції до нейтрального. Кз > 1.2 вказує на впізнання.")
        report_lines.append("- Кд (Костандов, 2004): Коефіцієнт диференціації, відношення нейтрального часу до реакції. Кд < 0.8 свідчить про швидше впізнання.")
        report_lines.append("- КАЗ (Лурія): Коефіцієнт афективної значущості, відношення тривалості натискання до нейтрального. КАЗ > 1.2 вказує на емоційне впізнання.")
        report_lines.append("- ЧАР (Лурія): Частота атипових реакцій, частка пропусків. ЧАР > 0.2 свідчить про емоційну значущість.")
        report_lines.append("- ΔТМР: Післядія, різниця середнього часу реакції після стимулу та нейтрального.")
        report_lines.append("- POS: Аналіз послідовності, враховує позицію стимулу в тесті.")
        report_lines.append("- ІВ: Композитний індекс впізнання, зважена сума Кз, Кд, КАЗ, ЧАР.")
        report_lines.append("")
        report_lines.append("4.2. Параметри таблиць значущості")  # ЗМІНА ВІД 17.07.2025
        report_lines.append("- Кз (Смирнов, 1995): Коефіцієнт значущості, відношення середнього часу реакції до нейтрального. Кз > 1.2 вказує на значущість.")
        report_lines.append("- Кд (Костандов, 2004): Коефіцієнт диференціації, відношення нейтрального часу до реакції. Кд < 0.8 свідчить про значущість.")
        report_lines.append("- КАЗ (Лурія): Коефіцієнт афективної значущості, відношення тривалості натискання до нейтрального. КАЗ > 1.2 вказує на значущість.")
        report_lines.append("- ЧАР (Лурія): Частота атипових реакцій, частка пропусків. ЧАР > 0.1 свідчить про значущість.")
        report_lines.append("")

        return "\n".join(report_lines)

if __name__ == "__main__":
    root = tk.Tk()
    app = PsychoSemanticTestApp(root)
    root.mainloop()

# Кінець файлу main011-s.py