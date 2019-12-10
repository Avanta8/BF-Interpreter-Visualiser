import codecs
import itertools
import re
import string
import tkinter as tk
import os
from tkinter import filedialog
from collections import deque
from interpreter import BFInterpreter, ExecutionEndedError, NoPreviousExecutionError, NoInputError, ProgramSyntaxError, ProgramRuntimeError, ErrorTypes


ASCII_PRINTABLE = set(string.printable)
CHARS_TO_ESCAPE = {
    '\n': r'\n',
    '\t': r'\t',
    '\r': r'\r'
}


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


class TagText(tk.Text):
    """Automatically tags everything using `tag_func`. `tag_func` must return a 1d iterable
    of char - tag pairs that can be unpacked into a suitable argument for tk.Text.insert"""

    def __init__(self, *args, tag_func, **kwargs):
        super().__init__(*args, **kwargs)

        self.tag_func = tag_func

        self._commands_dict = {
            'insert': self._insert
        }

        self._orig = self._w + '_orig'
        self.tk.call('rename', self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

    def _proxy(self, command, *args):
        try:
            result = self._commands_dict.get(
                command, self.tk.call)(self._orig, command, *args)
        except tk.TclError:
            return None

        return result

    def _insert(self, name, command, index, *args):
        if len(args) > 1:
            raise Exception(
                'Tagging for adding more than once thing is not yet supported.'
                f'Arguments length was: {len(args)}, args: {args}')

        result = self.tk.call(name, command, index, *self.tag_func(args[0]))
        return result


class ResizeFrame(tk.Frame):
    """Frame that uses `place` and resizes itself whenever `ResizeFrame.resize` is called.
    `relx`, `rely` are the top-left coordinates relative to the master widget.
    `relwidth`, `relheight` are the relative width and height. The position arguments
    should be between 0 and 1 inclusive. Don't use this frame with `pack` or `grid` and
    there is no need to `place` it. It places itself automatically whenever
    `ResizeFrame.resize` is called."""

    def __init__(self, master, relx, rely, relwidth, relheight, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.relx = relx
        self.rely = rely
        self.relwidth = relwidth
        self.relheight = relheight

    def resize(self):
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


class FileFrame(ResizeFrame):
    """Frame for file handling. Contains 4 buttons: New, Open, Save, Save As."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()

        self.file_types = (('Brainfuck (*.b)', '*.b'), ('All Files', '*.*'))
        self.current_filename = ''

    def create_widgets(self):
        """4 buttons: New, Open, Save, Save As."""
        new_button = tk.Button(
            self, width=8, text='New', command=self.new_file)
        open_button = tk.Button(
            self, width=8, text='Open', command=self.open_file)
        save_button = tk.Button(
            self, width=8, text='Save', command=self.save_file)
        save_as_button = tk.Button(
            self, width=8, text='Save As', command=self.save_as)

        new_button.grid(row=0, column=0)
        open_button.grid(row=0, column=1)
        save_button.grid(row=0, column=2)
        save_as_button.grid(row=0, column=3)

    def new_file(self):
        """Create a new blank file."""
        self.master.load_program_text('')
        self.current_filename = ''
        self.rename_window()

    def open_file(self):
        """Open the selected file. If no file is selected, then do nothing."""
        filename = filedialog.askopenfilename(filetypes=self.file_types)
        if not filename:
            return

        read = self.read_file(filename)
        self.master.load_program_text(read)
        self.current_filename = filename
        self.rename_window()

    def save_file(self):
        """Save the current file. If the file has not previously been saved,
        then have the save functionality as save as."""
        if not self.current_filename:
            self.save_as()
            return

        self.write_file(self.current_filename)

    def save_as(self):
        """Save the file as a new filename. If no filename is selected, then do nothing."""
        filename = filedialog.asksaveasfilename(
            filetypes=self.file_types, defaultextension='.*')
        if not filename:
            return

        self.write_file(filename)
        self.current_filename = filename
        self.rename_window()

    def read_file(self, filename):
        """Read `filename` and return the contents."""
        with open(filename, 'r') as file:
            read = file.read()
        return read

    def write_file(self, filename):
        """Get the program text and write that to `filename`."""
        program_text = self.master.get_program_text()
        with open(filename, 'w') as file:
            file.write(program_text)

    def rename_window(self):
        """Rename the root window based on the current file."""
        title = f'{os.path.basename(self.current_filename)} - BF' if self.current_filename else 'BF'
        self.winfo_toplevel().wm_title(title)


class CodeFrame(ResizeFrame, ScrollTextFrame):
    """Frame where the user types their code."""

    def __init__(self, *args, text_widget_type=TagText,
                 text_kwargs={'wrap': 'none'}, **kwargs):
        super().__init__(*args, text_widget_type=text_widget_type,
                         text_kwargs=text_kwargs, **kwargs)

    def create_widgets(self, *args, **kwargs):
        super().create_widgets(*args, **kwargs)
        # These are in order of priority (least to highest)
        self.text.tag_configure('breakpoint', background='yellow')
        self.text.tag_configure('highlight', background='grey')
        self.text.tag_configure('error', background='brown')

        self.text.bind('<Tab>', self.add_tab)
        self.text.bind('<Shift-Tab>', self.remove_tab)
        self.text.bind('<Return>', self.return_key)
        self.text.bind('<BackSpace>', self.backspace_key)

        self.code_line_numbers = TextLineNumbers(
            self, textwidget=self.text, width=30)

    def grid_widgets(self):
        super().grid_widgets(base_row=0, base_column=1)

        self.code_line_numbers.grid(row=0, column=0, sticky='nesw')

    def add_tab(self, event):
        self.text.event_generate('<Key>', when='now')
        selected = self.text.tag_ranges('sel')
        if not selected:
            self.text.insert('insert', '    ')
        else:
            # First line of selection
            start = int(selected[0].string.split('.')[0])
            # Last line of selection
            end = int(selected[1].string.split('.')[0])
            for line in range(start, end + 1):
                # Insert 4 spaces at the start of every selected line
                self.text.insert(f'{line}.0', '    ')

            # Inserting breaks the selection so fix the selection
            self.text.tag_remove('sel', '1.0')
            self.text.tag_add('sel', f'{selected[0]}+4c', f'{selected[1]}+4c')
        return 'break'

    def remove_tab(self, event):
        self.text.event_generate('<Key>', when='now')
        selected = self.text.tag_ranges('sel')
        if selected:
            # First line of selection
            start = int(selected[0].string.split('.')[0])
            # Last line of selection
            end = int(selected[1].string.split('.')[0])
        else:
            # If nothing is selected, then the first and last line of the selection
            # is the current line
            start = end = int(self.text.index('insert').split('.')[0])

        for line in range(start, end + 1):
            index = self._search_spaces(line)
            col = int(index.split('.')[1])
            self.text.delete(f'{line}.0', f'{line}.{min(col, 4)}')

        # This method seems to work without having to replace the current selection.
        # However, if it breaks, remove and add the selected tag like in `self.add_tag`
        return 'break'

    def return_key(self, event):
        self.text.event_generate('<Key>', when='now')

        # I still need to make this delete stuff if something is selected but I cba rn.

        insert = self.text.index('insert')

        # Find the amount of spaces at the start of the line
        line = int(insert.split('.')[0])
        index = self._search_spaces(line)
        spaces = int(index.split('.')[1])

        # Now insert newline along with the required amount of spaces
        self.text.insert(insert, '\n' + ' ' * spaces)
        return 'break'

    def backspace_key(self, event):
        self.text.event_generate('<Key>', when='now')

        # Allow for default behaviour if anything is selected
        selected = self.text.tag_ranges('sel')
        if selected:
            return None

        insert = self.text.index('insert')
        line, col = map(int, insert.split('.'))
        index = self._search_spaces(line)

        # Allow for default behaviour if cursor is at the start of the
        # line or if there are non-whitespace characters between the start
        # of the line and the current cursor.
        if col == 0 or insert != index:
            return None

        spaces = int(index.split('.')[1])
        to_delete = spaces % 4 or 4
        self.text.delete(f'{line}.0', f'{line}.{to_delete}')
        return 'break'

    def _search_spaces(self, line):
        """Searches for the first non-space character in `line`"""
        linestart = f'{line}.0'
        lineend = self.text.index(f'{linestart} lineend')
        index = self.text.search(
            '[^ ]', linestart, stopindex=lineend, regexp=True) or lineend
        return index


class TapeFrame(ResizeFrame):
    """Frame where the tape and cells are displayed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cells = []
        self.row_headings = []
        self.column_headings = []

        self.create_frame()

        self.reset()

    def create_frame(self):

        self.column_heading_frame = tk.Frame(self)
        self.column_heading_frame.grid(row=0, column=0, sticky='nesw')

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.frame = tk.Frame(self.canvas)
        self.vsb = tk.Scrollbar(self, orient="vertical",
                                command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.canvas.grid(row=1, column=0, sticky='nesw')
        self.vsb.grid(row=1, column=1, sticky='nesw')
        self.canvas_frame = self.canvas.create_window(
            0, 0, window=self.frame, anchor='nw')

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.frame.bind('<Configure>', lambda e: self.init_tape())

        self.frame.columnconfigure(0, weight=1)

        # Creates the empty cell at the start of the headings.
        # This cell should never be used. It's just to make the columns fit nicely.
        zero_heading = next(self.iter_column_headings())
        zero_heading.config(state='disabled')
        zero_heading.grid(row=0, column=0, sticky='nsew')
        self.column_headings.pop()

        for x in range(21):  # Max columns should be 20. Update this value if that changes
            self.column_heading_frame.grid_columnconfigure(x, weight=1)
            self.frame.columnconfigure(x, weight=1)

    def reset(self):
        for cell in self.cells:
            cell.destroy()
        self.cells = []

        for heading in self.row_headings + self.column_headings:
            heading.destroy()
        self.row_headings = []
        self.column_headings = []

        for _ in range(20):
            self.add_cell()

        self.last_tape_length = None
        self.last_rows = None
        self.last_columns = None
        self.last_cell_ind = 0
        self.init_tape()

        self.canvas.yview_moveto(0)

    def init_tape(self):
        self.resize_canvas()

        width = self.canvas.winfo_width()
        for columns in (20, 10, 5):
            if width / (columns + 1) > 35:
                break
        else:
            columns = width // 35
            if columns == 0:
                return

        # Don't have an empty extra row at the end if self.tape_length
        # if divided by columns perfectly
        rows = self.tape_length // columns + \
            (1 if self.tape_length % columns else 0)

        # Don't update if things were the same as last time
        if self.last_tape_length == self.tape_length and self.last_rows == rows and self.last_columns == columns:
            return

        # Don't update headings if they are the same as the previous ones
        if not (self.last_columns == columns and self.last_rows == rows):
            self.create_all_headings(rows, columns)
        self.place_all_cells(columns)

        self.last_tape_length = self.tape_length
        self.last_rows = rows
        self.last_columns = columns

    def place_all_cells(self, columns):
        for i, cell in enumerate(self.cells):
            row, column = divmod(i, columns)
            self.place_cell(cell, row, column)

    def place_cell(self, cell, row, column):
        cell.grid(row=row, column=column + 1, sticky='nsew')

    def create_all_headings(self, rows, columns):
        column_headings = self.iter_column_headings()
        for x, heading in zip(range(columns), column_headings):
            heading.grid(row=0, column=x + 1, sticky='nsew')
            heading.config(state='normal')
            heading.delete(0, 'end')
            heading.insert(0, x)
            heading.config(state='disabled')
        for heading in self.column_headings[x + 1:]:
            heading.grid_forget()

        row_headings = self.iter_row_headings()
        for y, heading in zip(range(rows), row_headings):
            heading.grid(row=y, column=0, sticky='nesw')
            heading.config(state='normal')
            heading.delete(0, 'end')
            heading.insert(0, y * columns)
            heading.config(state='disabled')
        for heading in self.row_headings[y + 1:]:
            heading.grid_forget()

    def resize_canvas(self, *args):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.itemconfig(
            self.canvas_frame, width=self.canvas.winfo_width())

    def set_cell(self, cell_ind, value, to_update=True):
        try:
            cell = self.cells[cell_ind]
        except IndexError:
            cell = self.add_cell()
            if to_update:
                self.init_tape()

        last_cell = self.cells[self.last_cell_ind]

        last_cell.config(disabledbackground='white')

        cell.config(state='normal')
        cell.delete(0, 'end')
        cell.insert(0, value)
        cell.config(state='disabled', disabledbackground='red')

        self.last_cell_ind = cell_ind

        if to_update:
            self.scroll_to_current()

    def add_cell(self):
        cell = tk.Entry(self.frame)
        cell.insert(0, 0)
        cell.config(state='disabled', disabledbackground='white',
                    disabledforeground='black')
        self.cells.append(cell)
        return cell

    def update_cells(self, cell_vals):
        for i, val in enumerate(cell_vals):
            self.set_cell(i, val, False)
        self.init_tape()

    def scroll_to_current(self):
        self.update_idletasks()
        cell_row = self.last_cell_ind // self.last_columns
        offset = cell_row / self.last_rows
        y_top, y_bottom = self.canvas.yview()
        view_height = y_bottom - y_top
        rows_encompassed = self.last_rows * view_height
        row_height = view_height / rows_encompassed

        if offset < y_top:
            self.canvas.yview_moveto(offset)
        elif offset + row_height > y_bottom:
            self.canvas.yview_moveto(offset - view_height + row_height)

    def iter_column_headings(self):
        for heading in self.column_headings:
            yield heading
        while True:
            heading = tk.Entry(self.column_heading_frame)
            heading.config(disabledbackground='grey',
                           disabledforeground='black')
            self.column_headings.append(heading)
            yield heading

    def iter_row_headings(self):
        for heading in self.row_headings:
            yield heading
        while True:
            heading = tk.Entry(self.frame)
            heading.config(disabledbackground='grey',
                           disabledforeground='black')
            self.row_headings.append(heading)
            yield heading

    def resize(self):
        super().resize()
        self.init_tape()

    @property
    def tape_length(self):
        return len(self.cells)


class CommandsFrame(ResizeFrame):
    """Frame containing interpreter commands: run, step, stop, pause, back, jump.
    Also contains settings: runspeed. Also contains input and output."""

    def __init__(self, *args, max_jump=1_000_000, **kwargs):
        super().__init__(*args, **kwargs)

        self.max_jump = max_jump
        self.create_widgets()

        self._commands = {
            'run': self._run,
            'step': self._step,
            'pause': self._pause,
            'stop': self._stop,
            'back': self._back
        }

    def create_widgets(self):
        input_frame = ResizeFrame(self, 0, 0, 1, .15)
        input_label = tk.Label(input_frame, text='Input:', width=10)
        input_entry_frame = ScrollTextFrame(input_frame, vsb=False, text_kwargs={
                                            'wrap': 'none'})
        self.input_entry = input_entry_frame.text
        self.input_entry.config(height=1)
        self.input_entry.tag_configure('highlight', background='grey')
        input_label.pack(side='left')
        input_entry_frame.pack(side='left')

        scale_frame = ResizeFrame(self, 0, .15, .85, .20)
        self.instruction_counter_text = tk.StringVar()
        instruction_label = tk.Label(
            scale_frame, textvariable=self.instruction_counter_text)
        self.speed_scale = tk.Scale(scale_frame, from_=1, to=100,
                                    orient='horizontal', command=self.master.set_runspeed,
                                    showvalue=False)
        speed_label = tk.Label(scale_frame, text='Speed:', width=10)
        self.speed_fast_mode = tk.BooleanVar()
        speed_checkbutton = tk.Checkbutton(scale_frame, text='faster',
                                           variable=self.speed_fast_mode,
                                           command=self.master.set_runspeed)
        instruction_label.pack(side='top', anchor='w', expand=True)
        speed_label.pack(side='left')
        self.speed_scale.pack(side='left', fill='x', expand=True)
        speed_checkbutton.pack(side='right', padx=(10, 0))

        self.buttons_frame = ResizeFrame(self, 0, .35, .85, .15)
        self.run_button = tk.Button(
            self.buttons_frame, text='run', command=self.run_command)
        self.step_button = tk.Button(
            self.buttons_frame, text='step', command=self.step_command)
        self.stop_button = tk.Button(
            self.buttons_frame, text='stop', command=self.stop_command)
        self.pause_button = tk.Button(
            self.buttons_frame, text='pause', command=self.pause_command)
        self.back_button = tk.Button(
            self.buttons_frame, text='back', command=self.back_command)
        self.buttons = [self.run_button, self.step_button, self.stop_button,
                        self.pause_button, self.back_button]

        output_frame = ResizeFrame(self, 0, .5, 1, .5)
        output_label = tk.Label(output_frame, text='Output:', width=10)
        output_text_frame = ScrollTextFrame(
            output_frame, text_kwargs={'wrap': 'none', 'state': 'disabled'})
        self.output_text = output_text_frame.text
        self.error_text_frame = ScrollTextFrame(
            output_frame, text_kwargs={'wrap': 'none', 'height': 1, 'relief': 'solid', 'state': 'disabled'}, vsb=False)
        self.error_text = self.error_text_frame.text
        output_frame.grid_columnconfigure(0, weight=1)
        output_frame.grid_rowconfigure(1, weight=1)
        output_label.grid(row=0, column=0, sticky='nesw')
        output_text_frame.grid(row=1, column=0, sticky='nesw')
        self.error_text_frame.grid(row=2, column=0, sticky='nesw')
        self.remove_error_text()  # Start without the error box displayed

        jump_frame = ResizeFrame(self, .86, .15, .14, .38)
        jump_label = tk.Label(jump_frame, text='Jump:')
        self.jump_entry = tk.Entry(jump_frame)
        jump_forwards = tk.Button(
            jump_frame, text='Forw', command=lambda: self.jump_command(1))
        jump_backwards = tk.Button(
            jump_frame, text='Bckw', command=lambda: self.jump_command(-1))
        jump_label.pack(side='top', fill='both')
        self.jump_entry.pack(side='top', fill='both')
        jump_forwards.pack(side='top', fill='both')
        jump_backwards.pack(side='top', fill='both')

        self.frames = [self.buttons_frame, input_frame,
                       scale_frame, output_frame, jump_frame]

    def clear_buttons(self):
        """Clear all the buttons from the screen."""
        for button in self.buttons:
            button.grid_forget()

    def reset_buttons(self):
        """Reset the buttons so how they should start like (run and step)"""
        self.clear_buttons()
        self.grid_button(self.run_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)

    def command_handle(self, command):
        self.clear_buttons()
        self.remove_error_text()
        self._commands[command]()

    def _run(self):
        self.grid_button(self.stop_button, row=0, column=0)
        self.grid_button(self.pause_button, row=0, column=1)
        self.master.run()

    def _step(self):
        self.grid_button(self.stop_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)
        self.grid_button(self.back_button, row=0, column=2)
        self.grid_button(self.run_button, row=0, column=3)
        self.master.step()

    def _pause(self):
        self.grid_button(self.stop_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)
        self.grid_button(self.back_button, row=0, column=2)
        self.grid_button(self.run_button, row=0, column=3)
        self.master.pause()

    def _stop(self):
        self.grid_button(self.run_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)
        self.master.stop()

    def _back(self):
        self.grid_button(self.stop_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)
        self.grid_button(self.back_button, row=0, column=2)
        self.grid_button(self.run_button, row=0, column=3)
        self.master.back()

    def run_command(self):
        self.command_handle('run')

    def step_command(self):
        self.command_handle('step')

    def pause_command(self):
        self.command_handle('pause')

    def stop_command(self):
        self.command_handle('stop')

    def back_command(self):
        self.command_handle('back')

    def jump_command(self, direction):
        self.pause_command()
        try:
            steps = int(self.jump_entry.get())
        except ValueError:
            return

        if steps > self.max_jump:
            steps = self.max_jump
            self.jump_entry.delete(0, 'end')
            self.jump_entry.insert(0, str(steps))
        self.master.jump(steps * direction)

    def grid_button(self, button, row, column):
        button.grid(row=row, column=column, sticky='nswe', padx=2)

    def configure_buttons(self):
        for i in range(4):
            self.buttons_frame.columnconfigure(
                i, weight=1, minsize=self.winfo_width() * .85 / 4)

    def resize(self):
        super().resize()
        for frame in self.frames:
            frame.resize()
        self.configure_buttons()

    def get_input_options(self):
        return self.input_entry, self.output_text, self.speed_scale, self.speed_fast_mode

    def update_instruction_counter(self, instruction_count):
        self.instruction_counter_text.set(
            f'Current Instruction: {instruction_count:,}')

    def remove_error_text(self):
        orig_state = self.error_text.cget('state')
        if orig_state == 'disabled':
            self.error_text.config(state='normal')

        self.error_text_frame.grid_remove()
        self.error_text.delete('1.0', 'end')

        if orig_state == 'disabled':
            self.error_text.config(state='disabled')

    def display_error_text(self, text):
        self.error_text.configure(state='normal')
        self.remove_error_text()
        self.error_text.insert('1.0', text)
        self.error_text.configure(state='disabled')
        self.error_text_frame.grid()


class Brainfuck(tk.Frame):
    """Main frame for the interpreter. Everyting goes in here"""

    def __init__(self, master):
        """Create all widgets. Reset everything."""
        super().__init__(master)

        self.code_tags_to_remove = []

        self.pack(fill='both', expand=True)
        self.create_widgets()
        self.bind('<Configure>', self.resize)

        self.set_runspeed()
        self.resize()

        self.file_frame.new_file()

        self.reset_all()

    def create_widgets(self):
        """Create the 4 main frames that go in the interpreter.

        Main frames:
            file_frame -- File commands: (new, open, save, save as),
            code_text_frame -- Where the user types the code to be interpreted,
            tape_frame -- The frame where the cells of the tape are displayed,
            commands_frame -- The commands for the interpreter eg. run, step, change
                              speed etc. Also where input / output is."""

        # Create file frame
        self.file_frame = FileFrame(self, .02, .02, .5, .08)

        # Create code text frame
        self.command_highlights = {
            '[': 'loop',
            ']': 'loop',
            '>': 'pointer',
            '<': 'pointer',
            '+': 'cell',
            '-': 'cell',
            ',': 'io',
            '.': 'io'
        }

        # Function for create the correct tag for chars
        def tag_func(chars):
            groups = itertools.groupby(
                chars, key=lambda x: self.command_highlights.get(x, 'comment'))
            return itertools.chain.from_iterable((''.join(group), key) for key, group in groups)

        self.code_text_frame = CodeFrame(self, .02, .1, .5, .88, text_kwargs={
            'undo': True,
            'wrap': 'none',
            'tag_func': tag_func,
            # 'font': ('Consolas', 10)
        })
        self.code_text = self.code_text_frame.text
        self.code_text.bind(
            '<Control-s>', lambda e: self.file_frame.save_file())
        self.code_text.bind('<Key>', self.code_text_input)
        self.code_text.bind('<Button-3>', self.set_breakpoint)  # rmb
        for tag, colour in ('comment', 'grey'), ('loop', 'red'), ('io', 'blue'), ('pointer', 'purple'), ('cell', 'green'):
            self.code_text.tag_configure(tag, foreground=colour)

        # Create tape frame
        self.tape_frame = TapeFrame(self, .54, .1, .44, .3)

        # Create commands frame
        self.commands_frame = CommandsFrame(self, .54, .42, .44, .56)
        self.input_entry, self.output_text, self.speed_scale, self.fast_mode = self.commands_frame.get_input_options()
        self.input_entry.bind('<Control-v>', self.input_entry_paste)
        self.input_entry.bind('<Key>', self.input_entry_input)

        self.main_frames = [self.file_frame, self.code_text_frame,
                            self.tape_frame, self.commands_frame]

    def resize(self, *args):
        """Called when the screen is resized"""
        self.update()
        for frame in self.main_frames:
            frame.resize()

    def init_interpreter(self):
        """Reset output text and previous interpreter settings. Then initialise
        a new `self.interpreter`. Program text is gotten again. Return True if
        initislising new interpreter was successful else False."""
        self.reset_all()

        self.parse_code_text()
        try:
            self.interpreter = BFInterpreter(
                self.get_program_text(), self.get_next_input_char)
        except ProgramSyntaxError as error:
            self.handle_interpreter_error(error)
            self.commands_frame.reset_buttons()
            return False

        return True

    def handle_interpreter_error(self, error):
        """Handle error from interpreter. May be a syntax error or runtime error.
        These errors do not include missing input."""
        error_type = error.error
        if error_type is ErrorTypes.UNMATCHED_OPEN_PAREN:
            message = 'Unmatched opening parentheses'
        elif error_type is ErrorTypes.UNMATCHED_CLOSE_PAREN:
            message = 'Unmatched closing parentheses'
        elif error_type is ErrorTypes.INVALID_TAPE_CELL:
            message = 'Tape pointer out of bounds'
        else:
            raise error

        if error.location is not None:
            location = self.pointer_to_index[error.location]
            line, char = map(int, location.split('.'))
            full_message = f'{message} at: line {line}, char {char + 1}'

            self.commands_frame.display_error_text(full_message)
            self.code_text.tag_add('error', location)
            self.code_text.see(location)
            self.code_tags_to_remove.append(('error', location))
        else:
            self.commands_frame.display_error_text(message)

    def reset_all(self):
        """Reset output text, previous interpreter settings and instruction count.
        Doesn't reset code text."""
        self.reset_output()
        self.reset_past_input_spans()
        self.reset_hightlights()
        self.tape_frame.reset()
        self.commands_frame.update_instruction_counter(0)

    def step(self, display=True):
        """Step one instruction. If execution has ended, then commands are paused.
        Change will be displayed if `display` is True. Return True if an
        instruction was executed successfully and there is no reason to stop else False."""
        if not self.interpreter:
            successful = self.init_interpreter()
            # Return False if not successful in creating new interpreter
            if not successful:
                return False

        try:
            self.code_pointer = self.interpreter.step()
        except ExecutionEndedError:
            # Execution has finised
            self.commands_frame.pause_command()
            self.commands_frame.display_error_text('Execution finished')
            return False
        except NoInputError:
            # No input was given (from `self.input_func`)
            self.commands_frame.pause_command()
            self.commands_frame.display_error_text('Enter input')
            return False
        except ProgramRuntimeError as error:
            self.commands_frame.pause_command()
            self.handle_interpreter_error(error)
            return False

        if display:
            self.configure_current()

        if self.code_pointer in self.breakpoints:
            self.commands_frame.pause_command()
            return False

        return True

    def run(self):
        """Run instructions until execution is paused or execution has ended."""
        if not self.interpreter:
            successful = self.init_interpreter()
            # Return if not successful in creating new interpreter
            if not successful:
                return
        self.run_code = True
        self.run_steps()

    def run_steps(self):
        """`self.step` every `self.runspeed` ms until `self.runcode` is False.
        Step `self.steps_skip` more times if it is non-zero."""
        if not self.run_code:
            return

        for _ in range(self.steps_skip + 1):
            if not self.step():
                return

        # step again after `self.runspeed` ms
        self.after(self.runspeed, self.run_steps)

    def stop(self):
        """Stop execution. Reset `self.interpreter`."""
        self.interpreter = None
        self.run_code = False
        self.reset_hightlights()
        self.tape_frame.reset()

    def pause(self):
        """Pause execution."""
        self.run_code = False

    def back(self, display=True):
        """Step one instruction backwards.
        Change will be displayed if `display` is True. Return True if
        stepping backwards was successful else False (no previous execution)."""

        if not self.interpreter:
            return False

        if self.interpreter.instruction_count == 0:
            self.commands_frame.display_error_text('No previous execution')
            return False

        # Rollback input if the current command is to take input
        if self.interpreter.current_instruction == ',':
            self.highlight_input(self.past_input_spans.pop(),
                                 self.past_input_spans[-1])

        self.code_pointer = self.interpreter.back()

        if display:
            self.configure_current()

        if self.code_pointer in self.breakpoints:
            self.commands_frame.pause_command()
            return False

        return True

    def jump(self, steps):
        """Jump `steps` number of steps forwards if `steps` is positive else backwards."""
        method = self.step if steps > 0 else self.back

        for _ in range(abs(steps)):
            if not method(False):
                break

        if self.interpreter:
            self.tape_frame.update_cells(self.interpreter.tape)
            self.configure_current()

    def configure_current(self):
        """Configures all the necessary output after a command."""
        self.highlight_cell()
        self.configure_output()
        self.hightlight_text()
        self.commands_frame.update_instruction_counter(
            self.interpreter.instruction_count)

    def hightlight_text(self):
        """Remove the hightlighting from the previous command and add the new highlighting."""
        self.remove_code_tags()
        if self.code_pointer >= 0:
            index = self.pointer_to_index[self.code_pointer]
            self.code_text.tag_add('highlight', index)
            # Scroll to current command if it is offscreen
            self.code_text.see(index)
            self.code_tags_to_remove.append(('highlight', index))

    def remove_code_tags(self):
        """Remove all tags in `self.code_tags_to_remove` from `self.code_text`."""
        while self.code_tags_to_remove:
            self.code_text.tag_remove(*self.code_tags_to_remove.pop())

    def highlight_cell(self):
        """Highlight the current cell that `self.interpreter.tape_pointer`
        is pointing to."""
        self.tape_frame.set_cell(
            self.interpreter.tape_pointer, self.interpreter.current_cell)

    def configure_output(self):
        """Make sure the output is correct. If the current output is too short, add
        the missing characters to the end. If the current output is too long, delete
        the extra characters"""
        output = self.interpreter.output
        current_output = self.output_text.get('1.0', 'end-1c')

        if len(output) > len(current_output):
            self.output_text.configure(state='normal')
            self.output_text.insert(
                'end', output[len(current_output):])
            self.output_text.configure(state='disabled')
        elif len(output) < len(current_output):
            self.output_text.configure(state='normal')
            self.output_text.delete(
                f'end-{len(current_output) - len(output) + 1}c', 'end')
            self.output_text.configure(state='disabled')

    def reset_output(self):
        """Delete all of the current output."""
        self.output_text.configure(state='normal')
        self.output_text.delete('1.0', 'end')
        self.output_text.configure(state='disabled')

    def set_runspeed(self, *args):
        """Set `self.runspeed` to the current speed to run at (ms between each step).
        Called if `self.speed_scale` or `self.fast_mode` was changed."""
        speed_scale = self.speed_scale.get()
        fast_mode = self.fast_mode.get()
        # runspeed = (110 - speed_scale) // 10 if fast_mode \
        #     else int(1000 / (speed_scale * speed_scale * .0098 + 1))
        if fast_mode:
            self.runspeed = 10
            self.steps_skip = (speed_scale - 1) // 5
        else:
            self.runspeed = int(1000 / (speed_scale * speed_scale * .0098 + 1))
            self.steps_skip = 0

    def get_program_text(self):
        """Return the current program text."""
        return self.code_text.get('1.0', 'end-1c')

    def get_next_input_char(self):
        """Return the next character in the input. If there is no next input, return `None`."""
        last_start, last_end = self.past_input_spans[-1]

        # Get the next character of input starting from the end of the last character of input
        match_obj = re.match(
            r'^(\\(?:n|r|t|\\|\d{1,3})|.)', self.input_entry.get(last_end, 'end-1c'))
        if not match_obj:
            return None
        match = match_obj[0]

        # A match of length 1 means that the match was just a standard chararacter.
        # A match of more than length 1 means that the match was an escape sequence
        if len(match) > 1:
            if match[1].isdecimal():
                # Ascii code
                match = chr(int(match[1:]))
            else:
                # Escape character (\n, \r, \t)
                match = codecs.decode(match, 'unicode_escape')

        new_input_span = (self.input_entry.index(f'{last_end}+{match_obj.start()}c'),
                          self.input_entry.index(f'{last_end}+{match_obj.end()}c'))
        self.past_input_spans.append(new_input_span)

        self.highlight_input()

        return match

    def highlight_input(self, last_input_span=None, new_input_span=None):
        """Remove the hightlighting from `last_input_span` and add
        highlighting to `new_input_span`. As default, set `last_input_span`
        and `new_input_span` to the 2nd last and last past input spans."""
        if not last_input_span:
            last_input_span = self.past_input_spans[-2]
        if not new_input_span:
            new_input_span = self.past_input_spans[-1]
        self.input_entry.tag_remove(
            'highlight', last_input_span[0], last_input_span[1])
        self.input_entry.tag_add(
            'highlight', new_input_span[0], new_input_span[1])
        self.input_entry.see(new_input_span[1])

    def input_entry_input(self, event):
        """Event called whenever a key is pressed in `self.input_entry`. Prevent
        user from deleting input that has already been processed."""

        if event.char in ASCII_PRINTABLE:
            if self.insert_entry_valid('insert'):
                self.input_entry_delete_selected()
                self.insert_entry_char(event.char)
                self.input_entry.see('insert')
            return 'break'
        elif event.keysym == 'BackSpace':
            # If cursor is on or behind the last input, then disallow the backspace.
            # Otherwise, allow for default behaviour.
            if not self.insert_entry_valid('insert-1c'):
                return 'break'
        return None

    def input_entry_paste(self, event):
        """Insert each character in the clipboard one by one.  Prevent
        user from deleting input that has already been processed."""
        if self.insert_entry_valid('insert'):
            self.input_entry_delete_selected()
            for char in self.input_entry.clipboard_get():
                self.insert_entry_char(char)
            self.input_entry.see('insert')
        return 'break'

    def insert_entry_char(self, char):
        """Insert `char`. Replaces whitespace characters with their escape characters. Eg. newline with \\n"""
        self.input_entry.insert('insert', CHARS_TO_ESCAPE.get(char, char))

    def insert_entry_valid(self, index):
        """Return whether it would be valid for a characted to be interted into `self.input_entry` at `index`.
        An insertion is only valid if that index hasn't yet been processed by the interpreter."""
        if not self.interpreter:
            return True
        last_input = self.past_input_spans[-1][1]
        if self.input_entry.compare(index, '<', last_input):
            return False
        selection_range = self.input_entry.tag_ranges('sel')
        if selection_range:
            # Check wether the cursor is within the selection. If it is, then
            # make sure the selection is in front of the last index.
            if self.input_entry.compare('insert', '>=', selection_range[0]) \
                    and self.input_entry.compare('insert', '<=', selection_range[1]) \
                    and self.input_entry.compare(selection_range[0], '<', last_input):
                return False
        return True

    def input_entry_delete_selected(self):
        """If text is selected, then delete it if the cursor is within the selection."""
        selection_range = self.input_entry.tag_ranges('sel')
        if selection_range:
            # Only delete if the cursor is within the current selection.
            if self.input_entry.compare('insert', '>=', selection_range[0]) \
                    and self.input_entry.compare('insert', '<=', selection_range[1]):
                self.input_entry.delete(*selection_range)

    def code_text_input(self, event):
        """When a key is pressed in `self.code_text`. If code is running, then disallow
        the key press. If there is currently an interpreter active, delete it and reset.
        Remove any code tags if there are any (error and highlight)."""
        if self.run_code:
            return 'break'
        if self.interpreter:
            self.commands_frame.stop_command()
            self.reset_all()
        if self.code_tags_to_remove:
            self.remove_code_tags()
            self.commands_frame.remove_error_text()

        # Currently, error text will only be displayed if there are tags to remove.
        # If this changes, use the following command. (I'm not sure how slow it is. Probably test it.)
        # if self.commands_frame.error_text.winfo_ismapped():
        #     self.commands_frame.remove_error_text()
        return None

    def set_breakpoint(self, event):
        """Called if user right clicked on `self.code_text`. Sets a breakpoint
        on the nearest character index if it doesn't have a breakpoint. Otherwise, remove
        the breakpoint. You can only set a breakpoint on a command character (not a comment).

        If there is currently an interpreter running, then also add the index to the current
        breakpoints. Warning: If `self.code_text` can change when the interpreter is active,
        then this part is likely to break."""
        index = self.code_text.index(f'@{event.x},{event.y}')
        char = self.code_text.get(index)

        if char not in self.command_highlights:
            return  # Breakpoints only allowed on command characters

        if 'breakpoint' in self.code_text.tag_names(index):
            self.code_text.tag_remove('breakpoint', index)
            if self.interpreter:
                self.breakpoints.remove(self.index_to_pointer[index])
        else:
            self.code_text.tag_add('breakpoint', index)
            if self.interpreter:
                self.breakpoints.add(self.index_to_pointer[index])

    def reset_past_input_spans(self):
        """Reset `self.past_input_spans` to a `deque([('1.0', '1.0')])`."""
        self.past_input_spans = deque([('1.0', '1.0')])

    def reset_hightlights(self):
        """Removes all highlighting from `self.input_entry` and `self.code_text`."""
        self.input_entry.tag_remove('highlight', '1.0', 'end')
        self.remove_code_tags()

    def load_program_text(self, code):
        """Writes `code` into `self.code_text`, overwriting everything."""
        self.commands_frame.stop_command()
        self.reset_all()
        self.code_text.delete('1.0', 'end')
        self.code_text.edit_reset()
        self.code_text.insert('1.0', code)

    def parse_code_text(self):
        """Need to think of a better name for this.
        Creates dicts `self.pointer_to_index` and `self.index_to_poitner` of
        all pointer to text index pairs and vice-vera. Also stores all breakpoints."""
        self.pointer_to_index = {}
        self.index_to_pointer = {}
        self.breakpoints = set()
        text = self.get_program_text()
        pointer = 0
        index = '1.0'
        for char in text:
            self.pointer_to_index[pointer] = index
            self.index_to_pointer[index] = pointer
            if 'breakpoint' in self.code_text.tag_names(index):
                self.breakpoints.add(pointer)
            pointer += 1
            index = self.code_text.index(f'{index}+1c')


def main():
    root = tk.Tk()
    root.geometry('1280x720')
    root.minsize(690, 570)

    Brainfuck(root)

    root.mainloop()


if __name__ == '__main__':
    main()


"""
TODO:
    - Star if modifed and not saved

    - Return key indents to the same level as the previous indentation - Done :)
    - BS key removes indentation level - Done :)

    - Tab, Return, etc. takes priority ahead of Key so Error highlighting is not reset if those keys are pressed
        Maybe could bind to <Modified> instead.  - Done :)

    - Stop at breakpoints when jumping backwards too.  - Done :)

    - If you jump to end of program, then jump to start, the location of the first character creeps upwards.
        This only happens on some programs. Eg, my Ceaser Cipher. Reason found: Its because of comment at end. Fixed now :)
"""
