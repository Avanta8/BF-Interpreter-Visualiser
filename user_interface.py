import codecs
import re
import tkinter as tk
from collections import deque
from interpreter import BFInterpreter, ExecutionEndedError, NoPreviousExecutionError, NoInputError


class NoNextInputCharError(Exception):
    """Error raised when there is no next character in input."""


class TextLineNumbers(tk.Canvas):
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

        # Refreshes the canvas widget every 10ms
        self.after(10, self.redraw)


class ScrollbarText(tk.Text):
    def __init__(self, *args, vsb=True, hsb=True, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_scrollbars(vsb, hsb)

    def create_scrollbars(self, vsb, hsb):
        if vsb:
            self.vsb = tk.Scrollbar(
                self.master, orient="vertical", command=self.yview)
            self.configure(yscrollcommand=self.vsb.set)
        else:
            self.vsb = None

        if hsb:
            self.hsb = tk.Scrollbar(
                self.master, orient="horizontal", command=self.xview)
            self.configure(xscrollcommand=self.hsb.set)
        else:
            self.hsb = None


class ResizeFrame(tk.Frame):
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

    def __init__(self, *args, vsb=True, hsb=True, **kwargs):
        super().__init__(*args, **kwargs)

        self.has_vsb = vsb
        self.has_hsb = hsb

        self.create_widgets()
        self.grid_widgets()

    def create_widgets(self):
        self.text = ScrollbarText(
            self, wrap='none', hsb=self.has_hsb, vsb=self.has_vsb, undo=True)

    def grid_widgets(self, *, base_column=0, base_row=0):
        self.grid_rowconfigure(base_row, weight=1)
        self.grid_columnconfigure(base_column, weight=1)

        self.text.grid(row=base_row, column=base_column, sticky='nesw')
        if self.has_vsb:
            self.text.vsb.grid(
                row=base_row, column=base_column + 1, sticky='nesw')
        if self.has_hsb:
            self.text.hsb.grid(
                row=base_row + 1, column=base_column, sticky='nesw')


class CodeFrame(ResizeFrame, ScrollTextFrame):
    def create_widgets(self):
        super().create_widgets()
        self.text.tag_configure('highlight', background='grey')
        self.text.bind('<Tab>', self.tab_to_spaces)

        self.code_line_numbers = TextLineNumbers(
            self, textwidget=self.text, width=30)

    def grid_widgets(self):
        super().grid_widgets(base_row=0, base_column=1)

        self.code_line_numbers.grid(row=0, column=0, sticky='nesw')

    def tab_to_spaces(self, event):
        self.text.insert('insert', '    ')
        return 'break'


class TapeFrame(ResizeFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        """
        NOTE:
            The code to create headings is hacky AF.
            Change it ASAP.

        """

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

        # Creates the empty cell at the start of the headings
        zero_heading = next(self.iter_column_headings())
        zero_heading.config(state='disabled')
        zero_heading.grid(row=0, column=0, sticky='nsew')
        self.column_headings.pop()
        self.column_heading_frame.columnconfigure(0, weight=1)

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

        rows = self.tape_length // columns + \
            (1 if self.tape_length % columns else 0)

        if self.last_tape_length == self.tape_length and self.last_rows == rows and self.last_columns == columns:
            return

        if not (self.last_columns == columns and self.last_rows == rows):
            self.create_all_headings(rows, columns)
        self.place_all_cells(columns)

        self.last_tape_length = self.tape_length
        self.last_rows = rows
        self.last_columns = columns

        self.update()

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
            self.column_heading_frame.grid_columnconfigure(x + 1, weight=1)
            self.frame.columnconfigure(x + 1, weight=1)
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.stop_command()

    def create_widgets(self):

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

        self.frames = [self.buttons_frame]

    def set_input_options(self):
        input_frame = ResizeFrame(self, 0, 0, 1, .15)
        input_label = tk.Label(input_frame, text='Input:', width=10)
        input_entry_frame = ScrollTextFrame(input_frame, vsb=False)
        input_entry = input_entry_frame.text
        input_entry.config(height=1)
        input_entry.tag_configure('highlight', background='grey')
        input_label.pack(side='left')
        input_entry_frame.pack(side='left')

        scale_frame = ResizeFrame(self, 0, .15, .85, .2)
        speed_scale = tk.Scale(scale_frame, from_=1, to=100,
                               orient='horizontal', command=self.master.set_runspeed)
        speed_label = tk.Label(scale_frame, text='Speed:', width=10)
        speed_fast_mode = tk.IntVar()
        speed_checkbutton = tk.Checkbutton(scale_frame, text='faster',
                                           variable=speed_fast_mode,
                                           command=self.master.set_runspeed)
        speed_label.pack(side='left')
        speed_scale.pack(side='left', fill='x', expand=True)
        speed_checkbutton.pack(side='right', padx=(10, 0))

        output_frame = ResizeFrame(self, 0, .5, 1, .5)
        output_label = tk.Label(output_frame, text='Output:', width=10)
        output_text_frame = ScrollTextFrame(output_frame)
        output_text = output_text_frame.text
        output_text.configure(state='disabled')
        output_label.pack()
        output_text_frame.pack(fill='both', expand=True)

        jump_frame = ResizeFrame(self, .86, .15, .14, .4)
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

        self.frames.extend(
            [input_frame, scale_frame, output_frame, jump_frame])

        return input_entry, output_text, speed_scale, speed_fast_mode

    def clear_buttons(self):
        for button in self.buttons:
            button.grid_forget()

    def run_command(self):
        self.clear_buttons()
        self.grid_button(self.stop_button, row=0, column=0)
        self.grid_button(self.pause_button, row=0, column=1)
        self.master.run()

    def step_command(self):
        self.clear_buttons()
        self.grid_button(self.stop_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)
        self.grid_button(self.back_button, row=0, column=2)
        self.grid_button(self.run_button, row=0, column=3)
        self.master.step()

    def pause_command(self):
        self.clear_buttons()
        self.grid_button(self.stop_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)
        self.grid_button(self.back_button, row=0, column=2)
        self.grid_button(self.run_button, row=0, column=3)
        self.master.pause()

    def stop_command(self):
        self.clear_buttons()
        self.grid_button(self.run_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)
        self.master.stop()

    def back_command(self):
        self.clear_buttons()
        self.grid_button(self.stop_button, row=0, column=0)
        self.grid_button(self.step_button, row=0, column=1)
        self.grid_button(self.back_button, row=0, column=2)
        self.grid_button(self.run_button, row=0, column=3)
        self.master.back()

    def jump_command(self, direction):
        self.pause_command()
        self.master.jump(int(self.jump_entry.get()) * direction)

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


class App(tk.Frame):
    """Main frame for the interpreter. Everyting goes in here"""

    def __init__(self, master):
        """Create all widgets. Reset everything."""
        super().__init__(master)

        self.pack(fill='both', expand=True)
        self.create_widgets()
        self.bind('<Configure>', self.resize)

        self.set_runspeed()
        self.resize()

        self.stop()

    def create_widgets(self):
        """Create the 3 main frames that go in the interpreter.
        `code_text_frame` -> Where the user types the code to be interpreted,
        `self.tape_frame` -> The frame where the cells of the tape are displayed,
        `self.commands_frame` -> The commands for the interpreter eg. run, step, change
            speed etc. Also where input / output is."""
        code_text_frame = CodeFrame(self, .02, .1, .5, .88)
        self.code_text = code_text_frame.text

        self.tape_frame = TapeFrame(self, .54, .1, .44, .3)

        self.commands_frame = CommandsFrame(self, .54, .45, .44, .53)
        self.input_entry, self.output_text, self.speed_scale, self.fast_mode = self.commands_frame.set_input_options()
        self.input_entry.bind('<Key>', self.input_entry_input)

        self.main_frames = [code_text_frame,
                            self.tape_frame, self.commands_frame]

    def resize(self, *args):
        """Called when the screen is resized"""
        self.update()
        for frame in self.main_frames:
            frame.resize()

    def init_interpreter(self):
        """Reset output text and previous interpreter settings. Then initialise
        a new `self.interpreter`. Program text is gotten again"""
        self.reset_output()
        self.reset_past_input_spans()
        self.reset_hightlights()
        self.tape_frame.reset()
        self.last_pointer = 0

        self.interpreter = BFInterpreter(self.get_program_text(), self.get_next_input_char)

    def step(self, display=True):
        """Step one instruction. If execution has ended, then commands are paused.
        Change will be displayed if `display` is True. Return True if an
        instruction was executed else False."""
        if not self.interpreter:
            self.init_interpreter()

        try:
            self.code_pointer = self.interpreter.step()
        except ExecutionEndedError:
            # Execution has finised
            self.commands_frame.pause_command()
            return False
        except NoInputError:
            # No input was given (from `self.input_func`)
            self.commands_frame.pause_command()
            return False

        if display:
            self.configure_current()
        return True

    def run(self):
        """Runs instructions until execution is paused or execution has ended."""
        if not self.interpreter:
            self.init_interpreter()
        self.run_code = True
        self.run_steps()

    def run_steps(self):
        if not self.run_code:
            return
        self.step()

        # step again after `self.runspeed` ms
        self.after(self.runspeed, self.run_steps)

    def stop(self):
        """Stop execution. Reset `self.interpreter`."""
        self.interpreter = None
        self.run_code = False

    def pause(self):
        """Pause execution."""
        self.run_code = False

    def back(self, display=True):
        """Step one instruction backwards.
        Change will be displayed if `display` is True. Return True if
        stepping backwards was successful else False (no previous instruction)."""

        # Whether input should be rolled back. However, don't rollback if
        # there is no previous instruction
        rollback_input = self.interpreter.current_instruction == ','

        try:
            self.code_pointer = self.interpreter.back()
        except NoPreviousExecutionError:
            return False

        if rollback_input:
            self.highlight_input(self.past_input_spans.pop(),
                                 self.past_input_spans[-1])
        if display:
            self.configure_current()
        return True

    def jump(self, steps):
        """Jump `steps` number of steps forwards if `steps` is positive else backwards."""
        method = self.step if steps > 0 else self.back

        for _ in range(abs(steps)):
            if not method(False):
                break

        self.tape_frame.update_cells(self.interpreter.tape)
        self.configure_current()

    def configure_current(self):
        """Configures all the necessary output after a command."""
        self.highlight_cell()
        self.configure_output()
        self.hightlight_text()

    def hightlight_text(self):
        """Remove the hightlighting from the previous command and add the new highlighting."""
        self.code_text.tag_remove(
            'highlight', f'1.0+{self.last_pointer}c', f'1.0+{self.last_pointer + 1}c')
        if self.code_pointer >= 0:
            self.code_text.tag_add('highlight', f'1.0+{self.code_pointer}c')
        self.last_pointer = self.code_pointer

    def highlight_cell(self):
        """Highlight the current cell that `self.interpreter.tape_pointer`
        is pointing to."""
        self.tape_frame.set_cell(
            self.interpreter.tape_pointer, self.interpreter.current_cell)

    def configure_output(self):
        """Make sure the output is correct. If the current output is too short, add
        the missing characters to the end. If the current output is too long, delete
        the extra characters."""
        output = self.interpreter.output
        current_output = self.output_text.get('1.0', 'end-1c')

        if len(output) > len(current_output):
            self.output_text.configure(state='normal')
            self.output_text.insert(
                'end', ''.join(output[len(current_output):]))
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
        runspeed = (110 - speed_scale) // 10 if fast_mode \
            else int(1000 / (speed_scale * speed_scale * .0098 + 1))
        self.runspeed = runspeed

    def get_program_text(self):
        """Return the current program text."""
        return self.code_text.get('1.0', 'end-1c')

    def get_input(self):
        """Return the current input"""
        return self.input_entry.get('1.0', 'end-1c')

    def get_next_input_char(self):
        """Return the next character in the input. If there is no next input, return `None`."""
        last_start, last_end = self.past_input_spans[-1]

        # Get the next character of input starting from the end of the last character of input
        match_obj = re.match(
            r'^(\\(?:n|r|t|\\|\d{1,3})|.)', self.get_input()[last_end:])
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

        new_input_span = (last_end + match_obj.start(),
                          last_end + match_obj.end())

        self.highlight_input((last_start, last_end), new_input_span)
        self.past_input_spans.append(new_input_span)

        return match

    def highlight_input(self, last_input_span, new_input_span):
        """Remove the hightlighting from `last_input_span` and add
        highlighting to `new_input_span`."""
        self.input_entry.tag_remove(
            'highlight', f'1.{last_input_span[0]}', f'1.{last_input_span[1]}')
        self.input_entry.tag_add(
            'highlight', f'1.{new_input_span[0]}', f'1.{new_input_span[1]}')

    def input_entry_input(self, event):
        """Event called whenever a key is pressed in `self.input_entry`. Prevent
        user from adding newlines and deleting input that has already been processed.

        NOTE: This doesn't always work:
            1 - The user can enter newlines by pasting.
            2 - The user can delete processed input by creating a selection and
                moving the cursor in front of the last processed character."""

        if event.keysym == 'Return':
            # Newlines are 100% not allowed
            return 'break'
        if not self.interpreter:
            # No other restriction if program hasn't started yet
            return None
        if event.state != 8 and event.char != '\x16':
            # Multiple key commands are always allowed as long as it isn't paste
            return None

        cursor_position = int(self.input_entry.index('insert')[2:])
        last_input = self.past_input_spans[-1][1]

        if event.keysym == 'BackSpace' and cursor_position <= last_input \
                or cursor_position < last_input:
            return 'break'
        return None

    def reset_past_input_spans(self):
        """Reset `self.past_input_spans` to a `deque([(0, 0)])`."""
        self.past_input_spans = deque([(0, 0)])

    def reset_hightlights(self):
        """Removes all highlighting from `self.input_entry` and `self.code_text`."""
        self.input_entry.tag_remove('highlight', '1.0', 'end')
        self.code_text.tag_remove('highlight', '1.0', 'end')


def main():
    # root = App()
    root = tk.Tk()
    root.wm_title('BF Interpreter')
    root.geometry('1280x720')
    root.minsize(690, 570)

    App(root)

    root.mainloop()


if __name__ == '__main__':
    main()
