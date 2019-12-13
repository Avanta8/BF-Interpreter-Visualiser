import tkinter as tk


class InputText(tk.Text):
    """Text class where the user could type in."""

    def get_selected(self):
        """Return the first and last index of the currently selected
        text if there is any, otherwise None"""
        return self.tag_ranges('sel') or None

    def within_selected(self, index='insert'):
        """Return True/False whether `index` is within the currently selected text.
        If no text is selected, then return None."""
        selected = self.get_selected()
        if not selected:
            return None

        index = self.index(index)

        return self.compare(index, '>=', selected[0]) \
            and self.compare(index, '<=', selected[1])

    def delete_selected(self, insert_only=True):
        """If any text is selected, then delete that selection if the cursor is within it.
        If `insert_only` is False, then delete even if the cursor is not within the selection.
        If no text is selected, then do nothing."""
        if not insert_only or self.within_selected():
            selected = self.get_selected()
            if selected is not None:
                self.delete(*selected)

    def index_linecol(self, index):
        """Return the line and column of `index` as integers."""
        return tuple(map(int, self.index(index).split('.')))

    def index_line(self, index):
        """Return the line of `index` as an integer."""
        return int(self.index(index).split('.')[0])

    def index_col(self, index):
        """Return the line of `index` as an integer."""
        return int(self.index(index).split('.')[1])


class TagText(InputText):
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
