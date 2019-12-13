import os
import tkinter as tk
from tkinter import filedialog


class MenuBar(tk.Menu):
    """Frame for file handling. Contains 4 buttons: New, Open, Save, Save As."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.create_menus()

        # Only an interpreter frame should set this to a value other than None
        self.active_frame = None
        self.file_types = (('Brainfuck (*.b)', '*.b'), ('All Files', '*.*'))
        self.current_filename = ''
        self.modified = False

    def create_menus(self):
        """4 buttons: New, Open, Save, Save As."""

        filemenu = tk.Menu(self, tearoff=0)
        filemenu.add_command(label='New', command=self.file_new, accelerator='Ctrl+N')
        filemenu.add_command(label='Open', command=self.file_open, accelerator='Ctrl+O')
        filemenu.add_command(label='Save', command=self.file_save, accelerator='Ctrl+S')
        filemenu.add_command(label='Save As', command=self.file_saveas, accelerator='Ctrl+Shift+S')

        self.master.bind('<Control-n>', lambda e: self.file_new())
        self.master.bind('<Control-o>', lambda e: self.file_open())
        self.master.bind('<Control-s>', lambda e: self.file_save())
        self.master.bind('<Control-Shift-S>', lambda e: self.file_saveas())

        self.add_cascade(label='File', menu=filemenu)

    def file_command(self, func):
        if not self.active_frame:
            return
        if not self.active_frame.modify_allowed():
            return
        func()

    def file_new(self):
        """Create a new blank file."""
        self.file_command(self._file_new)

    def file_open(self):
        """Open the selected file. If no file is selected, then do nothing."""
        self.file_command(self._file_open)

    def file_save(self):
        """Save the current file. If the file has not previously been saved,
        then have the save functionality as save as."""
        self.file_command(self._file_save)

    def file_saveas(self):
        """Save the file as a new filename. If no filename is selected, then do nothing."""
        self.file_command(self._file_saveas)

    def _file_new(self):
        """Create a new blank file."""
        self.active_frame.load_program_text('')
        self.current_filename = ''
        self._rename_window()

    def _file_open(self):
        filename = filedialog.askopenfilename(filetypes=self.file_types)
        if not filename:
            return

        read = self._read_file(filename)
        self.active_frame.load_program_text(read)
        self.current_filename = filename
        self._rename_window()

    def _file_save(self):
        if not self.current_filename:
            self.file_saveas()
            return

        self._write_file(self.current_filename)
        self.active_frame.code_text.edit_modified(False)
        self._rename_window()

    def _file_saveas(self):
        filename = filedialog.asksaveasfilename(
            filetypes=self.file_types, defaultextension='.*')
        if not filename:
            return

        self._write_file(filename)
        self.active_frame.code_text.edit_modified(False)
        self.current_filename = filename
        self._rename_window()

    def _read_file(self, filename):
        """Read `filename` and return the contents."""
        with open(filename, 'r') as file:
            read = file.read()
        return read

    def _write_file(self, filename):
        """Get the program text and write that to `filename`."""
        program_text = self.active_frame.get_program_text()
        with open(filename, 'w') as file:
            file.write(program_text)

    def _rename_window(self):
        """Rename the root window based on the current file."""
        filename = f'{os.path.basename(self.current_filename)} - BF' if self.current_filename else 'BF'
        modified = f'{"* " if self.modified else ""}'
        title = f'{modified}{filename}'
        self.master.wm_title(title)

    def set_modified(self, value):
        """If self.modified != value, then set it to `value` and rename the window."""
        if self.modified == value:
            return

        self.modified = value
        self._rename_window()

    def set_active_frame(self, frame):
        """Method called when the current main active frame changes."""
        self.active_frame = frame
        self.file_new()
