import tkinter as tk
from texts import TagText, InputText
from utility_widgets import ResizeFrame, ScrollTextFrame, TextLineNumbers


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

        self.text.bind('<Tab>', lambda e: self.binding_event(self.add_tab))
        self.text.bind('<Shift-Tab>', lambda e: self.binding_event(self.remove_tab))
        self.text.bind('<Return>', lambda e: self.binding_event(self.return_key))
        self.text.bind('<BackSpace>', lambda e: self.binding_event(self.backspace_key))
        self.text.bind('<space>', lambda e: self.binding_event(self.space_key))

        self.code_line_numbers = TextLineNumbers(
            self, textwidget=self.text, width=30)

    def grid_widgets(self):
        super().grid_widgets(base_row=0, base_column=1)

        self.code_line_numbers.grid(row=0, column=0, sticky='nesw')

    def add_tab(self):
        self.text.edit_separator()
        selected = self.text.get_selected()
        if not selected:
            self.text.insert('insert', '    ')
        else:
            # First line of selection
            start = self.text.index_line(selected[0].string)
            # Last line of selection
            end = self.text.index_line(selected[1].string)
            for line in range(start, end + 1):
                # Insert 4 spaces at the start of every selected line
                self.text.insert(f'{line}.0', '    ')

            # Inserting breaks the selection so fix the selection
            self.text.tag_remove('sel', '1.0')
            self.text.tag_add('sel', f'{selected[0]}+4c', f'{selected[1]}+4c')
        return 'break'

    def remove_tab(self):
        self.text.edit_separator()
        selected = self.text.get_selected()
        if selected:
            # First line of selection
            start = self.text.index_line(selected[0].string)
            # Last line of selection
            end = self.text.index_line(selected[1].string)
        else:
            # If nothing is selected, then the first and last line of the selection
            # is the current line
            start = end = self.text.index_line('insert')

        for line in range(start, end + 1):
            index = self._search_spaces(line)
            col = self.text.index_col(index)
            self.text.delete(f'{line}.0', f'{line}.{min(col, 4)}')

        # This method seems to work without having to replace the current selection.
        # However, if it breaks, remove and add the selected tag like in `self.add_tag`
        return 'break'

    def return_key(self):
        self.text.edit_separator()

        self.text.delete_selected()

        insert = self.text.index('insert')

        # Find the amount of spaces at the start of the line
        line = self.text.index_line(insert)
        index = self._search_spaces(line, end='insert')
        spaces = self.text.index_col(index)

        # Now insert newline along with the required amount of spaces
        self.text.insert(insert, '\n' + ' ' * spaces)
        return 'break'

    def backspace_key(self):

        # Allow for default behaviour if anything is selected
        if self.text.get_selected():
            return None

        insert = self.text.index('insert')
        line, col = self.text.index_linecol(insert)
        index = self._search_spaces(line, end='insert')

        # Allow for default behaviour if cursor is at the start of the
        # line or if there are non-whitespace characters between the start
        # of the line and the current cursor.
        if col == 0 or insert != index:
            return None

        spaces = self.text.index_col(index)
        to_delete = spaces % 4 or 4
        self.text.delete(f'{line}.0', f'{line}.{to_delete}')
        return 'break'

    def space_key(self):
        self.text.edit_separator()

    def binding_event(self, func):
        ret_val = self.master.code_text_input()
        if ret_val == 'break':
            # We don't want to keep running if 'break' was returned from
            # the main <key> function
            return 'break'
        return func()

    def _search_spaces(self, line, end=None):
        """Searches for the first non-space character in `line` up to `end`. Search stops at
        last character in line if `end` is not given."""
        linestart = f'{line}.0'
        lineend = self.text.index(end if end else f'{linestart} lineend')
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
        self.create_zero_heading()

        self.bind('<Configure>', lambda e: (self.update_idletasks(), self.resize_canvas()))

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

        self.frame.columnconfigure(0, weight=1)

    def create_zero_heading(self):
        """Create the empty cell at the start of the headings.
        This cell should never be used. It's just to make the columns fit nicely."""
        zero_heading = next(self.iter_column_headings())
        zero_heading.config(state='disabled')
        zero_heading.grid(row=0, column=0, sticky='nsew')
        self.column_headings.pop()

        for x in range(21):  # Max columns should be 20. Update this value if that changes
            self.column_heading_frame.grid_columnconfigure(x, weight=1)
            self.frame.columnconfigure(x, weight=1)

    def reset(self):
        for widget in self.cells + self.row_headings + self.column_headings:
            widget.destroy()
        self.cells = []
        self.row_headings = []
        self.column_headings = []

        for _ in range(20):
            self.add_cell()

        self.last_tape_length = 0
        self.last_rows = 0
        self.last_columns = 0
        self.last_cell_ind = 0
        self.resize_canvas()

        self.canvas.yview_moveto(0)

    def init_tape(self):
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

        # We don't need to replace earlier cells if the positions of them haven't changed
        start = 0 if self.tape_length == self.last_tape_length else self.last_tape_length
        self.place_cells(columns, start)

        self.last_tape_length = self.tape_length
        self.last_rows = rows
        self.last_columns = columns

    def place_cells(self, columns, start=0):
        for i in range(start, len(self.cells)):
            row, column = divmod(i, columns)
            self.place_cell(self.cells[i], row, column)

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

    def resize_canvas(self):
        self.init_tape()
        self.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.itemconfig(
            self.canvas_frame, width=self.canvas.winfo_width())

    def set_cell(self, cell_ind, value, to_update=True):
        try:
            cell = self.cells[cell_ind]
        except IndexError:
            cell = self.add_cell()
            if to_update:
                self.resize_canvas()

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
        self.resize_canvas()

    def scroll_to_current(self):
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

    @property
    def tape_length(self):
        """Total number of cells."""
        return len(self.cells)


class CommandsFrame(ResizeFrame):
    """Frame containing interpreter commands: run, step, stop, pause, back, jump.
    Also contains settings: runspeed. Also contains input and output."""

    def __init__(self, *args, max_jump=1_000_000, **kwargs):
        super().__init__(*args, **kwargs)

        self.max_jump = max_jump
        self.create_widgets()

        self.bind('<Configure>', lambda x: self.configure_buttons())
        self.current_after = None

    def create_widgets(self):
        input_frame = ResizeFrame(self, 0, 0, 1, .15)
        input_label = tk.Label(input_frame, text='Input:', width=10)
        input_entry_frame = ScrollTextFrame(input_frame, vsb=False,
                                            text_widget_type=InputText,
                                            text_kwargs={'wrap': 'none'})
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

    def command_handle(self, func):
        self.clear_buttons()
        self.remove_error_text()
        func()

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
        self.command_handle(self._run)

    def step_command(self):
        self.command_handle(self._step)

    def pause_command(self):
        self.command_handle(self._pause)

    def stop_command(self):
        self.command_handle(self._stop)

    def back_command(self):
        self.command_handle(self._back)

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
        minsize = self.winfo_width() * .85 / 4
        for i in range(4):
            self.buttons_frame.columnconfigure(i, weight=1, minsize=minsize)

    def get_input_options(self):
        return self.input_entry, self.output_text, self.speed_scale, self.speed_fast_mode

    def update_instruction_counter(self, instruction_count):
        self.instruction_counter_text.set(
            f'Current Instruction: {instruction_count:,}')

    def remove_error_text(self):
        self.current_after = None
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

    def timed_error_text(self, text, time=1000):
        if self.current_after:
            self.after_cancel(self.current_after)
        self.display_error_text(text)
        self.current_after = self.after(1000, self.remove_error_text)
