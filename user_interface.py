import codecs
import re
import tkinter as tk
from collections import deque
from interpreter import BFInterpreter, ExecutionEndedError, NoPreviousExecutionError


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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_scrollbars()

    def create_scrollbars(self):
        self.vsb = tk.Scrollbar(
            self.master, orient="vertical", command=self.yview)
        self.hsb = tk.Scrollbar(
            self.master, orient="horizontal", command=self.xview)
        self.configure(yscrollcommand=self.vsb.set)
        self.configure(xscrollcommand=self.hsb.set)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()

    def create_widgets(self):
        self.text = ScrollbarText(self, wrap='none')

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.text.grid(row=0, column=0, sticky='nesw')
        self.text.vsb.grid(row=0, column=1, sticky='nesw')
        self.text.hsb.grid(row=1, column=0, sticky='nesw')


class CodeFrame(ResizeFrame, ScrollTextFrame):
    def create_widgets(self):
        self.text = ScrollbarText(self, wrap='none')
        self.text.tag_configure('highlight', background='grey')
        self.text.bind('<Tab>', self.tab_to_spaces)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        code_line_numbers = TextLineNumbers(
            self, textwidget=self.text, width=30)

        self.text.grid(row=0, column=1, sticky='nesw')
        code_line_numbers.grid(row=0, column=0, sticky='nesw')
        self.text.vsb.grid(row=0, column=2, sticky='nesw')
        self.text.hsb.grid(row=1, column=1, sticky='nesw')

    def tab_to_spaces(self, event):
        self.text.insert('insert', '    ')
        return 'break'


