import tkinter as tk
from tkinter import Frame, Label, Button, Scrollbar, Canvas

class ScrollableFrame(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = Canvas(self, borderwidth=0)
        self.vbar = Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = Frame(self.canvas)
        self._win = self.canvas.create_window((0,0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._win, width=e.width))

        # Optional: platform-aware mousewheel bindings
        self.inner.bind_all("<MouseWheel>", self._on_mousewheel)   # Windows / macOS
        self.inner.bind_all("<Button-4>", self._on_mousewheel)     # Linux scroll up
        self.inner.bind_all("<Button-5>", self._on_mousewheel)     # Linux scroll down

    def _on_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            self.canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            # Windows: event.delta is multiple of 120
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")