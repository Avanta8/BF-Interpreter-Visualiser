import tkinter as tk
from user_interface import Brainfuck
from menu import MenuBar


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry('1280x720')
        self.minsize(690, 570)

        self.menubar = MenuBar(self)
        self.config(menu=self.menubar)

    def run(self):
        Brainfuck(self)

        self.mainloop()


def main():
    root = App()
    root.run()


if __name__ == '__main__':
    main()
