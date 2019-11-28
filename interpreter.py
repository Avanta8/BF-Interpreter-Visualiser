from collections import deque


class BFInterpreter:

    def __init__(self, code, input_func=input, maxlen=None):
        self.code = code
        self.input_func = input_func
        self.brackets = self.match_brackets(code)
        self.tape = [0]
        self.tape_pointer = 0
        self.code_pointer = -1
        self.output = ''
        self.instruction_count = 0
        self.past = deque(maxlen=maxlen)
        self.commands = {
            '[': self.open_loop,
            ']': self.close_loop,
            '>': self.increment_pointer,
            '<': self.decrement_pointer,
            '+': self.increment_cell,
            '-': self.decrement_cell,
            ',': self.accept_input,
            '.': self.add_output
        }

    def step(self):
        if self.code_pointer + 1 >= len(self.code):
            raise ExecutionEndedError

        self.past.append((self.code_pointer, self.tape_pointer,
                          self.tape[self.tape_pointer], self.output))

        self.code_pointer += 1
        try:
            while self.current_instruction not in self.commands:
                self.code_pointer += 1
        except IndexError:
            raise ExecutionEndedError

        code_pointer = self.code_pointer
        self.commands[self.current_instruction]()

        return code_pointer

    def run(self):
        while True:
            try:
                self.step()
            except ExecutionEndedError:
                break
        return self.output

    def open_loop(self):
        if self.current_cell == 0:
            self.code_pointer = self.brackets[self.code_pointer]

    def close_loop(self):
        if self.current_cell != 0:
            self.code_pointer = self.brackets[self.code_pointer]

    def increment_pointer(self):
        self.tape_pointer += 1
        if self.tape_pointer >= len(self.tape):
            self.tape.append(0)

    def decrement_pointer(self):
        self.tape_pointer -= 1

    def increment_cell(self):
        self.tape[self.tape_pointer] = (self.tape[self.tape_pointer] + 1) % 256

    def decrement_cell(self):
        self.tape[self.tape_pointer] = (self.tape[self.tape_pointer] - 1) % 256

    def accept_input(self):
        input_ = self.input_func()
        self.tape[self.tape_pointer] = ord(input_)

    def add_output(self):
        self.output += chr(self.current_cell)

    def back(self):
        try:
            self.code_pointer, self.tape_pointer, tape_val, self.output = self.past.pop()
        except IndexError:
            raise NoPreviousExecutionError
        self.tape[self.tape_pointer] = tape_val
        return self.code_pointer

    @property
    def current_cell(self):
        return self.tape[self.tape_pointer]

    @property
    def current_instruction(self):
        return self.code[self.code_pointer]

    @staticmethod
    def match_brackets(code):
        stack = deque()
        brackets = {}
        for i, char in enumerate(code):
            if char == '[':
                stack.append(i)
            elif char == ']':
                match = stack.pop()
                brackets[match] = i
                brackets[i] = match
        return brackets


class ExecutionEndedError(Exception):
    """Error raised when program has ended but `Interpreter.step` is still called"""

class NoPreviousExecutionError(Exception):
    """Error raised when `Interpreter.back` is called but it is the first instruction being processed"""

def main():
    quine = """
Written by Erik Bosman
->++>+++>+>+>++>>+>+>+++>>+>+>++>+++>+++>+>>>>>>>>>>
>>>>>>>>>>>>>>>>>>>>>>>+>+>++>>>+++>>>>>+++>+>>>>>>>
>>>>>>>>>>>>>>>+++>>>>>>>++>+++>+++>+>>+++>+++>+>+++
>+>+++>+>++>+++>>>+>+>+>+>++>+++>+>+>>+++>>>>>>>+>+>
>>+>+>++>+++>+++>+>>+++>+++>+>+++>+>++>+++>++>>+>+>+
+>+++>+>+>>+++>>>+++>+>>>++>+++>+++>+>>+++>>>+++>+>+
++>+>>+++>>+++>>+[[>>+[>]+>+[<]<-]>>[>]<+<+++[<]<<+]
>>>[>]+++[++++++++++>++[-<++++++++++++++++>]<.<-<]
"""
    # interpreter = BFInterpreter(quine)

    squares = """
      ++++[>+++++<-]>[<+++++>-]+<+[
    >[>+>+<<-]++>>[<<+>>-]>>>[-]++>[-]+
    >>>+[[-]++++++>>>]<<<[[<++++++++<++>>-]+<.<[>----<-]<]
    <<[>>>>>[>>>[-]+++++++++<[>-<-]+++++++++>[-[<->-]+[<<<]]<[>+<-]>]<<-]<<-
]
[Outputs square numbers from 0 to 10000.
Daniel B Cristofani (cristofdathevanetdotcom)
http://www.hevanet.com/cristofd/brainfuck/]
"""

    interpreter = BFInterpreter(squares)
    print(interpreter.run())

if __name__ == '__main__':
    main()