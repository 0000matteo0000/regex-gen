import enum
import logging
import sys
from copy import deepcopy

from escapes import ascii_printable, escapes

logger = logging.getLogger(__name__)
logging_format = "%(levelname)s:%(filename)s:%(funcName)s:%(message)s"
logging.basicConfig(encoding="utf-8", format=logging_format, level=logging.DEBUG)


class stable_set:
    def __init__(self, *args):
        self.__dict = dict()
        # self.__count = 0
        # self.__dirty_count = False
        for c in args:
            self.add(c)

    def add(self, c):
        if len(c) <= 1:
            self.__dict[c] = None  # self.__count
            # self.__count += 1
        else:
            for cc in c:
                self.__dict[cc] = None  # self.__count
                # self.__count += 1

    def remove(self, c):
        self.__dict.pop(c)
        # self.__dirty_count = True  # lazy index update
        # self.__count -= 1

    def __len__(self):
        return len(self.__dict)

    def __iter__(self):
        return iter(self.__dict)

    def __contains__(self, c):
        return c in self.__dict

    # def __recount(self):
    #     self.__count = 0
    #     for c in self.__dict:
    #         self.__dict[c] = self.__count
    #         self.__count += 1

    # def index(self, c):
    #     if self.__dirty_count:  # lazy index update
    #         self.__recount()
    #     return self.__dict[c]

    def __repr__(self):
        return "<" + repr(list(self.__dict))[1:-1] + ">"


class State(enum.IntEnum):
    NONE = enum.auto()
    ESCAPE = enum.auto()
    SET = enum.auto()
    COUNT = enum.auto()
    OR = enum.auto()
    GROUP = enum.auto()