class TapeFrame(ResizeFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cells = []
        self.headings = []
        self.create_frame()
        self.reset()

    def create_frame(self):
        self.canvas = tk.Canvas(self)
        self.frame = tk.Frame(self.canvas)
        self.vsb = tk.Scrollbar(self, orient="vertical",
                                command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_frame = self.canvas.create_window(
            0, 0, window=self.frame, anchor="nw")

    def reset(self):
        for cell in self.cells:
            cell.destroy()
        self.cells = []
        for _ in range(20):
            self.add_cell()

        for heading in self.headings:
            heading.destroy()
        self.headings = []

        self.last_tape_length = None
        self.last_rows = None
        self.last_columns = None
        self.last_ind = 0
        self.init_tape()

    def init_tape(self):
        self.resize_canvas()
        columns = self.winfo_width() // 50
        if columns == 0:
            return
        rows = self.tape_length // columns + 1

        if self.last_tape_length == self.tape_length and self.last_rows == rows and self.last_columns == columns:
            return

        if not (self.last_columns == columns and self.last_rows == rows):
            self.create_all_headings(rows, columns)
        self.place_all_cells(columns)

        for i in range(columns + 1):
            self.frame.columnconfigure(i, weight=1)

        self.last_tape_length = self.tape_length
        self.last_rows = rows
        self.last_columns = columns

    def place_all_cells(self, columns):
        for i, cell in enumerate(self.cells):
            row, column = divmod(i, columns)
            self.place_cell(cell, row, column)

    def place_cell(self, cell, row, column):
        cell.grid(row=row + 1, column=column + 1, sticky='nsew')

    def create_all_headings(self, rows, columns):
        positions = [{'row': 0, 'column': x + 1} for x in range(columns)] \
            + [{'row': y + 1, 'column': 0} for y in range(rows)]

        headings = self.iter_headings()

        for last, (pos, heading) in enumerate(zip(positions, headings)):
            self.display_heading(heading, **pos, column_count=columns)
        for heading in self.headings[last + 1:]:
            heading.grid_forget()

    def display_heading(self, heading, row, column, column_count):
        heading.grid(row=row, column=column)
        heading.config(state='normal')
        heading.delete(0, 'end')
        heading.insert(0, column - 1 if row == 0 else row * column_count)
        heading.config(state='disabled')

    def create_heading(self):
        heading = tk.Entry(self.frame)
        heading.config(disabledbackground='grey',
                       disabledforeground='black')
        self.headings.append(heading)
        return heading

    def resize(self, *args):
        super().resize()
        self.init_tape()

    def resize_canvas(self, *args):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.itemconfig(
            self.canvas_frame, width=self.canvas.winfo_width())

    def set_cell(self, cell_ind, value):
        # print(cell_ind, value)
        try:
            cell = self.cells[cell_ind]
        except IndexError:
            cell = self.add_cell()
            self.init_tape()
        last_cell = self.cells[self.last_ind]

        last_cell.config(disabledbackground='white')

        cell.config(state='normal')
        cell.delete(0, 'end')
        cell.insert(0, value)
        cell.config(state='disabled', disabledbackground='red')

        self.last_ind = cell_ind

    def add_cell(self):
        cell = tk.Entry(self.frame)
        cell.insert(0, 0)
        cell.config(state='disabled', disabledbackground='white',
                    disabledforeground='black')
        self.cells.append(cell)
        return cell

    def update_cells(self, cell_vals):
        for i, val in enumerate(cell_vals):
            self.set_cell(i, val)

    def iter_headings(self):
        for heading in self.headings:
            yield heading
        while True:
            heading = self.create_heading()
            yield heading

    @property
    def tape_length(self):
        return len(self.cells)


class CommandsFrame(ResizeFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_widgets()
        self.stop_command()

    def create_widgets(self):

        self.buttons_frame = ResizeFrame(self, 0, .3, .85, .15)
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
        input_frame = ResizeFrame(self, 0, 0, 1, .1)
        input_label = tk.Label(input_frame, text='Input:', width=10)
        input_entry = tk.Text(input_frame, height=1, wrap='none')
        input_entry.tag_configure('highlight', background='grey')
        input_label.pack(side='left')
        input_entry.pack(side='left', fill='x', expand=True)

        scale_frame = ResizeFrame(self, 0, .1, .85, .2)
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

        output_frame = ResizeFrame(self, 0, .45, .9, .55)
        output_label = tk.Label(output_frame, text='Output:', width=10)
        output_text_frame = ScrollTextFrame(output_frame)
        output_text = output_text_frame.text
        output_text.configure(state='disabled')
        output_label.pack()
        output_text_frame.pack(fill='both', expand=True)

        jump_frame = ResizeFrame(self, .86, .09, .14, .41)
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
    def __init__(self, master):
        super().__init__(master)

        self.interpreter = None

        self.pack(fill='both', expand=True)
        self.createWidgets()
        self.bind("<Configure>", self.resize)

        self.set_runspeed()
        self.resize()

        self.stop()

    def createWidgets(self):
        code_text_frame = CodeFrame(self, .02, .1, .5, .88)
        self.code_text = code_text_frame.text

        self.tape_frame = TapeFrame(self, .54, .1, .44, .35)

        self.commands_frame = CommandsFrame(self, .54, .5, .44, .48)
        self.input_entry, self.output_text, self.speed_scale, self.fast_mode = self.commands_frame.set_input_options()
        self.input_entry.bind('<Key>', self.input_entry_input)

        self.main_frames = [code_text_frame,
                            self.tape_frame, self.commands_frame]

    def resize(self, *args):
        self.update()
        for frame in self.main_frames:
            frame.resize()

    def init_interpreter(self):
        self.code = self.get_code()
        self.input_ = self.get_input()
        self.reset_past_input_spans()
        self.interpreter = BFInterpreter(self.code, self.next_input)
        self.tape_frame.reset()
        self.reset_output()

    def step(self, display=True):
        if self.interpreter is None:
            self.init_interpreter()

        try:
            self.code_pointer = self.interpreter.step()
        except ExecutionEndedError:
            self.commands_frame.pause_command()
            return False
        if display:
            self.configure_current()
        return True

    def run(self):
        if self.interpreter is None:
            self.init_interpreter()
        self.run_code = True
        self.run_steps()

    def run_steps(self):
        if not self.run_code:
            return
        self.step()
        self.after(self.runspeed, self.run_steps)

    def stop(self):
        self.interpreter = None
        self.run_code = False
        self.last_pointer = 0
        self.reset_past_input_spans()
        try:
            self.reset_hightlights()
        except AttributeError:
            # This is because CommandsFrame calls master.stop() when initialised. Should refactor this in the future
            pass

    def pause(self):
        self.run_code = False

    def back(self, display=True):
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
        method = self.step if steps > 0 else self.back

        for _ in range(abs(steps)):
            if not method(False):
                break

        self.tape_frame.update_cells(self.interpreter.tape)
        self.configure_current()

    def configure_current(self):
        self.highlight_cell()
        self.configure_output()
        self.hightlight_text()

    def hightlight_text(self):
        self.code_text.tag_remove(
            'highlight', f'1.0+{self.last_pointer}c', f'1.0+{self.last_pointer + 1}c')
        self.code_text.tag_add('highlight', f'1.0+{self.code_pointer}c')
        self.last_pointer = self.code_pointer

    def highlight_cell(self):
        self.tape_frame.set_cell(
            self.interpreter.tape_pointer, self.interpreter.current_cell)

    def configure_output(self):
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
        self.output_text.configure(state='normal')
        self.output_text.delete('1.0', 'end')
        self.output_text.configure(state='disabled')

    def set_runspeed(self, *args):
        speed_scale = self.speed_scale.get()
        fast_mode = self.fast_mode.get()
        runspeed = (110 - speed_scale) // 10 if fast_mode \
            else int(1000 / (speed_scale * speed_scale * .0098 + 1))
        self.runspeed = runspeed

    def get_code(self):
        code = self.code_text.get('1.0', 'end-1c')
        return code

    def get_input(self):
        input_ = self.input_entry.get('1.0', 'end-1c')
        return input_

    def next_input(self):
        last_input_span = self.past_input_spans[-1]

        match_obj = re.match(
            r'^(\\(?:n|r|t|\\|\d{1,3})|.)', self.get_input()[last_input_span[1]:])
        match = match_obj[0]
        if len(match) > 1:
            if match[1].isdecimal():
                match = chr(int(match[1:]))
            else:
                match = codecs.decode(match, 'unicode_escape')

        new_input_span = (last_input_span[1] + match_obj.start(),
                          last_input_span[1] + match_obj.end())

        self.highlight_input(last_input_span, new_input_span)
        self.past_input_spans.append(new_input_span)

        return match

    def highlight_input(self, last_input_span, new_input_span):
        self.input_entry.tag_remove(
            'highlight', f'1.{last_input_span[0]}', f'1.{last_input_span[1]}')
        self.input_entry.tag_add(
            'highlight', f'1.{new_input_span[0]}', f'1.{new_input_span[1]}')

    def input_entry_input(self, event):
        cursor_position = int(self.input_entry.index('insert')[2:])
        last_input = self.past_input_spans[-1][1]
        if event.keysym == 'BackSpace' and cursor_position <= last_input \
                or cursor_position < last_input:
            return 'break'

    def reset_past_input_spans(self):
        self.past_input_spans = deque([(0, 0)])

    def reset_hightlights(self):
        self.input_entry.tag_remove('highlight', '1.0', 'end')
        self.code_text.tag_remove('highlight', '1.0', 'end')


def main():
    # root = App()
    root = tk.Tk()
    root.wm_title('BF Interpreter')
    root.geometry('1280x720')

    App(root)

    root.mainloop()


if __name__ == '__main__':
    main()
