import tkinter as tk


class TextLineNumbers(tk.Canvas):
    """The line numbers for a text widget"""

    def __init__(self, *args, textwidget=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.textwidget = textwidget
        self.redraw()

    def redraw(self, *args):
        """redraw line numbers"""
        self.delete('all')

        i = self.textwidget.index('@0,0')
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split('.')[0]
            self.create_text(2, y, anchor='nw', text=linenum)
            i = self.textwidget.index(f'{i}+1line')

        # Refreshes the canvas widget every 20ms
        self.after(20, self.redraw)


class ResizeFrame(tk.Frame):
    """Frame that uses `place`.
    `relx`, `rely` are the top-left coordinates relative to the master widget.
    `relwidth`, `relheight` are the relative width and height. The position arguments
    should be between 0 and 1 inclusive. Don't use this frame with `pack` or `grid` and
    there is no need to `place` it. It places itself automatically"""

    def __init__(self, master, relx, rely, relwidth, relheight, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.relx = relx
        self.rely = rely
        self.relwidth = relwidth
        self.relheight = relheight

        self.place(relx=self.relx,
                   rely=self.rely,
                   relwidth=self.relwidth,
                   relheight=self.relheight)


class ScrollTextFrame(tk.Frame):
    """Frame that contains a text widget and optional horizonal and/or
    vertical scrollbars"""

    def __init__(self, *args, vsb=True, hsb=True, text_widget_type=tk.Text, text_kwargs={}, **kwargs):
        super().__init__(*args, **kwargs)

        self.has_vsb = vsb
        self.has_hsb = hsb

        self.create_widgets(text_widget_type, text_kwargs)
        self.grid_widgets()

    def create_widgets(self, text_widget_type, text_kwargs):
        self.text = text_widget_type(self, **text_kwargs)

        if self.has_vsb:
            self.vsb = tk.Scrollbar(
                self, orient='vertical', command=self.text.yview)
            self.text.configure(yscrollcommand=self.vsb.set)
        else:
            self.vsb = None

        if self.has_hsb:
            self.hsb = tk.Scrollbar(
                self, orient='horizontal', command=self.text.xview)
            self.text.configure(xscrollcommand=self.hsb.set)
        else:
            self.hsb = None

    def grid_widgets(self, *, base_column=0, base_row=0):
        self.grid_rowconfigure(base_row, weight=1)
        self.grid_columnconfigure(base_column, weight=1)

        self.text.grid(row=base_row, column=base_column, sticky='nesw')
        if self.vsb:
            self.vsb.grid(
                row=base_row, column=base_column + 1, sticky='nesw')
        if self.hsb:
            self.hsb.grid(
                row=base_row + 1, column=base_column, sticky='nesw')
