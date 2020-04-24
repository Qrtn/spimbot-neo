#!/usr/bin/python3

### Movement Pattern
# -360 to 360		absolute angle
# 1500 +- v		velocity
# 2000			UDP, may be contingent on previous check of arena map
# 3000 + (x << 6) + y	Check arena map at x, y and set flag for next UDP
# 10000000 + cm		Set current_move to cm
# 20000000		End program
# 100000000 + c		Delay c cycles

import sys
import math

import replace_line

class Compiler:
    DEFAULT_VELOCITY = 10

    def __init__(self):
        self.instructions = {
            'angle': self.angle,
            'vel': self.velocity,
            'end': self.end,
            #'jump': self.jump, # jump is disabled for now due to difficulty in using it
            'delay': self.delay,
            'go': self.go,
            'goto': self.goto,
            'shoot': self.shoot,
            'shootpos': self.shootpos,
            'hostcheck': self.hostcheck,
            'chkshoot': self.chkshoot,
            'custom_reset': self.custom_reset,
            'setloc': self.set_location
        }

        self.x = 4
        self.y = 4

    def parse(self, command, args):
        int_args = [int(arg) for arg in args]

        return self.instructions[command](*int_args)

    # TODO: Convert all static methods into normal methods
    @staticmethod
    def angle(angle):
        return [int(angle)]

    @staticmethod
    def velocity(velocity=DEFAULT_VELOCITY):
        return [1500 + int(velocity)]

    @staticmethod
    def end():
        return [20000000]

    @staticmethod
    def jump(inst):
        raise DeprecationWarning
        return [10000000 + 4 * int(inst)]

    @staticmethod
    def delay(cycles):
        return [100000000 + int(cycles)]

    @staticmethod
    def go(pixels):
        time = pixels / (Compiler.DEFAULT_VELOCITY / 10000)
        return Compiler.velocity(Compiler.DEFAULT_VELOCITY) + \
            Compiler.delay(time) + Compiler.velocity(0)

    def distTo(self, x, y):
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def angleTo(self, x, y):
        # y coordinate must be negative due to layout of coordinates on screen
        dy = -(y - self.y)
        dx = x - self.x

        # angle is flipped according to spimbot angle I/O
        angle = -math.atan2(dy, dx)

        return math.degrees(angle)

    def goto(self, x, y):
        # Highly tuned for consistency and accuracy

        angle = self.angleTo(x, y)
        dist = self.distTo(x, y)
        cmd_angle = self.angle(angle)
        cmd_go = self.go(dist)

        actualDist = int(dist / (Compiler.DEFAULT_VELOCITY / 10000)) * \
            (Compiler.DEFAULT_VELOCITY / 10000)
        actualAngle = math.radians(-int(angle))

        dx = actualDist * math.cos(actualAngle)
        # Flip dy again due to coordinate system
        dy = -actualDist * math.sin(actualAngle)

        self.x = self.x + dx
        self.y = self.y + dy

        return cmd_angle + cmd_go

    @staticmethod
    def shoot():
        return [2000]

    def shootpos(self, x, y):
        angle = self.angleTo(x, y)
        cmd = self.angle(angle) + self.shoot()
        return cmd

    @staticmethod
    def hostcheck(tile_x, tile_y):
        cmd = 3000 + (tile_x << 6) + tile_y
        return [cmd]

    def chkshoot(self, x, y):
        return self.hostcheck(x // 8, y // 8) + self.shootpos(x, y)

    def set_location(self, x, y):
        self.x = x
        self.y = y

    def custom_reset(self):
        return []


class Lexer:
    def __init__(self, compiler=Compiler):
        self.compiler = compiler()

    def convert_respawn_coordinates(self, pixel_x, pixel_y):
        x = pixel_x // 8
        y = pixel_y // 8

        A = x >= 16
        B = y >= 16
        C = (x // 2 >= 16) if A else (x * 2 >= 16)
        D = (y // 2 >= 16) if B else (y * 2 >= 16)

        host_index = (A << 3) + (B << 2) + (C << 1) + (D << 0)

        return host_index

    def dict_to_array(self, d, size=16):
        arr = [0] * size
        for key, val in d.items():
            arr[key] = val

        return arr

    def preprocess(self, lines):
        new_lines = []

        for line in lines:
            if line.startswith('!!'):
                # Preprocessor directive

                command, *args = line.split()

                if command == '!!copy':
                    start = int(args[0])
                    end = int(args[1])
                    try:
                        times = int(args[2])
                    except ValueError:
                        times = 1

                    start_index = start - 1
                    end_index = end

                    new_lines.extend(lines[start_index:end_index] * times)
            else:
                new_lines.append(line)

        return new_lines

    def parse(self, lines):
        lines = self.preprocess(lines)

        words = []
        respawn_pointers = {}

        for line in lines:
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            # Not a comment or whitespace

            command, *args = line.split()

            if command.startswith('!'):
                # Special lexer command
                if command == '!respawn':
                    if len(args) == 1:
                        host_index = int(args[0])
                    else:
                        x = int(args[0])
                        y = int(args[1])

                        host_index = self.convert_respawn_coordinates(x, y)

                    respawn_pointers[host_index] = 4 * len(words)

            else:
                # Normal compiled command
                words.extend(self.compiler.parse(command, args))

        str_words = [str(i) for i in words]
        output = ' '.join(['.word'] + str_words)

        respawn_pointers_arr = [str(i) for i in self.dict_to_array(respawn_pointers)]
        respawn_pointers_output = ' '.join(['.word'] + respawn_pointers_arr)

        return output, respawn_pointers_output


if __name__ == '__main__':
    inst_filename = sys.argv[1]
    try:
        replace = sys.argv[2] == '-r'
    except IndexError:
        replace = False

    if replace:
        asm_filename = sys.argv[3]

    lexer = Lexer()

    with open(inst_filename) as f:
        lines = f.readlines()

    output, respawn_pointers_output = lexer.parse(lines)

    print(output)
    print(respawn_pointers_output)

    if replace:
        replace_line.replace_in_file(asm_filename, 'movement:', output + '\n')
        replace_line.replace_in_file(asm_filename, 'respawn_pointers:',
            respawn_pointers_output + '\n')
