"""Small UI helpers; no desktop input or camera dependencies."""

import tkinter as tk

from .rendering import ACCENT, BACKGROUND, TEXT


class MenuAction:
    """Keep a command addressable while its presentation lives in the More menu."""
    def __init__(self, menu, index, labels=None):
        self.menu, self.index = menu, index
        self.labels = labels or {}

    def configure(self, *, text):
        self.menu.entryconfigure(self.index, label=self.labels.get(text, text))

    def invoke(self):
        self.menu.invoke(self.index)


def compact_button(parent, text, callback, *, accent=False):
    button = tk.Button(parent, text=text, command=callback, background=BACKGROUND,
                       foreground=ACCENT if accent else TEXT, activebackground="#28343d",
                       activeforeground=TEXT, relief="flat", borderwidth=0,
                       highlightthickness=1, highlightbackground=BACKGROUND, highlightcolor=ACCENT,
                       font=("Segoe UI", -11), padx=9, pady=2, takefocus=True, cursor="hand2")
    button.bind("<Return>", lambda event: button.invoke())
    return button
