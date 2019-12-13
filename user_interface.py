import codecs
from collections import deque
import functools
import itertools
import re
import string
import tkinter as tk

from interpreter import (BFInterpreter,
                         ExecutionEndedError,
                         NoPreviousExecutionError,
                         NoInputError,
                         ProgramSyntaxError,
                         ProgramRuntimeError,
                         ErrorTypes)
from main_frames import CodeFrame, TapeFrame, CommandsFrame


ASCII_PRINTABLE = set(string.printable)
CHARS_TO_ESCAPE = {
    '\n': r'\n',
    '\t': r'\t',
    '\r': r'\r'
}


class Brainfuck(tk.Frame):
    """Main frame for the interpreter. Everyting goes in here"""

    def __init__(self, master):
        """Create all widgets. Reset everything."""
        super().__init__(master)

        self.code_tags_to_remove = []

        self.pack(fill='both', expand=True)
        self.create_widgets()

        self.set_runspeed()

        self.reset_all()

        self.menubar = self.master.menubar
        self.menubar.set_active_frame(self)

    def create_widgets(self):
        """Create the 3 main frames that go in the interpreter.

        Main frames:
            code_text_frame -- Where the user types the code to be interpreted,
            tape_frame -- The frame where the cells of the tape are displayed,
            commands_frame -- The commands for the interpreter eg. run, step, change
                              speed etc. Also where input / output is."""

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

        self.code_text_frame = CodeFrame(self, .02, .1, .5, .88,
                                         text_kwargs={
                                             'undo': True,
                                             'wrap': 'none',
                                             'tag_func': tag_func,
                                             # 'font': ('Consolas', 10)
                                         })
        self.code_text = self.code_text_frame.text
        self.code_text.bind('<Key>', self.code_text_input)
        self.code_text.bind('<Button-3>', self.set_breakpoint)  # rmb
        self.code_text.bind('<<Modified>>', self.code_text_modified)
        for tag, colour in ('comment', 'grey'), ('loop', 'red'), ('io', 'blue'), ('pointer', 'purple'), ('cell', 'green'):
            self.code_text.tag_configure(tag, foreground=colour)

        # Create tape frame
        self.tape_frame = TapeFrame(self, .54, .1, .44, .3)

        # Create commands frame
        self.commands_frame = CommandsFrame(self, .54, .42, .44, .56)
        self.input_entry, self.output_text, self.speed_scale, self.fast_mode = self.commands_frame.get_input_options()
        self.input_entry.bind('<Control-v>', self.input_entry_paste)
        self.input_entry.bind('<Key>', self.input_entry_input)

        self.main_frames = [self.code_text_frame,
                            self.tape_frame, self.commands_frame]

    def init_interpreter(self):
        """Reset output text and previous interpreter settings. Then initialise
        a new `self.interpreter`. Program text is gotten again. Return True if
        initislising new interpreter was successful else False."""
        self.reset_all()

        self.parse_code_text()
        try:
            self.interpreter = BFInterpreter(
                self.get_program_text(),
                input_func=self.get_next_input_char,
                output_func=self.configure_output)
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
        self.run_code = False

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

    def configure_output(self, output):
        """Make sure the output is correct. If the current output is too short, add
        the missing characters to the end. If the current output is too long, delete
        the extra characters"""
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
        last_end = self.past_input_spans[-1][1]

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
                self.input_entry.delete_selected()
                self.insert_entry_char(event.char)
                self.input_entry.see('insert')
            return 'break'
        elif event.keysym == 'BackSpace':
            # If cursor is on or behind the last input, then disallow the backspace.
            # Otherwise, allow for default behaviour.
            if not self.insert_entry_valid('insert-1c'):
                return 'break'
        elif event.keysym == 'Delete':
            # Delete key (the one above backspace)
            if not self.insert_entry_valid('insert'):
                return 'break'
        return None

    def input_entry_paste(self, event):
        """Insert each character in the clipboard one by one.  Prevent
        user from deleting input that has already been processed."""
        if self.insert_entry_valid('insert'):
            self.input_entry.delete_selected()
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

        if self.input_entry.within_selected():
            # If text is selected and the cursor is within the current selection,
            # then make the comparison index the start of the current selection
            index = self.input_entry.get_selected()[0]

        if self.input_entry.compare(index, '<', last_input):
            return False
        return True

    def code_text_input(self, *event):
        """When a key is pressed in `self.code_text`. If code is running, then disallow
        the key press. If there is currently an interpreter active, delete it and reset.
        Remove any code tags if there are any (error and highlight)."""
        if not self.modify_allowed():
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

    def code_text_modified(self, event):
        """Method bound to <<Modified>> event on `self.code_text`.
        Call the set_modified method of menubar"""
        self.menubar.set_modified(self.code_text.edit_modified())

    def modify_allowed(self):
        if not self.run_code:
            return True
        self.commands_frame.timed_error_text('Please pause execution first')
        return False

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

        self.code_text.edit_modified(False)

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
        for _ in text:
            self.pointer_to_index[pointer] = index
            self.index_to_pointer[index] = pointer
            if 'breakpoint' in self.code_text.tag_names(index):
                self.breakpoints.add(pointer)
            pointer += 1
            index = self.code_text.index(f'{index}+1c')
