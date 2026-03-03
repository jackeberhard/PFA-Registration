#!/usr/bin/env python3
"""
PFA Event Registration System v1.0
Created by Jack Eberhard
- Graphical registration form with capacity-aware event/time slot selection
- CSV-based persistence for multi-day use
- Admin panel with login, stats, deletion, search, and summaries
- Per-day configurable time slots, modalities, slot caps, and modality caps
- Duplicate day names supported (e.g., two Mondays on different dates)
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import csv
import os
import json
from datetime import datetime
from collections import defaultdict

# ─── CONFIGURATION ───────────────────────────────────────────────────────────

DATA_FILE = "pfa_registrations.csv"
CONFIG_FILE = "pfa_config.json"
DEFAULT_ADMIN_PASSWORD = "admin2025"

DEFAULT_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DEFAULT_DATES = ["TBD", "TBD", "TBD", "TBD", "TBD"]

DEFAULT_TIME_SLOTS = [
    "0800-0900", "0900-1000", "1000-1100", "1100-1200", "1200-1300",
]

DEFAULT_MODALITY_CAPS = {
    "Run": 20, "Swim": 20, "Bike": 12, "Treadmill": 8, "Row": 6,
}
ALL_EVENT_NAMES = list(DEFAULT_MODALITY_CAPS.keys())
DEFAULT_MAX_PER_SLOT = 20

CSV_HEADERS = [
    "LastName", "FirstName", "MI", "Sex", "Age", "Rank",
    "Event", "Day", "Date", "TimeSlot", "Timestamp"
]

APP_VERSION = "1.0"
APP_AUTHOR = "CWT1 Jack Eberhard"
APP_UPDATED = "1MAR2026"


# ─── DATA LAYER ──────────────────────────────────────────────────────────────

class DataManager:
    """
    Dict keys use "DayName|Date" to allow duplicate day names on different dates.
    """
    def __init__(self):
        self.registrations = []
        self.days = list(DEFAULT_DAYS)
        self.dates = list(DEFAULT_DATES)
        self.admin_password = DEFAULT_ADMIN_PASSWORD
        self.time_slots = {}
        self.slot_caps = {}
        self.modalities = {}
        self.load_config()
        self._migrate_keys()
        self._ensure_defaults()
        self.load_registrations()

    def _dk(self, day_index):
        return f"{self.days[day_index]}|{self.dates[day_index]}"

    def _dkv(self, day_name, date):
        return f"{day_name}|{date}"

    def _ensure_defaults(self):
        for i in range(len(self.days)):
            dk = self._dk(i)
            if dk not in self.time_slots:
                self.time_slots[dk] = list(DEFAULT_TIME_SLOTS)
            if dk not in self.slot_caps:
                self.slot_caps[dk] = {}
            if dk not in self.modalities:
                self.modalities[dk] = {}
            for ts in self.time_slots[dk]:
                if ts not in self.slot_caps[dk]:
                    self.slot_caps[dk][ts] = DEFAULT_MAX_PER_SLOT
                if ts not in self.modalities[dk]:
                    self.modalities[dk][ts] = dict(DEFAULT_MODALITY_CAPS)
                else:
                    v = self.modalities[dk][ts]
                    if isinstance(v, list):
                        self.modalities[dk][ts] = {e: DEFAULT_MODALITY_CAPS.get(e, 20) for e in v}

    def _migrate_keys(self):
        """Migrate old bare-day-name keys to Day|Date keys."""
        for i in range(len(self.days)):
            old = self.days[i]
            new = self._dk(i)
            if old == new:
                continue
            for store in (self.time_slots, self.slot_caps, self.modalities):
                if old in store and new not in store:
                    store[new] = store.pop(old)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
                self.days = cfg.get("days", list(DEFAULT_DAYS))
                self.dates = cfg.get("dates", list(DEFAULT_DATES))
                self.admin_password = cfg.get("admin_password", DEFAULT_ADMIN_PASSWORD)
                self.time_slots = cfg.get("time_slots", {})
                self.slot_caps = cfg.get("slot_caps", {})
                self.modalities = cfg.get("modalities", {})
                while len(self.dates) < len(self.days):
                    self.dates.append("TBD")
                self.dates = self.dates[:len(self.days)]
            except (json.JSONDecodeError, KeyError):
                pass

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "days": self.days, "dates": self.dates,
                "admin_password": self.admin_password,
                "time_slots": self.time_slots, "slot_caps": self.slot_caps,
                "modalities": self.modalities,
            }, f, indent=2)

    def load_registrations(self):
        self.registrations = []
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", newline="") as f:
                for row in csv.DictReader(f):
                    self.registrations.append(row)

    def save_registrations(self):
        with open(DATA_FILE, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            w.writeheader()
            for r in self.registrations:
                w.writerow(r)

    def add_registration(self, data):
        data["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.registrations.append(data)
        self.save_registrations()

    def delete_registration(self, index):
        if 0 <= index < len(self.registrations):
            self.registrations.pop(index)
            self.save_registrations()

    def get_slot_counts(self, day, date, timeslot):
        counts = defaultdict(int)
        total = 0
        for r in self.registrations:
            if r["Day"] == day and r.get("Date", "") == date and r["TimeSlot"] == timeslot:
                counts[r["Event"]] += 1
                total += 1
        return counts, total

    def get_max_per_slot(self, dk, timeslot):
        return self.slot_caps.get(dk, {}).get(timeslot, DEFAULT_MAX_PER_SLOT)

    def get_modality_cap(self, dk, timeslot, event):
        m = self.modalities.get(dk, {}).get(timeslot, {})
        if isinstance(m, dict):
            return m.get(event, DEFAULT_MODALITY_CAPS.get(event, 20))
        return DEFAULT_MODALITY_CAPS.get(event, 20)

    def get_day_label(self, i):
        d, dt = self.days[i], self.dates[i]
        return f"{dt} ({d})" if dt and dt != "TBD" else d

    def get_time_slots_for(self, dk):
        return self.time_slots.get(dk, list(DEFAULT_TIME_SLOTS))

    def get_modalities_for(self, dk, ts):
        m = self.modalities.get(dk, {}).get(ts, dict(DEFAULT_MODALITY_CAPS))
        return m if isinstance(m, dict) else {e: DEFAULT_MODALITY_CAPS.get(e, 20) for e in m}

    def add_day(self, name, date="TBD"):
        self.days.append(name)
        self.dates.append(date)
        dk = self._dkv(name, date)
        self.time_slots[dk] = list(DEFAULT_TIME_SLOTS)
        self.slot_caps[dk] = {ts: DEFAULT_MAX_PER_SLOT for ts in DEFAULT_TIME_SLOTS}
        self.modalities[dk] = {ts: dict(DEFAULT_MODALITY_CAPS) for ts in DEFAULT_TIME_SLOTS}
        self.save_config()

    def remove_day(self, index):
        if 0 <= index < len(self.days):
            dk = self._dk(index)
            self.days.pop(index)
            self.dates.pop(index)
            self.time_slots.pop(dk, None)
            self.slot_caps.pop(dk, None)
            self.modalities.pop(dk, None)
            self.save_config()

    def add_time_slot(self, ts, dk_list, mod_caps, slot_cap):
        for dk in dk_list:
            if dk not in self.time_slots:
                self.time_slots[dk] = []
            if ts not in self.time_slots[dk]:
                self.time_slots[dk].append(ts)
                self.time_slots[dk].sort()
            if dk not in self.slot_caps:
                self.slot_caps[dk] = {}
            self.slot_caps[dk][ts] = slot_cap
            if dk not in self.modalities:
                self.modalities[dk] = {}
            self.modalities[dk][ts] = dict(mod_caps)
        self.save_config()

    def remove_time_slot(self, ts, dk):
        if dk in self.time_slots and ts in self.time_slots[dk]:
            self.time_slots[dk].remove(ts)
        if dk in self.slot_caps and ts in self.slot_caps[dk]:
            del self.slot_caps[dk][ts]
        if dk in self.modalities and ts in self.modalities[dk]:
            del self.modalities[dk][ts]
        self.save_config()

    def set_slot_config(self, dk, ts, slot_cap, mod_caps):
        if dk not in self.slot_caps: self.slot_caps[dk] = {}
        self.slot_caps[dk][ts] = slot_cap
        if dk not in self.modalities: self.modalities[dk] = {}
        self.modalities[dk][ts] = dict(mod_caps)
        self.save_config()


# ─── COLOR THEME ─────────────────────────────────────────────────────────────

COLORS = {
    "bg": "#1a1f2e", "bg_light": "#242b3d", "bg_card": "#2a3249",
    "accent": "#4a9eff", "accent_hover": "#6bb3ff", "accent_dark": "#2d7ad4",
    "success": "#34d399", "warning": "#fbbf24", "danger": "#f87171",
    "text": "#e2e8f0", "text_dim": "#94a3b8", "text_dark": "#475569",
    "white": "#ffffff", "border": "#374151", "input_bg": "#1e2538",
}


# ─── MAIN APPLICATION ────────────────────────────────────────────────────────

class PFAApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PFA Event Registration")
        self.root.configure(bg=COLORS["bg"])
        self.root.resizable(True, True)
        self.root.attributes("-fullscreen", True)
        self.root.protocol("WM_DELETE_WINDOW", self._block_close)
        self.data = DataManager()
        self.reg_first = tk.StringVar()
        self.reg_last = tk.StringVar()
        self.reg_mi = tk.StringVar()
        self.reg_sex = tk.StringVar()
        self.reg_age = tk.StringVar()
        self.reg_rank = tk.StringVar()
        self.selected_event = tk.StringVar()
        self.selected_day_idx = None
        self.selected_time = tk.StringVar()
        self.show_main_menu()

    def clear_window(self):
        for w in self.root.winfo_children(): w.destroy()

    def _block_close(self):
        messagebox.showinfo("Exit Disabled", "Please use the Admin Panel to exit.")

    def make_label(self, parent, text, size=12, bold=False, color=None, anchor="w"):
        return tk.Label(parent, text=text,
                        font=("Segoe UI", size, "bold" if bold else "normal"),
                        fg=color or COLORS["text"], bg=parent["bg"], anchor=anchor)

    def make_entry(self, parent, var, width=None):
        e = tk.Entry(parent, textvariable=var, font=("Segoe UI", 12),
                     bg=COLORS["input_bg"], fg=COLORS["text"], insertbackground=COLORS["text"],
                     relief="flat", bd=0, highlightthickness=2,
                     highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"])
        if width: e.configure(width=width)
        return e

    def make_button(self, parent, text, cmd, color=None, width=20, size=11):
        return tk.Button(parent, text=text, command=cmd,
                         font=("Segoe UI", size, "bold"), bg=color or COLORS["accent"],
                         fg=COLORS["white"], activebackground=COLORS["accent_hover"],
                         activeforeground=COLORS["white"], relief="flat", bd=0,
                         cursor="hand2", width=width, pady=8)

    def _scroll(self, parent):
        c = tk.Canvas(parent, bg=COLORS["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=c.yview)
        sf = tk.Frame(c, bg=COLORS["bg"])
        sf.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
        c.create_window((0, 0), window=sf, anchor="nw")
        c.configure(yscrollcommand=sb.set)
        c.bind_all("<MouseWheel>", lambda e: c.yview_scroll(int(-1*(e.delta/120)), "units"))
        sb.pack(side="right", fill="y"); c.pack(side="left", fill="both", expand=True)
        return c, sf

    def _full_name(self, r):
        mi = r.get("MI", "").strip()
        return f"{r.get('LastName','')}, {r.get('FirstName','')}{' '+mi+'.' if mi else ''}"

    # ── Main Menu ─────────────────────────────────────────────────────────

    def show_main_menu(self):
        self.clear_window()
        f = tk.Frame(self.root, bg=COLORS["bg"]); f.pack(expand=True)
        self.make_label(f, "PFA EVENT REGISTRATION", size=28, bold=True,
                        color=COLORS["accent"], anchor="center").pack(pady=(40, 5))
        self.make_label(f, "Physical Fitness Assessment Sign-Up System",
                        size=13, color=COLORS["text_dim"], anchor="center").pack(pady=(0, 50))
        bf = tk.Frame(f, bg=COLORS["bg"]); bf.pack()
        self.make_button(bf, "\U0001F4DD  New Registration",
                         self.show_registration_form, width=25, size=13).pack(pady=10)
        self.make_button(bf, "\U0001F512  Admin Panel",
                         self.prompt_admin_login, width=25, size=13,
                         color=COLORS["bg_card"]).pack(pady=10)

    # ── Registration Form ─────────────────────────────────────────────────

    def show_registration_form(self):
        self.clear_window()
        for v in [self.reg_first, self.reg_last, self.reg_mi, self.reg_sex,
                  self.reg_age, self.reg_rank]: v.set("")
        _, sf = self._scroll(self.root)
        h = tk.Frame(sf, bg=COLORS["bg"]); h.pack(fill="x", padx=40, pady=(20, 10))
        tk.Button(h, text="\u2190 Back", command=self.show_main_menu, font=("Segoe UI", 10),
                  bg=COLORS["bg"], fg=COLORS["text_dim"], relief="flat", cursor="hand2",
                  activebackground=COLORS["bg"], activeforeground=COLORS["accent"]).pack(anchor="w")
        self.make_label(h, "PARTICIPANT REGISTRATION", size=22, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(10, 5))
        self.make_label(h, "Fill in your details and select your event",
                        size=11, color=COLORS["text_dim"]).pack(anchor="w")
        cd = tk.Frame(sf, bg=COLORS["bg_card"], padx=30, pady=25)
        cd.pack(fill="x", padx=40, pady=15)
        self.make_label(cd, "PERSONAL INFORMATION", size=14, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 15))

        self.make_label(cd, "Last Name *", size=10, color=COLORS["text_dim"]).pack(anchor="w")
        self.make_entry(cd, self.reg_last).pack(fill="x", pady=(2, 12), ipady=6)
        self.make_label(cd, "First Name *", size=10, color=COLORS["text_dim"]).pack(anchor="w")
        self.make_entry(cd, self.reg_first).pack(fill="x", pady=(2, 12), ipady=6)

        row = tk.Frame(cd, bg=COLORS["bg_card"]); row.pack(fill="x", pady=(0, 12))
        mf = tk.Frame(row, bg=COLORS["bg_card"]); mf.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.make_label(mf, "Middle Initial", size=10, color=COLORS["text_dim"]).pack(anchor="w")
        self.make_entry(mf, self.reg_mi, width=5).pack(anchor="w", pady=(2, 0), ipady=6)
        xf = tk.Frame(row, bg=COLORS["bg_card"]); xf.pack(side="left", fill="x", expand=True)
        self.make_label(xf, "Sex *", size=10, color=COLORS["text_dim"]).pack(anchor="w")
        sb = tk.Frame(xf, bg=COLORS["bg_card"]); sb.pack(anchor="w", pady=(2, 0))
        self.sex_buttons = []
        for v in ["M", "F"]:
            b = tk.Button(sb, text=v, font=("Segoe UI", 12, "bold"),
                          bg=COLORS["bg_light"], fg=COLORS["text"],
                          activebackground=COLORS["accent"], activeforeground=COLORS["white"],
                          relief="flat", cursor="hand2", width=4, pady=6,
                          command=lambda x=v: self._sel_sex(x))
            b.pack(side="left", padx=(0, 8)); self.sex_buttons.append((b, v))

        self.make_label(cd, "Age *", size=10, color=COLORS["text_dim"]).pack(anchor="w")
        self.make_entry(cd, self.reg_age).pack(fill="x", pady=(2, 12), ipady=6)
        self.make_label(cd, "Rank *", size=10, color=COLORS["text_dim"]).pack(anchor="w")
        self.make_entry(cd, self.reg_rank).pack(fill="x", pady=(2, 12), ipady=6)
        self.make_button(cd, "Continue to Event Selection \u2192",
                         self.validate_and_continue, width=30).pack(pady=(15, 0))

    def _sel_sex(self, v):
        self.reg_sex.set(v)
        for b, x in self.sex_buttons:
            b.configure(bg=COLORS["accent"] if x == v else COLORS["bg_light"],
                        fg=COLORS["white"] if x == v else COLORS["text"])

    def validate_and_continue(self):
        first, last = self.reg_first.get().strip(), self.reg_last.get().strip()
        sex, age = self.reg_sex.get().strip(), self.reg_age.get().strip()
        rank = self.reg_rank.get().strip(),
        if not all([first, last, sex, age, rank]):
            messagebox.showwarning("Missing Fields", "Please fill in all required fields."); return
        if sex not in ("M", "F"):
            messagebox.showwarning("Select Sex", "Please select M or F."); return
        if not age.isdigit() or not (1 <= int(age) <= 120):
            messagebox.showwarning("Invalid Age", "Please enter a valid age."); return
        mi = self.reg_mi.get().strip()
        if mi and len(mi) > 1:
            messagebox.showwarning("MI", "Enter only a single letter."); return
        self.show_event_selection()

    # ── Event Selection ───────────────────────────────────────────────────

    def show_event_selection(self):
        self.clear_window()
        self.selected_event.set(""); self.selected_day_idx = None; self.selected_time.set("")
        _, sf = self._scroll(self.root)
        self._esf = sf
        h = tk.Frame(sf, bg=COLORS["bg"]); h.pack(fill="x", padx=40, pady=(20, 10))
        tk.Button(h, text="\u2190 Back", command=self.show_registration_form, font=("Segoe UI", 10),
                  bg=COLORS["bg"], fg=COLORS["text_dim"], relief="flat", cursor="hand2",
                  activebackground=COLORS["bg"], activeforeground=COLORS["accent"]).pack(anchor="w")
        self.make_label(h, "SELECT YOUR EVENT", size=22, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(10, 5))
        r, l = self.reg_rank.get().strip(), self.reg_last.get().strip()
        self.make_label(h, f"Registering: {r} {l}, {self.reg_first.get().strip()}",
                        size=11, color=COLORS["text_dim"]).pack(anchor="w")
        ic = tk.Frame(sf, bg=COLORS["bg_light"], padx=20, pady=12)
        ic.pack(fill="x", padx=40, pady=(10, 5))
        self.make_label(ic, "1) Select a day  \u2192  2) Select a time slot  \u2192  3) Select an event",
                        size=10, color=COLORS["text_dim"]).pack(anchor="w")

        dc = tk.Frame(sf, bg=COLORS["bg_card"], padx=25, pady=20)
        dc.pack(fill="x", padx=40, pady=10)
        self.make_label(dc, "STEP 1: CHOOSE A DAY", size=13, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 12))
        dbf = tk.Frame(dc, bg=COLORS["bg_card"]); dbf.pack(fill="x")
        self.day_buttons = []
        for i in range(len(self.data.days)):
            lbl = self.data.get_day_label(i)
            b = tk.Button(dbf, text=lbl, font=("Segoe UI", 11),
                          bg=COLORS["bg_light"], fg=COLORS["text"],
                          activebackground=COLORS["accent"], activeforeground=COLORS["white"],
                          relief="flat", cursor="hand2", pady=8, padx=12,
                          command=lambda idx=i: self.select_day(idx))
            b.pack(side="left", padx=(0, 8), pady=4); self.day_buttons.append(b)

        self.time_card = tk.Frame(sf, bg=COLORS["bg_card"], padx=25, pady=20)
        self.time_card_packed = False
        self.event_card = tk.Frame(sf, bg=COLORS["bg_card"], padx=25, pady=20)
        self.event_card_packed = False
        self.submit_frame = tk.Frame(sf, bg=COLORS["bg"])

    def select_day(self, idx):
        self.selected_day_idx = idx
        self.data.load_registrations()
        self.selected_time.set(""); self.selected_event.set("")
        for i, b in enumerate(self.day_buttons):
            b.configure(bg=COLORS["accent"] if i == idx else COLORS["bg_light"],
                        fg=COLORS["white"] if i == idx else COLORS["text"])
        if self.event_card_packed: self.event_card.pack_forget(); self.event_card_packed = False
        if self.submit_frame.winfo_manager(): self.submit_frame.pack_forget()
        if self.time_card_packed: self.time_card.pack_forget()

        self.time_card = tk.Frame(self._esf, bg=COLORS["bg_card"], padx=25, pady=20)
        self.time_card.pack(fill="x", padx=40, pady=10); self.time_card_packed = True
        self.make_label(self.time_card, "STEP 2: CHOOSE A TIME SLOT", size=13, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 12))
        tf = tk.Frame(self.time_card, bg=COLORS["bg_card"]); tf.pack(fill="x")

        day, date = self.data.days[idx], self.data.dates[idx]
        dk = self.data._dk(idx)
        self.time_buttons = []; any_avail = False
        for ts in self.data.get_time_slots_for(dk):
            counts, total = self.data.get_slot_counts(day, date, ts)
            cap = self.data.get_max_per_slot(dk, ts)
            rem = cap - total
            if rem <= 0:
                tk.Button(tf, text=f"{ts}\nFULL", font=("Segoe UI", 10),
                          bg=COLORS["border"], fg=COLORS["text_dark"],
                          relief="flat", state="disabled", pady=8, padx=8
                          ).pack(side="left", padx=(0, 8), pady=4)
            else:
                any_avail = True
                b = tk.Button(tf, text=f"{ts}\n{rem} spots", font=("Segoe UI", 10),
                              bg=COLORS["bg_light"], fg=COLORS["text"],
                              activebackground=COLORS["accent"], activeforeground=COLORS["white"],
                              relief="flat", cursor="hand2", pady=8, padx=8,
                              command=lambda t=ts: self.select_time(t))
                b.pack(side="left", padx=(0, 8), pady=4); self.time_buttons.append((b, ts))
        if not any_avail:
            self.make_label(self.time_card, "All time slots full.", size=11,
                            color=COLORS["warning"]).pack(anchor="w", pady=(10, 0))

    def select_time(self, ts):
        self.selected_time.set(ts); self.selected_event.set("")
        self.data.load_registrations()
        for b, t in self.time_buttons:
            b.configure(bg=COLORS["accent"] if t == ts else COLORS["bg_light"],
                        fg=COLORS["white"] if t == ts else COLORS["text"])
        idx = self.selected_day_idx
        day, date = self.data.days[idx], self.data.dates[idx]
        dk = self.data._dk(idx)
        counts, total = self.data.get_slot_counts(day, date, ts)
        cap = self.data.get_max_per_slot(dk, ts)

        if self.submit_frame.winfo_manager(): self.submit_frame.pack_forget()
        if self.event_card_packed: self.event_card.pack_forget()
        self.event_card = tk.Frame(self._esf, bg=COLORS["bg_card"], padx=25, pady=20)
        self.event_card.pack(fill="x", padx=40, pady=10); self.event_card_packed = True
        self.make_label(self.event_card, "STEP 3: CHOOSE YOUR EVENT", size=13, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 12))
        ef = tk.Frame(self.event_card, bg=COLORS["bg_card"]); ef.pack(fill="x")

        self.event_buttons = []; any_ev = False
        mc = self.data.get_modalities_for(dk, ts)
        for en, ecap in mc.items():
            ec = counts.get(en, 0); er = ecap - ec; sr = cap - total
            if er <= 0 or sr <= 0: continue
            any_ev = True; spots = min(er, sr)
            b = tk.Button(ef, text=f"{en}\n{spots} spots left", font=("Segoe UI", 11),
                          bg=COLORS["bg_light"], fg=COLORS["text"],
                          activebackground=COLORS["accent"], activeforeground=COLORS["white"],
                          relief="flat", cursor="hand2", pady=12, padx=15, width=12,
                          command=lambda e=en: self.select_event(e))
            b.pack(side="left", padx=(0, 8)); self.event_buttons.append((b, en))

        if not any_ev:
            self.make_label(self.event_card, "No events available.", size=11,
                            color=COLORS["warning"]).pack(anchor="w", pady=(10, 0))
        else:
            self.submit_frame = tk.Frame(self._esf, bg=COLORS["bg"])
            self.submit_frame.pack(fill="x", padx=40, pady=(5, 30))
            self.submit_btn = self.make_button(self.submit_frame, "\u2714  Complete Registration",
                                                self.submit_registration, width=30,
                                                color=COLORS["success"], size=13)
            self.submit_btn.pack(pady=10)
            self.submit_btn.configure(state="disabled", bg=COLORS["border"])

    def select_event(self, en):
        self.selected_event.set(en)
        for b, n in self.event_buttons:
            b.configure(bg=COLORS["accent"] if n == en else COLORS["bg_light"],
                        fg=COLORS["white"] if n == en else COLORS["text"])
        if hasattr(self, 'submit_btn'):
            self.submit_btn.configure(state="normal", bg=COLORS["success"])

    def submit_registration(self):
        ev, ts = self.selected_event.get(), self.selected_time.get()
        idx = self.selected_day_idx
        if not all([ev, ts, idx is not None]):
            messagebox.showwarning("Incomplete", "Select day, time, and event."); return
        self.data.load_registrations()
        day, date = self.data.days[idx], self.data.dates[idx]
        dk = self.data._dk(idx)
        counts, total = self.data.get_slot_counts(day, date, ts)
        if total >= self.data.get_max_per_slot(dk, ts):
            messagebox.showerror("Full", "Slot full."); self.show_event_selection(); return
        if counts.get(ev, 0) >= self.data.get_modality_cap(dk, ts, ev):
            messagebox.showerror("Full", f"{ev} full."); self.show_event_selection(); return

        reg = {"LastName": self.reg_last.get().strip(),
               "FirstName": self.reg_first.get().strip(),
               "MI": self.reg_mi.get().strip().upper(),
               "Sex": self.reg_sex.get().strip(),
               "Age": self.reg_age.get().strip(),
               "Rank": self.reg_rank.get().strip(),
               "Event": ev, "Day": day, "Date": date, "TimeSlot": ts}
        self.data.add_registration(reg)
        self.show_confirmation(reg)

    # ── Confirmation ──────────────────────────────────────────────────────

    def show_confirmation(self, reg):
        self.clear_window()
        f = tk.Frame(self.root, bg=COLORS["bg"]); f.pack(expand=True)
        self.make_label(f, "\u2713", size=60, color=COLORS["success"], anchor="center").pack(pady=(40, 10))
        self.make_label(f, "REGISTRATION COMPLETE", size=24, bold=True,
                        color=COLORS["success"], anchor="center").pack(pady=(0, 20))
        ds = f" ({reg['Date']})" if reg["Date"] and reg["Date"] != "TBD" else ""
        msg = (f"Thank you {reg['Rank']} {self._full_name(reg)} for signing up for the PFA!\n\n"
               f"Event: {reg['Event']}\nTime Slot: {reg['TimeSlot']}\nDay: {reg['Day']}{ds}")
        mc = tk.Frame(f, bg=COLORS["bg_card"], padx=30, pady=25)
        mc.pack(fill="x", padx=80, pady=10)
        tk.Label(mc, text=msg, font=("Segoe UI", 13), fg=COLORS["text"],
                 bg=COLORS["bg_card"], justify="center", wraplength=500).pack()
        bf = tk.Frame(f, bg=COLORS["bg"]); bf.pack(pady=30)
        self.make_button(bf, "\U0001F4DD  Register Another",
                         self.show_registration_form, width=25).pack(pady=8)
        self.make_button(bf, "\U0001F3E0  Main Menu",
                         self.show_main_menu, width=25, color=COLORS["bg_card"]).pack(pady=8)

    # ── Admin Panel ───────────────────────────────────────────────────────

    def prompt_admin_login(self):
        pwd = simpledialog.askstring("Admin Login", "Enter admin password:",
                                     show="*", parent=self.root)
        if pwd == self.data.admin_password: self.show_admin_panel()
        elif pwd is not None: messagebox.showerror("Access Denied", "Incorrect password.")

    def _admin_exit(self):
        if messagebox.askyesno("Exit", "Exit application?\nAll data has been saved."):
            self.root.destroy()

    def show_admin_panel(self):
        self.clear_window()
        hd = tk.Frame(self.root, bg=COLORS["bg"], padx=30, pady=15); hd.pack(fill="x")
        tk.Button(hd, text="\u2190 Main Menu", command=self.show_main_menu, font=("Segoe UI", 10),
                  bg=COLORS["bg"], fg=COLORS["text_dim"], relief="flat", cursor="hand2",
                  activebackground=COLORS["bg"], activeforeground=COLORS["accent"]).pack(anchor="w")
        tr = tk.Frame(hd, bg=COLORS["bg"]); tr.pack(fill="x", pady=(10, 0))
        self.make_label(tr, "ADMIN PANEL", size=22, bold=True, color=COLORS["accent"]).pack(side="left")

        nav = tk.Frame(self.root, bg=COLORS["bg_light"], padx=30, pady=10); nav.pack(fill="x")
        self.admin_content = tk.Frame(self.root, bg=COLORS["bg"])
        self.admin_content.pack(fill="both", expand=True)

        tabs = [("Overview & Stats", self.admin_overview), ("All Registrations", self.admin_regs),
                ("Slot Capacity", self.admin_capacity), ("Manage Days", self.admin_days),
                ("Manage Time Slots", self.admin_timeslots), ("About", self.admin_about)]
        for t, c in tabs:
            tk.Button(nav, text=t, command=c, font=("Segoe UI", 10, "bold"),
                      bg=COLORS["bg_card"], fg=COLORS["text"],
                      activebackground=COLORS["accent"], activeforeground=COLORS["white"],
                      relief="flat", cursor="hand2", padx=15, pady=6).pack(side="left", padx=(0, 8))
        tk.Button(nav, text="\u274C  Exit Application", command=self._admin_exit,
                  font=("Segoe UI", 10, "bold"), bg=COLORS["danger"], fg=COLORS["white"],
                  activebackground="#ef4444", activeforeground=COLORS["white"],
                  relief="flat", cursor="hand2", padx=15, pady=6).pack(side="right")
        self.admin_overview()

    def _aclear(self):
        for w in self.admin_content.winfo_children(): w.destroy()

    # ── Admin: Overview ───────────────────────────────────────────────────

    def admin_overview(self):
        self._aclear()
        f = tk.Frame(self.admin_content, bg=COLORS["bg"], padx=30, pady=20); f.pack(fill="both", expand=True)
        tot = len(self.data.registrations)
        cf = tk.Frame(f, bg=COLORS["bg"]); cf.pack(fill="x", pady=(0, 20))
        self._scard(cf, "Total", str(tot), COLORS["accent"])
        ec = defaultdict(int); dc = defaultdict(int)
        for r in self.data.registrations: ec[r["Event"]] += 1; dc[r["Day"]+"|"+r.get("Date","")] += 1
        for en in ALL_EVENT_NAMES: self._scard(cf, en, str(ec.get(en, 0)), COLORS["text_dim"])
        self.make_label(f, "REGISTRATIONS BY DAY", size=14, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(15, 10))
        for i in range(len(self.data.days)):
            dl = self.data.get_day_label(i)
            dk = self.data._dk(i)
            cnt = dc.get(dk, 0)
            rw = tk.Frame(f, bg=COLORS["bg_card"], padx=15, pady=8); rw.pack(fill="x", pady=2)
            self.make_label(rw, f"{dl}: {cnt} registrations", size=11).pack(anchor="w")

    def _scard(self, p, title, val, color):
        c = tk.Frame(p, bg=COLORS["bg_card"], padx=20, pady=15)
        c.pack(side="left", padx=(0, 10), fill="x", expand=True)
        self.make_label(c, val, size=24, bold=True, color=color, anchor="center").pack()
        self.make_label(c, title, size=9, color=COLORS["text_dim"], anchor="center").pack()

    # ── Admin: All Registrations ──────────────────────────────────────────

    def admin_regs(self):
        self._aclear()
        f = tk.Frame(self.admin_content, bg=COLORS["bg"], padx=30, pady=20); f.pack(fill="both", expand=True)
        hr = tk.Frame(f, bg=COLORS["bg"]); hr.pack(fill="x", pady=(0, 10))
        self.make_label(hr, f"ALL REGISTRATIONS ({len(self.data.registrations)})",
                        size=14, bold=True, color=COLORS["accent"]).pack(side="left")
        sf = tk.Frame(hr, bg=COLORS["bg"]); sf.pack(side="right")
        self.make_label(sf, "\U0001F50D", size=12, color=COLORS["text_dim"]).pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        se = tk.Entry(sf, textvariable=self.search_var, font=("Segoe UI", 11),
                      bg=COLORS["input_bg"], fg=COLORS["text"], insertbackground=COLORS["text"],
                      relief="flat", bd=0, width=25, highlightthickness=2,
                      highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"])
        se.pack(side="left", ipady=4)
        se.bind("<KeyRelease>", lambda e: self._ptree(self.search_var.get().strip()))
        tk.Button(sf, text="Clear", command=lambda: [self.search_var.set(""), self._ptree()],
                  font=("Segoe UI", 9), bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                  relief="flat", cursor="hand2", padx=8).pack(side="left", padx=(5, 0))
        if not self.data.registrations:
            self.make_label(f, "No registrations yet.", size=12, color=COLORS["text_dim"]).pack(pady=20); return

        tf = tk.Frame(f, bg=COLORS["bg"]); tf.pack(fill="both", expand=True)
        cols = ("idx","Last","First","MI","Sex","Rank","Age","Event","Day","Date","TimeSlot")
        self.rtree = ttk.Treeview(tf, columns=cols, show="headings", height=20)
        sty = ttk.Style(); sty.theme_use("default")
        sty.configure("Treeview", background=COLORS["bg_card"], foreground=COLORS["text"],
                       fieldbackground=COLORS["bg_card"], font=("Segoe UI", 10))
        sty.configure("Treeview.Heading", background=COLORS["bg_light"],
                       foreground=COLORS["text"], font=("Segoe UI", 10, "bold"))
        sty.map("Treeview", background=[("selected", COLORS["accent"])])
        ws = {"idx":35,"Last":110,"First":100,"MI":30,"Sex":35,"Rank":70,"Age":35,
              "Event":75,"Day":90,"Date":70,"TimeSlot":80}
        for c in cols:
            self.rtree.heading(c, text="#" if c == "idx" else c)
            self.rtree.column(c, width=ws.get(c, 80), anchor="center" if c in ("idx","Age","MI","Sex") else "w")
        self._ptree()
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.rtree.yview)
        self.rtree.configure(yscrollcommand=sb.set)
        self.rtree.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        bf = tk.Frame(f, bg=COLORS["bg"]); bf.pack(fill="x", pady=(10, 0))
        self.make_button(bf, "\U0001F5D1  Delete Selected", self._del_reg,
                         color=COLORS["danger"], width=20).pack(anchor="w")

    def _ptree(self, ft=""):
        self.rtree.delete(*self.rtree.get_children())
        fl = ft.lower()
        for i, r in enumerate(self.data.registrations):
            if fl:
                s = " ".join(r.get(k, "") for k in CSV_HEADERS).lower()
                if fl not in s: continue
            self.rtree.insert("", "end", iid=str(i),
                              values=(i+1, r.get("LastName",""), r.get("FirstName",""),
                                      r.get("MI",""), r.get("Sex",""), r.get("Rank",""),
                                      r.get("Age",""), r.get("Event",""),
                                      r.get("Day",""), r.get("Date",""), r.get("TimeSlot","")))

    def _del_reg(self):
        sel = self.rtree.selection()
        if not sel: messagebox.showinfo("Select", "Select a registration."); return
        idx = int(sel[0]); r = self.data.registrations[idx]
        if messagebox.askyesno("Delete", f"Delete {r.get('Rank','')} {self._full_name(r)}?"):
            self.data.delete_registration(idx); self.admin_regs()

    # ── Admin: Capacity ───────────────────────────────────────────────────

    def admin_capacity(self):
        self._aclear()
        _, sf = self._scroll(self.admin_content)
        f = tk.Frame(sf, bg=COLORS["bg"], padx=30, pady=20); f.pack(fill="both", expand=True)
        self.make_label(f, "SLOT CAPACITY OVERVIEW", size=14, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 15))
        for i in range(len(self.data.days)):
            dl = self.data.get_day_label(i)
            day, date = self.data.days[i], self.data.dates[i]
            dk = self.data._dk(i)
            df = tk.Frame(f, bg=COLORS["bg_card"], padx=15, pady=12); df.pack(fill="x", pady=(0, 10))
            self.make_label(df, dl, size=12, bold=True, color=COLORS["warning"]).pack(anchor="w", pady=(0, 8))
            for ts in self.data.get_time_slots_for(dk):
                counts, total = self.data.get_slot_counts(day, date, ts)
                cap = self.data.get_max_per_slot(dk, ts)
                rem = cap - total
                if rem <= 0: sc, bg = COLORS["danger"], "#3d1f1f"
                elif total >= int(cap * 0.75): sc, bg = COLORS["warning"], "#3d3520"
                else: sc, bg = COLORS["success"], COLORS["bg_light"]
                tf = tk.Frame(df, bg=bg, padx=12, pady=6); tf.pack(fill="x", pady=2)
                self.make_label(tf, f"{ts}  |  {total}/{cap} total", size=10, bold=True, color=sc).pack(anchor="w")
                mc = self.data.get_modalities_for(dk, ts)
                dt = "  |  ".join(f"{e}: {counts.get(e,0)}/{c}" for e, c in mc.items())
                self.make_label(tf, dt or "No modalities", size=9, color=COLORS["text_dim"]).pack(anchor="w")

    # ── Admin: Manage Days ────────────────────────────────────────────────

    def admin_days(self):
        self._aclear()
        _, sf = self._scroll(self.admin_content)
        f = tk.Frame(sf, bg=COLORS["bg"], padx=30, pady=20); f.pack(fill="both", expand=True)
        self.make_label(f, "MANAGE EVENT DAYS", size=14, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 5))
        self.make_label(f, f"Currently {len(self.data.days)} day(s).", size=10,
                        color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 20))

        self.dnv = []; self.ddv = []
        th = tk.Frame(f, bg=COLORS["bg_light"], padx=10, pady=6); th.pack(fill="x")
        self.make_label(th, "#", size=10, bold=True).pack(side="left", padx=(0, 10))
        self.make_label(th, "Day Name", size=10, bold=True).pack(side="left", padx=(0, 80))
        self.make_label(th, "Date", size=10, bold=True).pack(side="left", padx=(70, 0))
        self.dlf = tk.Frame(f, bg=COLORS["bg"]); self.dlf.pack(fill="x", pady=(0, 10))
        for i in range(len(self.data.days)): self._day_row(i)

        ac = tk.Frame(f, bg=COLORS["bg_card"], padx=20, pady=15); ac.pack(fill="x", pady=(10, 5))
        self.make_label(ac, "ADD A NEW DAY", size=12, bold=True, color=COLORS["accent"]).pack(anchor="w", pady=(0, 10))
        ar = tk.Frame(ac, bg=COLORS["bg_card"]); ar.pack(fill="x")
        self.make_label(ar, "Name:", size=10, color=COLORS["text_dim"]).pack(side="left")
        self.ndn = tk.StringVar()
        tk.Entry(ar, textvariable=self.ndn, font=("Segoe UI", 11), bg=COLORS["input_bg"],
                 fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=15,
                 highlightthickness=2, highlightbackground=COLORS["border"],
                 highlightcolor=COLORS["accent"]).pack(side="left", padx=(5, 20), ipady=4)
        self.make_label(ar, "Date:", size=10, color=COLORS["text_dim"]).pack(side="left")
        self.ndd = tk.StringVar(value="TBD")
        tk.Entry(ar, textvariable=self.ndd, font=("Segoe UI", 11), bg=COLORS["input_bg"],
                 fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=15,
                 highlightthickness=2, highlightbackground=COLORS["border"],
                 highlightcolor=COLORS["accent"]).pack(side="left", padx=(5, 20), ipady=4)
        tk.Button(ar, text="+ Add Day", command=self._add_day, font=("Segoe UI", 10, "bold"),
                  bg=COLORS["success"], fg=COLORS["white"], relief="flat", cursor="hand2",
                  padx=15, pady=4).pack(side="left")
        sv = tk.Frame(f, bg=COLORS["bg"]); sv.pack(fill="x", pady=(20, 10))
        self.make_button(sv, "\U0001F4BE  Save All Changes", self._save_days,
                         color=COLORS["success"], width=22).pack(anchor="w")
        self.make_label(f, "Note: Removing a day will NOT delete existing registrations.",
                        size=9, color=COLORS["text_dim"]).pack(anchor="w", pady=(10, 0))

    def _day_row(self, i):
        rw = tk.Frame(self.dlf, bg=COLORS["bg_card"], padx=10, pady=8); rw.pack(fill="x", pady=2)
        self.make_label(rw, f"{i+1}.", size=11, bold=True).pack(side="left", padx=(0, 10))
        nv = tk.StringVar(value=self.data.days[i])
        tk.Entry(rw, textvariable=nv, font=("Segoe UI", 11), bg=COLORS["input_bg"],
                 fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=15,
                 highlightthickness=2, highlightbackground=COLORS["border"],
                 highlightcolor=COLORS["accent"]).pack(side="left", padx=(0, 15), ipady=4)
        self.dnv.append(nv)
        dv = tk.StringVar(value=self.data.dates[i])
        tk.Entry(rw, textvariable=dv, font=("Segoe UI", 11), bg=COLORS["input_bg"],
                 fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=15,
                 highlightthickness=2, highlightbackground=COLORS["border"],
                 highlightcolor=COLORS["accent"]).pack(side="left", padx=(0, 15), ipady=4)
        self.ddv.append(dv)
        dn = self.data.days[i]
        dt = self.data.dates[i]
        rc = sum(1 for r in self.data.registrations if r["Day"] == dn and r.get("Date", "") == dt)
        self.make_label(rw, f"({rc} reg{'s' if rc != 1 else ''})", size=9,
                        color=COLORS["text_dim"]).pack(side="left", padx=(0, 15))
        tk.Button(rw, text="\u2716 Remove", font=("Segoe UI", 9), bg=COLORS["danger"],
                  fg=COLORS["white"], relief="flat", cursor="hand2", padx=8, pady=2,
                  command=lambda idx=i: self._rem_day(idx)).pack(side="right")

    def _add_day(self):
        n, d = self.ndn.get().strip(), self.ndd.get().strip() or "TBD"
        if not n: messagebox.showwarning("Missing", "Enter a day name."); return
        self.data.add_day(n, d)
        self.admin_days()

    def _rem_day(self, i):
        dn, dt = self.data.days[i], self.data.dates[i]
        rc = sum(1 for r in self.data.registrations if r["Day"] == dn and r.get("Date", "") == dt)
        w = f"Remove '{dn}' ({dt})?"
        if rc: w += f"\n\n\u26A0 {rc} registration(s) will NOT be deleted."
        if messagebox.askyesno("Confirm", w):
            self.data.remove_day(i); self.admin_days()

    def _save_days(self):
        nn = [v.get().strip() for v in self.dnv]
        nd = [v.get().strip() or "TBD" for v in self.ddv]
        for i, n in enumerate(nn):
            if not n: messagebox.showwarning("Empty", f"Day {i+1} has no name."); return
        # Check for duplicate name+date combos (same day AND same date)
        combos = [(nn[i], nd[i]) for i in range(len(nn))]
        if len(set(combos)) != len(combos):
            messagebox.showwarning("Duplicate", "Two days can share a name but must have different dates."); return
        for i in range(len(self.data.days)):
            old_dk = self.data._dk(i)
            new_dk = f"{nn[i]}|{nd[i]}"
            if old_dk != new_dk:
                old_day, old_date = self.data.days[i], self.data.dates[i]
                for r in self.data.registrations:
                    if r["Day"] == old_day and r.get("Date", "") == old_date:
                        r["Day"] = nn[i]; r["Date"] = nd[i]
                for store in (self.data.time_slots, self.data.slot_caps, self.data.modalities):
                    if old_dk in store: store[new_dk] = store.pop(old_dk)
        self.data.days = nn; self.data.dates = nd
        self.data.save_config(); self.data.save_registrations()
        messagebox.showinfo("Saved", "Day configurations saved!")
        self.admin_days()

    # ── Admin: Manage Time Slots ──────────────────────────────────────────

    def admin_timeslots(self):
        self._aclear()
        _, sf = self._scroll(self.admin_content)
        f = tk.Frame(sf, bg=COLORS["bg"], padx=30, pady=20); f.pack(fill="both", expand=True)
        self.make_label(f, "MANAGE TIME SLOTS & MODALITIES", size=14, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 5))
        self.make_label(f, "Add/remove time slots, set max participants, configure modality caps.",
                        size=10, color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 20))

        ac = tk.Frame(f, bg=COLORS["bg_card"], padx=20, pady=15); ac.pack(fill="x", pady=(0, 20))
        self.make_label(ac, "ADD A NEW TIME SLOT", size=12, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 12))
        tr = tk.Frame(ac, bg=COLORS["bg_card"]); tr.pack(fill="x", pady=(0, 10))
        self.make_label(tr, "Time Slot:", size=10, color=COLORS["text_dim"]).pack(side="left")
        self.nts = tk.StringVar()
        tk.Entry(tr, textvariable=self.nts, font=("Segoe UI", 11), bg=COLORS["input_bg"],
                 fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=12,
                 highlightthickness=2, highlightbackground=COLORS["border"],
                 highlightcolor=COLORS["accent"]).pack(side="left", padx=(5, 20), ipady=4)
        self.make_label(tr, "Max Participants:", size=10, color=COLORS["text_dim"]).pack(side="left")
        self.ntsc = tk.StringVar(value=str(DEFAULT_MAX_PER_SLOT))
        tk.Entry(tr, textvariable=self.ntsc, font=("Segoe UI", 11), bg=COLORS["input_bg"],
                 fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=5,
                 highlightthickness=2, highlightbackground=COLORS["border"],
                 highlightcolor=COLORS["accent"]).pack(side="left", padx=(5, 0), ipady=4)

        dcf = tk.Frame(ac, bg=COLORS["bg_card"]); dcf.pack(fill="x", pady=(5, 5))
        self.make_label(dcf, "Apply to days:", size=10, color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.ntsdv = {}
        dcr = tk.Frame(dcf, bg=COLORS["bg_card"]); dcr.pack(fill="x")
        for i in range(len(self.data.days)):
            dl = self.data.get_day_label(i); dk = self.data._dk(i)
            v = tk.BooleanVar(value=True)
            tk.Checkbutton(dcr, text=dl, variable=v, font=("Segoe UI", 10),
                           bg=COLORS["bg_card"], fg=COLORS["text"], selectcolor=COLORS["input_bg"],
                           activebackground=COLORS["bg_card"], activeforeground=COLORS["text"]
                           ).pack(side="left", padx=(0, 15))
            self.ntsdv[dk] = v

        mcf = tk.Frame(ac, bg=COLORS["bg_card"]); mcf.pack(fill="x", pady=(10, 5))
        self.make_label(mcf, "Available modalities & caps:", size=10, color=COLORS["text_dim"]).pack(anchor="w", pady=(0, 5))
        self.ntsmv = {}; self.ntsmcv = {}
        for en in ALL_EVENT_NAMES:
            mr = tk.Frame(mcf, bg=COLORS["bg_card"]); mr.pack(fill="x", pady=2)
            v = tk.BooleanVar(value=True)
            tk.Checkbutton(mr, text=en, variable=v, font=("Segoe UI", 10), bg=COLORS["bg_card"],
                           fg=COLORS["text"], selectcolor=COLORS["input_bg"],
                           activebackground=COLORS["bg_card"], activeforeground=COLORS["text"],
                           width=12, anchor="w").pack(side="left")
            self.ntsmv[en] = v
            self.make_label(mr, "Max:", size=9, color=COLORS["text_dim"]).pack(side="left", padx=(10, 3))
            cv = tk.StringVar(value=str(DEFAULT_MODALITY_CAPS[en]))
            tk.Entry(mr, textvariable=cv, font=("Segoe UI", 10), bg=COLORS["input_bg"],
                     fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=5,
                     highlightthickness=2, highlightbackground=COLORS["border"],
                     highlightcolor=COLORS["accent"]).pack(side="left", ipady=2)
            self.ntsmcv[en] = cv
        tk.Button(ac, text="+ Add Time Slot", command=self._add_ts, font=("Segoe UI", 10, "bold"),
                  bg=COLORS["success"], fg=COLORS["white"], relief="flat", cursor="hand2",
                  padx=15, pady=6).pack(anchor="w", pady=(10, 0))

        self.make_label(f, "CURRENT TIME SLOTS BY DAY", size=13, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(10, 10))
        for i in range(len(self.data.days)):
            dl = self.data.get_day_label(i); dk = self.data._dk(i)
            day, date = self.data.days[i], self.data.dates[i]
            dcd = tk.Frame(f, bg=COLORS["bg_card"], padx=15, pady=12); dcd.pack(fill="x", pady=(0, 8))
            self.make_label(dcd, dl, size=12, bold=True, color=COLORS["warning"]).pack(anchor="w", pady=(0, 8))
            for ts in self.data.get_time_slots_for(dk):
                tsr = tk.Frame(dcd, bg=COLORS["bg_light"], padx=12, pady=8); tsr.pack(fill="x", pady=2)
                cap = self.data.get_max_per_slot(dk, ts)
                self.make_label(tsr, f"{ts} (max {cap})", size=11, bold=True).pack(side="left", padx=(0, 15))
                mc = self.data.get_modalities_for(dk, ts)
                self.make_label(tsr, ", ".join(f"{e}:{c}" for e, c in mc.items()) or "None",
                                size=9, color=COLORS["text_dim"]).pack(side="left", padx=(0, 15))
                tk.Button(tsr, text="\u270E Edit", font=("Segoe UI", 9), bg=COLORS["accent"],
                          fg=COLORS["white"], relief="flat", cursor="hand2", padx=8, pady=2,
                          command=lambda d=dk, t=ts: self._edit_slot(d, t)).pack(side="right", padx=(5, 0))
                rc = sum(1 for r in self.data.registrations
                         if r["Day"] == day and r.get("Date", "") == date and r["TimeSlot"] == ts)
                tk.Button(tsr, text=f"\u2716 Remove ({rc})", font=("Segoe UI", 9), bg=COLORS["danger"],
                          fg=COLORS["white"], relief="flat", cursor="hand2", padx=8, pady=2,
                          command=lambda d=dk, t=ts, c=rc: self._rem_ts(d, t, c)).pack(side="right")

    def _add_ts(self):
        ts = self.nts.get().strip()
        if not ts or "-" not in ts:
            messagebox.showwarning("Invalid", "Enter format like 0800-0900."); return
        cs = self.ntsc.get().strip()
        if not cs.isdigit() or int(cs) < 1:
            messagebox.showwarning("Invalid", "Max must be positive."); return
        dks = [dk for dk, v in self.ntsdv.items() if v.get()]
        if not dks: messagebox.showwarning("No Days", "Select at least one day."); return
        mc = {}
        for en in ALL_EVENT_NAMES:
            if self.ntsmv[en].get():
                cv = self.ntsmcv[en].get().strip()
                if not cv.isdigit() or int(cv) < 1:
                    messagebox.showwarning("Invalid", f"Cap for {en} must be positive."); return
                mc[en] = int(cv)
        if not mc: messagebox.showwarning("No Modalities", "Select at least one."); return
        confl = [dk for dk in dks if ts in self.data.get_time_slots_for(dk)]
        if confl: messagebox.showwarning("Duplicate", f"'{ts}' already exists for some selected days."); return
        self.data.add_time_slot(ts, dks, mc, int(cs))
        self.admin_timeslots()

    def _rem_ts(self, dk, ts, rc):
        w = f"Remove '{ts}'?"
        if rc: w += f"\n\n\u26A0 {rc} registration(s) will NOT be deleted."
        if messagebox.askyesno("Confirm", w): self.data.remove_time_slot(ts, dk); self.admin_timeslots()

    def _edit_slot(self, dk, ts):
        d = tk.Toplevel(self.root); d.title(f"Edit {ts}"); d.configure(bg=COLORS["bg_card"])
        d.geometry("460x480"); d.transient(self.root); d.grab_set()
        d.update_idletasks()
        d.geometry(f"460x480+{d.winfo_screenwidth()//2-230}+{d.winfo_screenheight()//2-240}")

        self.make_label(d, f"Edit {dk.replace('|',' — ')} — {ts}", size=13, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", padx=20, pady=(15, 10))
        cr = tk.Frame(d, bg=COLORS["bg_card"]); cr.pack(fill="x", padx=20, pady=(0, 10))
        self.make_label(cr, "Max Participants:", size=10, color=COLORS["text_dim"]).pack(side="left")
        cv = tk.StringVar(value=str(self.data.get_max_per_slot(dk, ts)))
        tk.Entry(cr, textvariable=cv, font=("Segoe UI", 11), bg=COLORS["input_bg"],
                 fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=5,
                 highlightthickness=2, highlightbackground=COLORS["border"],
                 highlightcolor=COLORS["accent"]).pack(side="left", padx=(10, 0), ipady=4)

        self.make_label(d, "Modalities & Caps:", size=10, color=COLORS["text_dim"]).pack(anchor="w", padx=20, pady=(5, 5))
        cm = self.data.get_modalities_for(dk, ts)
        mvs = {}; mcvs = {}
        for en in ALL_EVENT_NAMES:
            mr = tk.Frame(d, bg=COLORS["bg_card"]); mr.pack(fill="x", padx=30, pady=3)
            v = tk.BooleanVar(value=en in cm)
            tk.Checkbutton(mr, text=en, variable=v, font=("Segoe UI", 11), bg=COLORS["bg_card"],
                           fg=COLORS["text"], selectcolor=COLORS["input_bg"],
                           activebackground=COLORS["bg_card"], activeforeground=COLORS["text"],
                           width=12, anchor="w").pack(side="left")
            mvs[en] = v
            self.make_label(mr, "Max:", size=9, color=COLORS["text_dim"]).pack(side="left", padx=(10, 3))
            ecv = tk.StringVar(value=str(cm.get(en, DEFAULT_MODALITY_CAPS.get(en, 20))))
            tk.Entry(mr, textvariable=ecv, font=("Segoe UI", 10), bg=COLORS["input_bg"],
                     fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", bd=0, width=5,
                     highlightthickness=2, highlightbackground=COLORS["border"],
                     highlightcolor=COLORS["accent"]).pack(side="left", ipady=2)
            mcvs[en] = ecv

        def save():
            cs = cv.get().strip()
            if not cs.isdigit() or int(cs) < 1:
                messagebox.showwarning("Invalid", "Max must be positive.", parent=d); return
            nm = {}
            for en in ALL_EVENT_NAMES:
                if mvs[en].get():
                    mc = mcvs[en].get().strip()
                    if not mc.isdigit() or int(mc) < 1:
                        messagebox.showwarning("Invalid", f"{en} cap must be positive.", parent=d); return
                    nm[en] = int(mc)
            if not nm: messagebox.showwarning("None", "Select at least one modality.", parent=d); return
            self.data.set_slot_config(dk, ts, int(cs), nm); d.destroy(); self.admin_timeslots()

        bf = tk.Frame(d, bg=COLORS["bg_card"]); bf.pack(fill="x", padx=20, pady=(15, 15))
        tk.Button(bf, text="\U0001F4BE Save", command=save, font=("Segoe UI", 10, "bold"),
                  bg=COLORS["success"], fg=COLORS["white"], relief="flat", cursor="hand2",
                  padx=15, pady=6).pack(side="left")
        tk.Button(bf, text="Cancel", command=d.destroy, font=("Segoe UI", 10),
                  bg=COLORS["bg_light"], fg=COLORS["text"], relief="flat", cursor="hand2",
                  padx=15, pady=6).pack(side="left", padx=(10, 0))

    # ── Admin: About ──────────────────────────────────────────────────────

    def admin_about(self):
        self._aclear()
        f = tk.Frame(self.admin_content, bg=COLORS["bg"], padx=30, pady=40)
        f.pack(fill="both", expand=True)

        self.make_label(f, "PFA EVENT REGISTRATION", size=22, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 20))

        info = tk.Frame(f, bg=COLORS["bg_card"], padx=25, pady=20)
        info.pack(fill="x", pady=(0, 30))

        self.make_label(info, f"Version {APP_VERSION}", size=14, bold=True).pack(anchor="w", pady=(0, 8))
        self.make_label(info, f"Created by {APP_AUTHOR}", size=12).pack(anchor="w", pady=(0, 4))
        self.make_label(info, f"Last updated {APP_UPDATED}", size=11,
                        color=COLORS["text_dim"]).pack(anchor="w")

        # Password section
        pw_card = tk.Frame(f, bg=COLORS["bg_card"], padx=25, pady=20)
        pw_card.pack(fill="x", pady=(0, 20))

        self.make_label(pw_card, "CHANGE ADMIN PASSWORD", size=13, bold=True,
                        color=COLORS["accent"]).pack(anchor="w", pady=(0, 15))

        r1 = tk.Frame(pw_card, bg=COLORS["bg_card"]); r1.pack(fill="x", pady=(0, 8))
        self.make_label(r1, "Current Password:", size=10, color=COLORS["text_dim"]).pack(side="left")
        self.pw_current = tk.StringVar()
        tk.Entry(r1, textvariable=self.pw_current, show="*", font=("Segoe UI", 11),
                 bg=COLORS["input_bg"], fg=COLORS["text"], insertbackground=COLORS["text"],
                 relief="flat", bd=0, width=20, highlightthickness=2,
                 highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"]
                 ).pack(side="left", padx=(10, 0), ipady=4)

        r2 = tk.Frame(pw_card, bg=COLORS["bg_card"]); r2.pack(fill="x", pady=(0, 8))
        self.make_label(r2, "New Password:", size=10, color=COLORS["text_dim"]).pack(side="left")
        self.pw_new = tk.StringVar()
        tk.Entry(r2, textvariable=self.pw_new, show="*", font=("Segoe UI", 11),
                 bg=COLORS["input_bg"], fg=COLORS["text"], insertbackground=COLORS["text"],
                 relief="flat", bd=0, width=20, highlightthickness=2,
                 highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"]
                 ).pack(side="left", padx=(10, 0), ipady=4)

        r3 = tk.Frame(pw_card, bg=COLORS["bg_card"]); r3.pack(fill="x", pady=(0, 12))
        self.make_label(r3, "Confirm New Password:", size=10, color=COLORS["text_dim"]).pack(side="left")
        self.pw_confirm = tk.StringVar()
        tk.Entry(r3, textvariable=self.pw_confirm, show="*", font=("Segoe UI", 11),
                 bg=COLORS["input_bg"], fg=COLORS["text"], insertbackground=COLORS["text"],
                 relief="flat", bd=0, width=20, highlightthickness=2,
                 highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"]
                 ).pack(side="left", padx=(10, 0), ipady=4)

        tk.Button(pw_card, text="\U0001F512  Update Password", command=self._change_password,
                  font=("Segoe UI", 10, "bold"), bg=COLORS["accent"], fg=COLORS["white"],
                  relief="flat", cursor="hand2", padx=15, pady=6).pack(anchor="w")

    def _change_password(self):
        cur = self.pw_current.get()
        new = self.pw_new.get()
        conf = self.pw_confirm.get()

        if cur != self.data.admin_password:
            messagebox.showerror("Error", "Current password is incorrect.")
            return
        if not new or len(new) < 4:
            messagebox.showwarning("Weak Password", "New password must be at least 4 characters.")
            return
        if new != conf:
            messagebox.showerror("Mismatch", "New password and confirmation do not match.")
            return
        if new == cur:
            messagebox.showwarning("Same Password", "New password must be different from current.")
            return

        self.data.admin_password = new
        self.data.save_config()
        messagebox.showinfo("Success", "Admin password has been updated!")
        self.pw_current.set(""); self.pw_new.set(""); self.pw_confirm.set("")


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = PFAApp(root)
    root.mainloop()
