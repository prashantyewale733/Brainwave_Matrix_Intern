

import json
import os
import time
from datetime import datetime
from hashlib import sha256
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

APP_TITLE = "Python ATM"
DATA_FILE = "bank_data.json"
SESSION_TIMEOUT_SECONDS = 120  # auto logout after inactivity
WITHDRAW_MIN = 100
WITHDRAW_STEP = 100
DEPOSIT_MIN = 50
DEPOSIT_STEP = 50
TRANSFER_MIN = 1

def hash_pin(pin: str) -> str:
    return sha256(("atm_salt::" + pin).encode()).hexdigest()

def load_data():
    if not os.path.exists(DATA_FILE):
        seed_data = {
            "users": {
                "1111222233334444": {
                    "name": "Alice Demo",
                    "account_number": "AC-10001",
                    "pin_hash": hash_pin("1234"),
                    "balance": 35000.0,
                    "transactions": []
                },
                "5555666677778888": {
                    "name": "Bob Demo",
                    "account_number": "AC-10002",
                    "pin_hash": hash_pin("4321"),
                    "balance": 12500.0,
                    "transactions": []
                }
            },
            "atm": {
                "cash_stock": 10_00_00  # simulated cash stock (not enforced strictly, just for realism)
            }
        }
        save_data(seed_data)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def format_currency(x):
    # Simple formatting with commas
    return f"₹{x:,.2f}"

class ATMApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x600")
        self.resizable(False, False)

        self.data = load_data()
        self.current_card = None
        self.last_activity = time.time()

        # Style
        style = ttk.Style(self)
        try:
            self.call("source", "azure.tcl")
            style.theme_use("azure")
        except Exception:
            style.theme_use("clam")

        style.configure("TFrame", background="#0f172a")
        style.configure("TLabel", background="#0f172a", foreground="#e2e8f0", font=("Inter", 12))
        style.configure("Header.TLabel", font=("Inter", 18, "bold"))
        style.configure("Big.TLabel", font=("Inter", 22, "bold"))
        style.configure("TButton", font=("Inter", 12))
        style.configure("Menu.TButton", padding=10)

        # Container for screens
        self.container = ttk.Frame(self, padding=20)
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (WelcomeScreen, PinScreen, MenuScreen, AmountScreen, DepositScreen,
                  TransferScreen, StatementScreen, ChangePinScreen, BalanceScreen):
            frame = F(parent=self.container, app=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show("WelcomeScreen")
        self.bind_all("<Any-KeyPress>", self._activity)
        self.bind_all("<Button>", self._activity)
        self.after(1000, self._check_timeout)

    def _activity(self, event=None):
        self.last_activity = time.time()

    def _check_timeout(self):
        if self.current_card and (time.time() - self.last_activity > SESSION_TIMEOUT_SECONDS):
            messagebox.showinfo("Session Timeout", "You have been logged out due to inactivity.")
            self.logout()
        self.after(1000, self._check_timeout)

    def show(self, name: str):
        frame = self.frames[name]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    def logout(self):
        self.current_card = None
        self.show("WelcomeScreen")

    # Data helpers
    def get_user(self, card):
        return self.data["users"].get(card)

    def add_txn(self, card, ttype, amount, balance_after, meta=None):
        user = self.get_user(card)
        if not user:
            return
        if meta is None:
            meta = {}
        user["transactions"].append({
            "time": now_str(),
            "type": ttype,
            "amount": round(float(amount), 2),
            "balance": round(float(balance_after), 2),
            "meta": meta
        })
        # keep only last 200 to limit file growth
        user["transactions"] = user["transactions"][-200:]
        save_data(self.data)

    def withdraw(self, card, amount):
        user = self.get_user(card)
        if not user:
            return False, "Unknown card"
        if amount < WITHDRAW_MIN or amount % WITHDRAW_STEP != 0:
            return False, f"Amount must be at least {WITHDRAW_MIN} and a multiple of {WITHDRAW_STEP}."
        if user["balance"] < amount:
            return False, "Insufficient funds."
        user["balance"] -= amount
        save_data(self.data)
        self.add_txn(card, "WITHDRAW", amount, user["balance"])
        return True, f"Dispensed {format_currency(amount)}. New balance: {format_currency(user['balance'])}"

    def deposit(self, card, amount):
        user = self.get_user(card)
        if not user:
            return False, "Unknown card"
        if amount < DEPOSIT_MIN or amount % DEPOSIT_STEP != 0:
            return False, f"Amount must be at least {DEPOSIT_MIN} and a multiple of {DEPOSIT_STEP}."
        user["balance"] += amount
        save_data(self.data)
        self.add_txn(card, "DEPOSIT", amount, user["balance"])
        return True, f"Deposited {format_currency(amount)}. New balance: {format_currency(user['balance'])}"

    def transfer(self, from_card, to_card, amount):
        if from_card == to_card:
            return False, "Cannot transfer to the same account."
        src = self.get_user(from_card)
        dst = self.get_user(to_card)
        if not src:
            return False, "Unknown source card."
        if not dst:
            return False, "Destination card not found."
        if amount < TRANSFER_MIN:
            return False, f"Minimum transfer is {TRANSFER_MIN}."
        if src["balance"] < amount:
            return False, "Insufficient funds."
        src["balance"] -= amount
        dst["balance"] += amount
        save_data(self.data)
        self.add_txn(from_card, "TRANSFER_OUT", amount, src["balance"], meta={"to": to_card})
        self.add_txn(to_card, "TRANSFER_IN", amount, dst["balance"], meta={"from": from_card})
        return True, f"Transferred {format_currency(amount)} to {dst['name']} ({to_card})."

    def change_pin(self, card, old_pin, new_pin):
        user = self.get_user(card)
        if not user:
            return False, "Unknown card."
        if user["pin_hash"] != hash_pin(old_pin):
            return False, "Old PIN is incorrect."
        if len(new_pin) < 4 or not new_pin.isdigit():
            return False, "PIN must be at least 4 digits."
        user["pin_hash"] = hash_pin(new_pin)
        save_data(self.data)
        return True, "PIN updated successfully."

    def export_receipt(self, lines, title="receipt"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{title}_{ts}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return filename

# -------------------------- UI SCREENS --------------------------

class Keypad(ttk.Frame):
    def __init__(self, parent, on_press, on_enter, on_clear, on_backspace):
        super().__init__(parent)
        self.on_press = on_press
        self.on_enter = on_enter
        self.on_clear = on_clear
        self.on_backspace = on_backspace

        buttons = [
            ("1", lambda: self.on_press("1")), ("2", lambda: self.on_press("2")), ("3", lambda: self.on_press("3")),
            ("4", lambda: self.on_press("4")), ("5", lambda: self.on_press("5")), ("6", lambda: self.on_press("6")),
            ("7", lambda: self.on_press("7")), ("8", lambda: self.on_press("8")), ("9", lambda: self.on_press("9")),
            ("←", self.on_backspace),        ("0", lambda: self.on_press("0")), ("C", self.on_clear),
        ]

        for i, (text, cmd) in enumerate(buttons):
            r = i // 3
            c = i % 3
            b = ttk.Button(self, text=text, command=cmd, width=6)
            b.grid(row=r, column=c, padx=6, pady=6, ipadx=4, ipady=10)

        enter_btn = ttk.Button(self, text="ENTER", command=self.on_enter)
        enter_btn.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=8, ipady=10)

class WelcomeScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app

        left = ttk.Frame(self, padding=20)
        right = ttk.Frame(self, padding=20)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y")

        ttk.Label(left, text="Welcome to", style="Header.TLabel").pack(anchor="w", pady=(10, 0))
        ttk.Label(left, text=APP_TITLE, style="Big.TLabel").pack(anchor="w")

        ttk.Label(left, text="Insert your card (select from demo)", font=("Inter", 13, "italic")).pack(anchor="w", pady=10)

        self.card_var = tk.StringVar()
        self.card_combo = ttk.Combobox(left, textvariable=self.card_var, state="readonly", width=36)
        self.card_combo.pack(anchor="w", pady=5)
        self._refresh_cards()

        ttk.Button(left, text="Insert Card", command=self.insert_card, style="Menu.TButton").pack(anchor="w", pady=12)

        info = ttk.Label(left, text=(
            "Demo Cards:\n"
            "• Alice Demo — Card: 1111222233334444 — PIN: 1234\n"
            "• Bob Demo   — Card: 5555666677778888 — PIN: 4321\n\n"
            "Tip: You can add more users by editing bank_data.json"
        ))
        info.pack(anchor="w", pady=16)

        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Button(left, text="Open Data File...", command=self.open_data_file).pack(anchor="w")

        # Right panel decoration / logo area
        ttk.Label(right, text="Secure • Fast • Simple", style="Header.TLabel").pack(pady=20)
        ttk.Label(right, text="Use the keypad on each screen\nfor easy input.", justify="center").pack(pady=10)

    def _refresh_cards(self):
        cards = list(self.app.data["users"].keys())
        self.card_combo["values"] = cards
        if cards:
            self.card_combo.current(0)

    def open_data_file(self):
        path = os.path.abspath(DATA_FILE)
        messagebox.showinfo("Locate file", f"Bank data file is at:\n{path}")
        try:
            os.startfile(path)  # Windows
        except Exception:
            try:
                # macOS
                if sys.platform == "darwin":
                    os.system(f"open '{path}'")
                else:
                    os.system(f"xdg-open '{path}'")
            except Exception:
                pass

    def insert_card(self):
        card = self.card_var.get()
        if not card:
            messagebox.showwarning("Select Card", "Please select a card to insert.")
            return
        self.app.current_card = card
        self.app.show("PinScreen")

    def on_show(self):
        self._refresh_cards()

class PinScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app

        left = ttk.Frame(self, padding=20)
        right = ttk.Frame(self, padding=20)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y")

        self.name_label = ttk.Label(left, text="", style="Header.TLabel")
        self.name_label.pack(anchor="w", pady=(10, 4))

        ttk.Label(left, text="Enter your 4+ digit PIN:").pack(anchor="w")
        self.pin_var = tk.StringVar()
        self.pin_entry = ttk.Entry(left, textvariable=self.pin_var, show="•", font=("Inter", 16), width=20)
        self.pin_entry.pack(anchor="w", pady=10)
        self.pin_entry.focus()

        ttk.Button(left, text="Login", command=self.try_login, style="Menu.TButton").pack(anchor="w", pady=10)
        ttk.Button(left, text="Cancel", command=self.app.logout).pack(anchor="w")

        self.keypad = Keypad(right,
                             on_press=self._kp_press,
                             on_enter=self.try_login,
                             on_clear=self._kp_clear,
                             on_backspace=self._kp_back)
        self.keypad.pack()

    def _kp_press(self, ch):
        self.pin_entry.insert("end", ch)

    def _kp_clear(self):
        self.pin_var.set("")

    def _kp_back(self):
        cur = self.pin_var.get()
        self.pin_var.set(cur[:-1])

    def on_show(self):
        user = self.app.get_user(self.app.current_card) if self.app.current_card else None
        if user:
            self.name_label.config(text=f"Hello, {user['name']}")
        self.pin_var.set("")
        self.pin_entry.focus_set()

    def try_login(self):
        pin = self.pin_var.get().strip()
        if not pin.isdigit() or len(pin) < 4:
            messagebox.showerror("Invalid PIN", "PIN must be at least 4 digits.")
            return
        user = self.app.get_user(self.app.current_card)
        if not user:
            messagebox.showerror("Error", "Card not recognized.")
            self.app.logout()
            return
        if user["pin_hash"] != hash_pin(pin):
            messagebox.showerror("Access Denied", "Incorrect PIN. Try again.")
            self.pin_var.set("")
            return
        self.app.add_txn(self.app.current_card, "LOGIN", 0, user["balance"])
        self.app.show("MenuScreen")

class MenuScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app

        header = ttk.Frame(self, padding=10)
        header.pack(fill="x")
        self.user_label = ttk.Label(header, text="", style="Header.TLabel")
        self.user_label.pack(side="left")
        ttk.Button(header, text="Logout", command=self.app.logout).pack(side="right")

        grid = ttk.Frame(self, padding=20)
        grid.pack(expand=True)

        buttons = [
            ("Balance", lambda: self.app.show("BalanceScreen")),
            ("Withdraw", lambda: self.app.show("AmountScreen")),
            ("Deposit", lambda: self.app.show("DepositScreen")),
            ("Transfer", lambda: self.app.show("TransferScreen")),
            ("Mini Statement", lambda: self.app.show("StatementScreen")),
            ("Change PIN", lambda: self.app.show("ChangePinScreen")),
        ]

        for i, (text, cmd) in enumerate(buttons):
            r, c = divmod(i, 3)
            btn = ttk.Button(grid, text=text, command=cmd, style="Menu.TButton", width=20)
            btn.grid(row=r, column=c, padx=12, pady=12, ipadx=8, ipady=12)

    def on_show(self):
        user = self.app.get_user(self.app.current_card)
        if user:
            self.user_label.config(text=f"{user['name']} — {user['account_number']}")

class BalanceScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app

        top = ttk.Frame(self, padding=20)
        top.pack(fill="x")
        ttk.Button(top, text="← Back", command=lambda: self.app.show("MenuScreen")).pack(side="left")
        ttk.Label(top, text="Account Balance", style="Header.TLabel").pack(side="left", padx=12)

        self.balance_label = ttk.Label(self, text="", style="Big.TLabel")
        self.balance_label.pack(pady=20)

        btns = ttk.Frame(self, padding=10)
        btns.pack()
        ttk.Button(btns, text="Export Receipt", command=self.export_receipt).pack(side="left", padx=8)
        ttk.Button(btns, text="Main Menu", command=lambda: self.app.show("MenuScreen")).pack(side="left", padx=8)

    def on_show(self):
        user = self.app.get_user(self.app.current_card)
        if user:
            self.balance_label.config(text=f"Available Balance: {format_currency(user['balance'])}")

    def export_receipt(self):
        user = self.app.get_user(self.app.current_card)
        if not user:
            return
        lines = [
            f"{APP_TITLE} — Balance Receipt",
            f"Date: {now_str()}",
            f"Name: {user['name']}",
            f"Account: {user['account_number']}",
            f"Available Balance: {format_currency(user['balance'])}",
        ]
        fn = self.app.export_receipt(lines, title="balance_receipt")
        messagebox.showinfo("Receipt Saved", f"Saved as {fn}")

class AmountScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app
        self.amount_var = tk.StringVar()

        top = ttk.Frame(self, padding=20)
        top.pack(fill="x")
        ttk.Button(top, text="← Back", command=lambda: self.app.show("MenuScreen")).pack(side="left")
        ttk.Label(top, text="Withdraw Cash", style="Header.TLabel").pack(side="left", padx=12)

        form = ttk.Frame(self, padding=20)
        form.pack(side="left", fill="both", expand=True)
        ttk.Label(form, text=f"Enter amount (min {WITHDRAW_MIN}, step {WITHDRAW_STEP}):").pack(anchor="w")
        self.entry = ttk.Entry(form, textvariable=self.amount_var, font=("Inter", 16), width=20)
        self.entry.pack(anchor="w", pady=10)

        ttk.Button(form, text="Withdraw", command=self.do_withdraw, style="Menu.TButton").pack(anchor="w", pady=8)

        self.status = ttk.Label(form, text="", foreground="#a3e635")
        self.status.pack(anchor="w", pady=6)

        self.keypad = Keypad(self,
                             on_press=self._kp_press,
                             on_enter=self.do_withdraw,
                             on_clear=self._kp_clear,
                             on_backspace=self._kp_back)
        self.keypad.pack(side="right", padx=20, pady=20)

    def on_show(self):
        self.amount_var.set("")
        self.status.config(text="")
        self.entry.focus_set()

    def _kp_press(self, ch):
        self.entry.insert("end", ch)

    def _kp_clear(self):
        self.amount_var.set("")

    def _kp_back(self):
        cur = self.amount_var.get()
        self.amount_var.set(cur[:-1])

    def do_withdraw(self):
        try:
            amount = int(self.amount_var.get())
        except Exception:
            messagebox.showerror("Invalid Input", "Enter a whole number amount.")
            return
        ok, msg = self.app.withdraw(self.app.current_card, amount)
        if ok:
            self.status.config(text=msg, foreground="#a3e635")
            if messagebox.askyesno("Receipt", "Withdrawal successful. Do you want a receipt?"):
                user = self.app.get_user(self.app.current_card)
                lines = [
                    f"{APP_TITLE} — Withdrawal Receipt",
                    f"Date: {now_str()}",
                    f"Name: {user['name']}",
                    f"Account: {user['account_number']}",
                    f"Amount: {format_currency(amount)}",
                    f"Balance: {format_currency(user['balance'])}",
                ]
                fn = self.app.export_receipt(lines, title="withdraw_receipt")
                messagebox.showinfo("Receipt Saved", f"Saved as {fn}")
        else:
            self.status.config(text=msg, foreground="#fca5a5")

class DepositScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app
        self.amount_var = tk.StringVar()

        top = ttk.Frame(self, padding=20)
        top.pack(fill="x")
        ttk.Button(top, text="← Back", command=lambda: self.app.show("MenuScreen")).pack(side="left")
        ttk.Label(top, text="Deposit Cash", style="Header.TLabel").pack(side="left", padx=12)

        form = ttk.Frame(self, padding=20)
        form.pack(side="left", fill="both", expand=True)
        ttk.Label(form, text=f"Enter amount (min {DEPOSIT_MIN}, step {DEPOSIT_STEP}):").pack(anchor="w")
        self.entry = ttk.Entry(form, textvariable=self.amount_var, font=("Inter", 16), width=20)
        self.entry.pack(anchor="w", pady=10)
        ttk.Button(form, text="Deposit", command=self.do_deposit, style="Menu.TButton").pack(anchor="w", pady=8)

        self.status = ttk.Label(form, text="", foreground="#a3e635")
        self.status.pack(anchor="w", pady=6)

        self.keypad = Keypad(self,
                             on_press=self._kp_press,
                             on_enter=self.do_deposit,
                             on_clear=self._kp_clear,
                             on_backspace=self._kp_back)
        self.keypad.pack(side="right", padx=20, pady=20)

    def on_show(self):
        self.amount_var.set("")
        self.status.config(text="")
        self.entry.focus_set()

    def _kp_press(self, ch):
        self.entry.insert("end", ch)

    def _kp_clear(self):
        self.amount_var.set("")

    def _kp_back(self):
        cur = self.amount_var.get()
        self.amount_var.set(cur[:-1])

    def do_deposit(self):
        try:
            amount = int(self.amount_var.get())
        except Exception:
            messagebox.showerror("Invalid Input", "Enter a whole number amount.")
            return
        ok, msg = self.app.deposit(self.app.current_card, amount)
        if ok:
            self.status.config(text=msg, foreground="#a3e635")
            if messagebox.askyesno("Receipt", "Deposit successful. Do you want a receipt?"):
                user = self.app.get_user(self.app.current_card)
                lines = [
                    f"{APP_TITLE} — Deposit Receipt",
                    f"Date: {now_str()}",
                    f"Name: {user['name']}",
                    f"Account: {user['account_number']}",
                    f"Amount: {format_currency(amount)}",
                    f"Balance: {format_currency(user['balance'])}",
                ]
                fn = self.app.export_receipt(lines, title="deposit_receipt")
                messagebox.showinfo("Receipt Saved", f"Saved as {fn}")
        else:
            self.status.config(text=msg, foreground="#fca5a5")

class TransferScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app
        self.card_var = tk.StringVar()
        self.amount_var = tk.StringVar()

        top = ttk.Frame(self, padding=20)
        top.pack(fill="x")
        ttk.Button(top, text="← Back", command=lambda: self.app.show("MenuScreen")).pack(side="left")
        ttk.Label(top, text="Transfer Funds", style="Header.TLabel").pack(side="left", padx=12)

        form = ttk.Frame(self, padding=20)
        form.pack(side="left", fill="both", expand=True)

        ttk.Label(form, text="Destination Card Number:").pack(anchor="w")
        self.card_entry = ttk.Entry(form, textvariable=self.card_var, font=("Inter", 14), width=26)
        self.card_entry.pack(anchor="w", pady=6)

        ttk.Label(form, text="Amount:").pack(anchor="w")
        self.amount_entry = ttk.Entry(form, textvariable=self.amount_var, font=("Inter", 16), width=20)
        self.amount_entry.pack(anchor="w", pady=6)

        ttk.Button(form, text="Transfer", command=self.do_transfer, style="Menu.TButton").pack(anchor="w", pady=8)
        self.status = ttk.Label(form, text="", foreground="#a3e635")
        self.status.pack(anchor="w", pady=6)

        # Right keypad controls the Amount field by default; toggle with radio
        right = ttk.Frame(self, padding=10)
        right.pack(side="right")
        self.kp_target = tk.StringVar(value="amount")
        ttk.Radiobutton(right, text="Keypad → Amount", variable=self.kp_target, value="amount").pack(anchor="w")
        ttk.Radiobutton(right, text="Keypad → Card", variable=self.kp_target, value="card").pack(anchor="w")
        self.keypad = Keypad(right,
                             on_press=self._kp_press,
                             on_enter=self.do_transfer,
                             on_clear=self._kp_clear,
                             on_backspace=self._kp_back)
        self.keypad.pack(padx=10, pady=10)

    def on_show(self):
        self.card_var.set("")
        self.amount_var.set("")
        self.status.config(text="")
        self.card_entry.focus_set()

    def _kp_target_entry(self):
        return self.amount_entry if self.kp_target.get() == "amount" else self.card_entry

    def _kp_press(self, ch):
        self._kp_target_entry().insert("end", ch)

    def _kp_clear(self):
        entry = self._kp_target_entry()
        entry.delete(0, "end")

    def _kp_back(self):
        entry = self._kp_target_entry()
        cur = entry.get()
        entry.delete(0, "end")
        entry.insert(0, cur[:-1])

    def do_transfer(self):
        to_card = self.card_var.get().strip()
        try:
            amount = int(self.amount_var.get())
        except Exception:
            messagebox.showerror("Invalid Input", "Enter a whole number amount.")
            return
        ok, msg = self.app.transfer(self.app.current_card, to_card, amount)
        if ok:
            self.status.config(text=msg, foreground="#a3e635")
            if messagebox.askyesno("Receipt", "Transfer successful. Do you want a receipt?"):
                src = self.app.get_user(self.app.current_card)
                dst = self.app.get_user(to_card)
                lines = [
                    f"{APP_TITLE} — Transfer Receipt",
                    f"Date: {now_str()}",
                    f"From: {src['name']}  ({self.app.current_card})",
                    f"To:   {dst['name']} ({to_card})",
                    f"Amount: {format_currency(amount)}",
                    f"Your New Balance: {format_currency(src['balance'])}",
                ]
                fn = self.app.export_receipt(lines, title="transfer_receipt")
                messagebox.showinfo("Receipt Saved", f"Saved as {fn}")
        else:
            self.status.config(text=msg, foreground="#fca5a5")

class StatementScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app

        top = ttk.Frame(self, padding=20)
        top.pack(fill="x")
        ttk.Button(top, text="← Back", command=lambda: self.app.show("MenuScreen")).pack(side="left")
        ttk.Label(top, text="Mini Statement (Last 10)", style="Header.TLabel").pack(side="left", padx=12)

        self.tree = ttk.Treeview(self, columns=("time", "type", "amount", "balance", "meta"), show="headings", height=12)
        self.tree.heading("time", text="Time")
        self.tree.heading("type", text="Type")
        self.tree.heading("amount", text="Amount")
        self.tree.heading("balance", text="Balance")
        self.tree.heading("meta", text="Meta")
        self.tree.column("time", width=170)
        self.tree.column("type", width=120)
        self.tree.column("amount", width=120, anchor="e")
        self.tree.column("balance", width=120, anchor="e")
        self.tree.column("meta", width=250)
        self.tree.pack(fill="both", expand=True, padx=20, pady=10)

        btns = ttk.Frame(self, padding=10)
        btns.pack()
        ttk.Button(btns, text="Export as Receipt", command=self.export_receipt).pack(side="left", padx=8)

    def on_show(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        user = self.app.get_user(self.app.current_card)
        if not user:
            return
        txns = user.get("transactions", [])[-10:]
        for t in txns[::-1]:
            meta_str = ""
            if t.get("meta"):
                kv = [f"{k}:{v}" for k, v in t["meta"].items()]
                meta_str = ", ".join(kv)
            self.tree.insert("", "end", values=(
                t.get("time", ""),
                t.get("type", ""),
                format_currency(t.get("amount", 0)),
                format_currency(t.get("balance", 0)),
                meta_str
            ))

    def export_receipt(self):
        user = self.app.get_user(self.app.current_card)
        if not user:
            return
        txns = user.get("transactions", [])[-10:]
        lines = [
            f"{APP_TITLE} — Mini Statement",
            f"Date: {now_str()}",
            f"Name: {user['name']}",
            f"Account: {user['account_number']}",
            "",
        ]
        for t in txns[::-1]:
            meta_str = ""
            if t.get("meta"):
                kv = [f"{k}:{v}" for k, v in t["meta"].items()]
                meta_str = " (" + ", ".join(kv) + ")"
            lines.append(f"{t['time']}  {t['type']:<14} {format_currency(t['amount']):>12}  Bal: {format_currency(t['balance'])}{meta_str}")
        fn = self.app.export_receipt(lines, title="mini_statement")
        messagebox.showinfo("Receipt Saved", f"Saved as {fn}")

class ChangePinScreen(ttk.Frame):
    def __init__(self, parent, app: ATMApp):
        super().__init__(parent)
        self.app = app

        top = ttk.Frame(self, padding=20)
        top.pack(fill="x")
        ttk.Button(top, text="← Back", command=lambda: self.app.show("MenuScreen")).pack(side="left")
        ttk.Label(top, text="Change PIN", style="Header.TLabel").pack(side="left", padx=12)

        form = ttk.Frame(self, padding=20)
        form.pack(side="left", fill="both", expand=True)

        ttk.Label(form, text="Old PIN:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(form, text="New PIN:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(form, text="Confirm New PIN:").grid(row=2, column=0, sticky="w", pady=4)

        self.old_var = tk.StringVar()
        self.new_var = tk.StringVar()
        self.conf_var = tk.StringVar()
        e1 = ttk.Entry(form, textvariable=self.old_var, show="•", font=("Inter", 14), width=20)
        e2 = ttk.Entry(form, textvariable=self.new_var, show="•", font=("Inter", 14), width=20)
        e3 = ttk.Entry(form, textvariable=self.conf_var, show="•", font=("Inter", 14), width=20)
        e1.grid(row=0, column=1, pady=4); e2.grid(row=1, column=1, pady=4); e3.grid(row=2, column=1, pady=4)

        ttk.Button(form, text="Update PIN", command=self.do_change, style="Menu.TButton").grid(row=3, column=0, columnspan=2, pady=10)
        self.status = ttk.Label(form, text="", foreground="#a3e635")
        self.status.grid(row=4, column=0, columnspan=2, sticky="w")

        self.keypad = Keypad(self,
                             on_press=self._kp_press,
                             on_enter=self.do_change,
                             on_clear=self._kp_clear,
                             on_backspace=self._kp_back)
        self.keypad.pack(side="right", padx=20, pady=20)

        self.focus_target = e1
        for w in (e1, e2, e3):
            w.bind("<FocusIn>", lambda e, widget=w: self._set_target(widget))

    def _set_target(self, w):
        self.focus_target = w

    def _kp_press(self, ch):
        if self.focus_target:
            self.focus_target.insert("end", ch)

    def _kp_clear(self):
        if self.focus_target:
            self.focus_target.delete(0, "end")

    def _kp_back(self):
        if self.focus_target:
            cur = self.focus_target.get()
            self.focus_target.delete(0, "end")
            self.focus_target.insert(0, cur[:-1])

    def on_show(self):
        self.old_var.set(""); self.new_var.set(""); self.conf_var.set("")
        self.status.config(text="")

    def do_change(self):
        oldp = self.old_var.get().strip()
        newp = self.new_var.get().strip()
        conf = self.conf_var.get().strip()
        if newp != conf:
            self.status.config(text="New PIN and confirmation do not match.", foreground="#fca5a5")
            return
        ok, msg = self.app.change_pin(self.app.current_card, oldp, newp)
        self.status.config(text=msg, foreground="#a3e635" if ok else "#fca5a5")

def main():
    app = ATMApp()
    app.mainloop()

if __name__ == "__main__":
    main()