def read_hex(rule, i=0, n=2):
    values = ""
    for i in range(i, i + n):
        if i >= len(rule):
            logger.debug("SystaxError unclosed %r", State.ESCAPE)
            raise SyntaxError(f"Invalid spec, end of spec while still processing an open {State.ESCAPE.name} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")
        match rule[i]:
            case "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "a" | "b" | "c" | "d" | "e" | "f" | "A" | "B" | "C" | "D" | "E" | "F":
                logger.debug("case %r", rule[i])
                values += rule[i]
                logger.debug("values %r", values)
            case _:
                raise SyntaxError(f"Invalid hexadecimal escape sequence, invalid hexadecimal character at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
    return chr(int(values, 16)), i


def read_oct(rule, i=0, n=3):
    values = ""
    for i in range(i, i + n):
        if i >= len(rule):
            logger.debug("SystaxError unclosed %r", State.ESCAPE)
            raise SyntaxError(f"Invalid spec, end of spec while still processing an open {State.ESCAPE.name} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")
        match rule[i]:
            case "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7":
                logger.debug("case %r", rule[i])
                values += rule[i]
                logger.debug("values %r", values)
            case _:
                raise SyntaxError(f"Invalid octal escape sequence, invalid octal character at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
    ov = int(values, 8)
    if ov > 255:
        raise SyntaxError(f"Invalid octal escape sequence, invalid octal value ({ov!r} is > than 255 = 0o377 = 0xff) at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
    return chr(ov), i


def rparse_escape(rule, i=0, states=None, options=None):
    logger.debug("enter %r, %r, %r, %r", rule, i, states, options)
    # skip registering state since this function does not recurse
    if states[-1] != State.SET:
        options.append(stable_set())  # do not create a new option if escaping inside a set
        logger.debug("set %r %r", states[-1], State.SET)
    if i >= len(rule):
        logger.debug("SystaxError unclosed %r", State.ESCAPE)
        raise SyntaxError(f"Invalid spec, end of spec while still processing an open {State.ESCAPE.name} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")
    logger.debug("case %r", rule[i])
    if rule[i] in escapes:
        l = escapes[rule[i]]
    else:
        match rule[i]:
            case "x":
                l, i = read_hex(rule, i=i + 1, n=2)
            case "o":
                l, i = read_oct(rule, i=i + 1, n=3)
            case "u":
                l, i = read_hex(rule, i=i + 1, n=4)
            case "U":
                l, i = read_hex(rule, i=i + 1, n=8)
            case _:
                l = rule[i]
    logger.debug("l %r", l)
    options[-1].add(l)
    logger.debug("options %r", options[-1])
    logger.debug("return %r, %r", i, options)
    return i, options


def rparse_set(rule, i=0, states=None, options=None):
    logger.debug("se_setenter %r, %r, %r, %r", rule, i, states, options)
    negative_group = False
    if i >= len(rule):
        logger.debug("SystaxError unclosed %r", State.SET)
        raise SyntaxError(f"Invalid spec, end of spec while still processing an open {State.SET.name} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")
    if rule[i] == "^":
        logger.debug("negative %r", rule[i])
        negative_group = True
        i += 1
        if i >= len(rule):
            logger.debug("SystaxError unclosed %r", State.SET)
            raise SyntaxError(f"Invalid spec, end of spec while still processing an open {State.SET.name} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")
    if not negative_group:
        options.append(stable_set())
    else:
        options.append(stable_set(ascii_printable))
    logger.debug("options %r", options[-1])
    while i < len(rule):
        match rule[i]:
            case "]":  # end set
                logger.debug("case %r", rule[i])
                logger.debug("options %r", options[-1])
                if len(options[-1]) == 0:  # discard empty set
                    logger.debug("options pop empty")
                    options.pop()
                logger.debug("return %r, %r", i, options)
                return i, options
            case "\\":  # escape sequence in set
                logger.debug("case %r", rule[i])
                states.append(State.SET)
                i, options = rparse_escape(rule, i=i + 1, states=states, options=options)
                states.pop()
            case _:  # set opening char is allowed in set as a normal char
                logger.debug("case %r", rule[i])
                if not negative_group:
                    options[-1].add(rule[i])
                else:
                    options[-1].remove(rule[i])
                logger.debug("options %r", options[-1])
        i += 1
    logger.debug("SystaxError unclosed %r", State.SET)
    raise SyntaxError(f"Invalid spec, end of spec while still processing an open {State.SET.name} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")


def rparse__count(rule, i=0, states=None, options=None):
    logger.debug("enter %r, %r, %r, %r", rule, i, states, options)
    # skip registering state since this function does not recurse
    count_values = [""]
    while i < len(rule):
        match rule[i]:
            case "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9":
                logger.debug("case %r", rule[i])
                count_values[-1] += rule[i]
            case ",":  # next count argument
                logger.debug("case %r", rule[i])
                if len(count_values) >= 2:  # count only allows a max of 2 arguments
                    raise SyntaxError(f"Invalid count, too many count arguments at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
                count_values.append("")
            case "}":  # end count
                logger.debug("case %r", rule[i])
                assert 1 <= len(count_values) <= 2  # count only allows 1 or 2 arguments
                if len(count_values) == 1:  # count with one argument
                    if len(count_values[0]) == 0:  # if no argument was given
                        raise SyntaxError(f"Invalid count, no count arguments given at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
                    max = int(count_values[0])
                    min = max
                else:  # count with two arguments
                    if len(count_values[1]) == 0:  # first argument is infinity by default if not given, but we can't do that
                        raise SyntaxError(f"Invalid count, even if regex allows unlimited count max it's not possible to handle it for generation, error at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
                    if len(count_values[0]) == 0:  # first argument is zero by default if not given
                        count_values[0] = 0
                    min, max = int(count_values[0]), int(count_values[1])
                if min > max:  # the first count argument must be less than the second
                    raise SyntaxError(f"Invalid count, the first count argument must be less than the second at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
                if max == 0:
                    logger.debug("options pop empty")
                    options.pop()  # discard empty count
                else:
                    # TODO: generate differently to remove duplicates (ex.: 'a', 'a' on "a?a?")
                    # TODO: generate differently to remove duplication of already optionals (ex.: '', '' on "a??")
                    options.append([[options.pop()]])
                    if min > 0:
                        for _ in range(1, min):
                            options[-1][-1].append(options[-1][-1][-1])
                        if max > 1 and max > min:
                            options[-1][-1].append(deepcopy(options[-1][-1][-1]))
                            options[-1][-1][-1].add("")
                    else:
                        options[-1][-1][-1].add("")
                    for _ in range(min + 1, max):
                        options[-1][-1].append(options[-1][-1][-1])
                logger.debug("return %r, %r", i, options)
                return i, options
            case _:
                logger.debug("case %r", rule[i])
                raise SyntaxError(f"Invalid count, invalid argument character at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
        i += 1
    logger.debug("SystaxError unclosed %r", State.COUNT)
    raise SyntaxError(f"Invalid spec, end of spec while still processing an open {State.COUNT.name} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")


def rparse(rule, i=0, states=None, options=None):
    if options is None:
        options = []
    if states is None:
        states = [State.NONE]
    enter_state_index = len(states) - 1
    while i < len(rule):
        match rule[i]:
            case "\\":  # escape sequence
                i, options = rparse_escape(rule, i=i + 1, states=states, options=options)
            case "[":  # new set
                i, options = rparse_set(rule, i=i + 1, states=states, options=options)
            case "*" | "+":
                raise SyntaxError(f"Invalid count, even if regex allows unlimited count max it's not possible to handle it for generation, error at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
            case "?":  # new optional (same as count 0-1)
                if len(options) > 0:
                    options.append([[options.pop()], ""])
                else:
                    # logger.warning(f"optional modifier character {rule[i]!r} applied to nothing, ignoring it, warning at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
                    print(f"optional modifier character {rule[i]!r} applied to nothing, ignoring it, warning at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^", file=sys.stderr)
            case "{":  # new count
                i, options = rparse__count(rule, i=i + 1, states=states, options=options)
            case "|":  # new or
                if len(states) > 1 and states[enter_state_index] == State.OR:
                    return options, i
                states.append(State.OR)
                if len(options) > 0:
                    options = [[options, ]]
                else:
                    options = [[[[""]], ]]
                while i < len(rule) and rule[i] == "|":
                    o, i = rparse(rule, i=i + 1, states=states)
                    options[-1].append(o)
                states.pop()
            case "(":  # new group
                states.append(State.GROUP)
                o, i = rparse(rule, i=i + 1, states=states)
                options.append([o])
                states.pop()
            case ")":
                if states[enter_state_index] == State.GROUP:
                    return options, i
                elif states[enter_state_index] == State.OR and enter_state_index > 0 and states[enter_state_index - 1] == State.GROUP:
                    return options, i - 1  # allow closing for the parent group too
                else:
                    raise SyntaxError(f"Invalid spec, closing group that was never opened {rule[i]!r} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")
            case "^" | "$":  # special char
                # logger.warning(f"boundary assertion character {rule[i]!r} is valid in regex  but does not make sense here, ignoring it, warning at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^")
                print(f"boundary assertion character {rule[i]!r} is valid in regex  but does not make sense here, ignoring it, warning at index {i}: {rule[i]!r}\n\t{rule}\n\t{'~' * i}^", file=sys.stderr)
            case _:  # normal char
                options.append(stable_set())
                options[-1].add(rule[i])
        i += 1
    if states[-1] != State.NONE and states[-1] != State.OR:
        logger.debug("SystaxError unclosed %r", states[-1])
        raise SyntaxError(f"Invalid spec, end of spec while still processing an open {states[-1].name} at index {i-1}: {rule[i-1]!r}\n\t{rule}\n\t{'~' * (i-1)}^")
    if len(options) == 0:
        options = [[""]]
    return options, i


def rmap(f, it):
    return (f(rmap(f, x)) if not isinstance(x, str) else x for x in it)


def parse(rule, i=0, states=None, options=None):
    logger.debug("-" * 25)
    logger.info("enter %r, %r, %r, %r", rule, i, states, options)
    p = list(rmap(list, rparse(rule, i=i, states=states, options=options)[0]))
    logger.debug("-" * 25)
    return p


def r_or_gen(options, generated=""):
    logger.debug("in %r, %r", options, generated)
    if isinstance(options, str):
        logger.debug("yeld str %r, %r, %r", options, generated, generated + options)
        yield generated + options
        return
    for o in options:
        for g in r_and_gen(o, generated=generated):
            logger.debug("yeld g %r, %r, %r", options, generated, g)
            yield g
    logger.debug("return %r, %r", options, generated)


def r_and_gen(options, i=0, generated=""):
    logger.debug("in %r, %r, %r", options, i, generated)
    if isinstance(options, str):
        logger.debug("yeld str %r, %r, %r, %r", options, i, generated, generated + options)
        yield generated + options
        return
    if i >= len(options):
        if i > 0:
            logger.debug("yeld i>0 %r, %r, %r", options, i, generated)
            yield generated
        logger.debug("return i >= len(options) %r, %r, %r", options, i, generated)
        return
    for o in r_or_gen(options[i], generated=generated):
        for g in r_and_gen(options, i + 1, o):
            logger.debug("yeld g %r, %r, %r", options, i, generated, g)
            yield g
    logger.debug("return %r, %r, %r", options, i, generated)


def gen(options):
    logger.debug("-" * 25)
    for r in r_and_gen(options):
        yield r
    logger.debug("-" * 25)
