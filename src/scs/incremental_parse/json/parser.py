from enum import Enum
from typing import Dict, Union, Optional
from copy import deepcopy

from scs.incremental_parse import IncrementalParser

from .. import IncrementalParser, ParseFailure, SpecialToken


class JSONParser(IncrementalParser):
    def __init__(
        self,
        allow_outer_list: bool = True,
        allow_empty: bool = True,
        allow_empty_children: bool = True,
        allow_whitespace_formatting: bool = False,
    ):
        super().__init__()
        self._allow_outer_list = allow_outer_list
        self._allow_empty = allow_empty
        self._allow_empty_children = allow_empty_children
        self._allow_whitespace_formatting = allow_whitespace_formatting
        self._subparser = None
        self._complete = False

    def _copy_from(self, other: "JSONParser"):
        super()._copy_from(other)
        if other._subparser:
            self._subparser = other._subparser.copy()
        self._complete = other._complete
        self._allow_outer_list = other._allow_outer_list
        self._allow_empty = other._allow_empty
        self._allow_empty_children = other._allow_empty_children
        self._allow_whitespace_formatting = other._allow_whitespace_formatting

    def _append(self, char: Union[str, SpecialToken]) -> bool:
        if self._subparser is None:
            if char == SpecialChar.OPEN_ARRAY.value:
                if self._allow_outer_list:
                    self._subparser = ArrayParser(
                        allow_empty=self._allow_empty,
                        allow_empty_children=self._allow_empty_children,
                        allow_whitespace_formatting=self._allow_whitespace_formatting,
                    )
                else:
                    raise ParseFailure("Only allow object in outer JSON")
            elif char == SpecialChar.OPEN_OBJECT.value:
                self._subparser = ObjectParser(
                    allow_empty=self._allow_empty,
                    allow_empty_children=self._allow_empty_children,
                    allow_whitespace_formatting=self._allow_whitespace_formatting,
                )
            else:  # disallow empty space characters
                raise ParseFailure(f"Expected '{{' or '[', got {char}")
            return False
        if self._complete:
            if char == SpecialToken.EOS:
                return True
            raise ParseFailure("Expected end of sequence after close.")
        if isinstance(char, SpecialToken):
            raise ParseFailure(f"Expected character, got special token: {char}")
        done = self._subparser._append(char)
        if done:
            sub_parsed = self._subparser._parsed
            self._parsed += sub_parsed
            self._complete = True
            return True
        return False

    def get_parsed(self) -> str:
        if self._subparser is None:
            return ""
        else:
            return self._subparser.get_parsed()


class ObjectParser(IncrementalParser):
    def __init__(
        self,
        allow_empty: bool = True,
        allow_empty_children: bool = True,
        allow_whitespace_formatting: bool = False,
    ):
        super().__init__()
        self._allow_empty = allow_empty
        self._allow_empty_children = allow_empty_children
        self._allow_whitespace_formatting = allow_whitespace_formatting
        self._parsed = SpecialChar.OPEN_OBJECT.value
        self.state: Dict[str, Union[int, float, str, ObjectParser]] = {}
        self._parse_status: ObjectParseStatus = ObjectParseStatus.OPENED
        self._active_subparser: Optional[IncrementalParser] = None

    def _copy_from(self, other: "ObjectParser"):
        super()._copy_from(other)
        self.state = deepcopy(other.state)
        self._parse_status = other._parse_status
        self._active_subparser = (
            other._active_subparser.copy() if other._active_subparser else None
        )
        self._allow_empty = other._allow_empty
        self._allow_empty_children = other._allow_empty_children
        self._allow_whitespace_formatting = other._allow_whitespace_formatting

    def get_parsed(self) -> str:
        parsed = self._parsed
        if self._parse_status in [
            ObjectParseStatus.IN_KEY_SUBPARSER,
            ObjectParseStatus.IN_VALUE_SUBPARSER,
        ]:
            parsed += self._active_subparser.get_parsed()
        return parsed

    r"""
    Opens a subparser and sends characters to it to begin parsing.
    Previous subparser should be closed before this is called."""

    def _open_subparser(self, char: str):
        if char == SpecialChar.OPEN_OBJECT.value:  # begin parsing object
            self._active_subparser = ObjectParser(
                allow_empty=self._allow_empty_children,
                allow_empty_children=self._allow_empty_children,
                allow_whitespace_formatting=self._allow_whitespace_formatting,
            )
        elif char == SpecialChar.OPEN_ARRAY.value:  # begin parsing array
            self._active_subparser = ArrayParser(
                allow_empty=self._allow_empty_children,
                allow_empty_children=self._allow_empty_children,
            )
        elif char == SpecialChar.QUOTE.value:  # begin parsing text
            self._active_subparser = StringParser()
        elif char.isnumeric():  # begin parsing number
            self._active_subparser = NumberParser()
            self._active_subparser._append(char)
        else:
            raise ParseFailure(f"Expected start of value, got {char}")

    r"""
    Closes a subparser and adds its final value to current parsed
    content"""

    def _close_subparser(self):
        self._parsed += self._active_subparser._parsed
        if (
            isinstance(self._active_subparser, NumberParser)
            and not self._active_subparser.closing_char.isspace()
        ):
            # infer current parse state based on how number parser was terminated
            self._parsed += self._active_subparser.closing_char
            if self._active_subparser.closing_char == SpecialChar.COMMA.value:
                self._parse_status = ObjectParseStatus.AWAITING_KEY
            elif self._active_subparser.closing_char == SpecialChar.CLOSE_OBJECT.value:
                self._parse_status = ObjectParseStatus.PARSE_COMPLETE
            else:
                raise ParseFailure(
                    f"Expected ',' or '}}', got {self._active_subparser.closing_char}"
                )
        elif self._parse_status == ObjectParseStatus.IN_VALUE_SUBPARSER:
            self._parse_status = ObjectParseStatus.FINISHED_VALUE
        else:
            self._parse_status = ObjectParseStatus.FINISHED_KEY
        self._active_subparser = None

    def _append(self, char: str) -> bool:
        if self._parse_status in [
            ObjectParseStatus.IN_VALUE_SUBPARSER,
            ObjectParseStatus.IN_KEY_SUBPARSER,
        ]:
            done = self._active_subparser._append(char)
            if done:
                self._close_subparser()
                return self._parse_status == ObjectParseStatus.PARSE_COMPLETE
            return False

        if char.isspace():
            if not self._allow_whitespace_formatting:
                raise ParseFailure(
                    "Got whitespace in JSON body. If expected set allow_whitespace_formatting accordingly."
                )
            return False

        if self._parse_status == ObjectParseStatus.OPENED:
            if char == SpecialChar.CLOSE_OBJECT.value:
                if not self._allow_empty:
                    raise ParseFailure(
                        "Got empty object. If this is expected set allow_empty and allow_empty_children accordingly"
                    )
                self._parsed += char
                return True
            if char == SpecialChar.QUOTE.value:
                self._active_subparser = StringParser()
                self._parse_status = ObjectParseStatus.IN_KEY_SUBPARSER
                return False
            raise ParseFailure(f"Expected '}}' or '\"', got {char}")

        if self._parse_status == ObjectParseStatus.AWAITING_VALUE:
            self._open_subparser(char)
            self._parse_status = ObjectParseStatus.IN_VALUE_SUBPARSER
            return False

        if self._parse_status == ObjectParseStatus.AWAITING_KEY:
            if char == SpecialChar.QUOTE.value:  # begin parsing key
                self._active_subparser = StringParser()
                self._parse_status = ObjectParseStatus.IN_KEY_SUBPARSER
                return False
            raise ParseFailure(f"Expected '\"', got {char}")

        if self._parse_status == ObjectParseStatus.FINISHED_VALUE:
            if char == SpecialChar.COMMA.value:
                self._parsed += char
                self._parse_status = ObjectParseStatus.AWAITING_KEY
                return False
            if char == SpecialChar.CLOSE_OBJECT.value:
                self._parsed += char
                self._parse_status = ObjectParseStatus.PARSE_COMPLETE
                return True
            raise ParseFailure("Expected ',' or '}', got " + char)

        if self._parse_status == ObjectParseStatus.FINISHED_KEY:
            if char == SpecialChar.COLON.value:
                self._parsed += char
                self._parse_status = ObjectParseStatus.AWAITING_VALUE
                return False
            raise ParseFailure(f"Expected ':', got {char}")

        raise Exception("Something went wrong")


class ArrayParser(ObjectParser):
    def __init__(
        self,
        allow_empty: bool = True,
        allow_empty_children: bool = True,
        allow_whitespace_formatting: bool = False,
    ):
        super().__init__(
            allow_empty=allow_empty,
            allow_empty_children=allow_empty_children,
            allow_whitespace_formatting=allow_whitespace_formatting,
        )
        self._parsed = SpecialChar.OPEN_ARRAY.value

    def _close_subparser(self):
        self._parsed += self._active_subparser._parsed
        if (
            isinstance(self._active_subparser, NumberParser)
            and not self._active_subparser.closing_char.isspace()
        ):
            # infer current parse state based on how number parsing was terminated
            self._parsed += self._active_subparser.closing_char
            if self._active_subparser.closing_char == SpecialChar.COMMA.value:
                self._parse_status = ObjectParseStatus.AWAITING_VALUE
            elif self._active_subparser.closing_char == SpecialChar.CLOSE_ARRAY.value:
                self._parse_status = ObjectParseStatus.PARSE_COMPLETE
            else:
                raise ParseFailure(
                    f"Expected ',' or ']', got {self._active_subparser.closing_char}"
                )
        else:
            self._parse_status = ObjectParseStatus.FINISHED_VALUE
        self._active_subparser = None

    def _append(self, char: str) -> bool:
        if self._parse_status == ObjectParseStatus.IN_VALUE_SUBPARSER:
            done = self._active_subparser._append(char)
            if done:
                self._close_subparser()
                return self._parse_status == ObjectParseStatus.PARSE_COMPLETE
            return False

        if char.isspace():
            if not self._allow_whitespace_formatting:
                raise ParseFailure(
                    "Got whitespace in JSON body. If expected set allow_whitespace_formatting accordingly."
                )
            return False

        if self._parse_status == ObjectParseStatus.OPENED:
            if char == SpecialChar.CLOSE_ARRAY.value:
                if not self._allow_empty:
                    raise ParseFailure(
                        "Got empty object. If this is expected set allow_empty and allow_empty_children accordingly"
                    )
                self._parsed += char
                return True
            self._open_subparser(char)
            self._parse_status = ObjectParseStatus.IN_VALUE_SUBPARSER
            return False

        if self._parse_status == ObjectParseStatus.AWAITING_VALUE:
            self._open_subparser(char)
            self._parse_status = ObjectParseStatus.IN_VALUE_SUBPARSER
            return False

        if self._parse_status == ObjectParseStatus.FINISHED_VALUE:
            if char == SpecialChar.COMMA.value:
                self._parsed += char
                self._parse_status = ObjectParseStatus.AWAITING_VALUE
                return False
            if char == SpecialChar.CLOSE_ARRAY.value:
                self._parsed += char
                self._parse_status = ObjectParseStatus.PARSE_COMPLETE
                return True
            raise ParseFailure(f"Expected ',' or ']', got {char}")

        raise Exception("Something went wrong")


class NumberParser(IncrementalParser):
    _END_CHARS = [",", "]", "}"]

    def __init__(self) -> None:
        super().__init__()
        self._has_period = False
        self._leading_zero = None
        self._is_valid = True
        self.closing_char = None  # appended to outer parser after closing

    def _copy_from(self, other: "NumberParser") -> "NumberParser":
        super()._copy_from(other)
        self._has_period = other._has_period
        self._leading_zero = other._leading_zero
        self._is_valid = other._is_valid

    def _append(self, char: str) -> bool:
        if self._leading_zero:
            if char != SpecialChar.PERIOD.value:
                raise ParseFailure("Leading 0 in integer value")
            self._leading_zero = False
        if char.isnumeric():
            if len(self._parsed) == 0 and char == SpecialChar.ZERO.value:
                self._leading_zero = True
            self._parsed += char
            self._is_valid = True
        elif char == SpecialChar.PERIOD.value:
            if (not self._has_period) and len(
                self._parsed
            ) > 0:  # cannot begin with '.'
                self._parsed += char
                self._has_period = True
                self._is_valid = False  # cannot end with '.'
            else:
                raise ParseFailure("Invalid position for '.' in number")
        elif char in NumberParser._END_CHARS or char.isspace():
            if self._is_valid:
                self.closing_char = char
                return True
            raise ParseFailure(
                f"End character '{char}' after invalid number {self._parsed}"
            )
        else:
            raise ParseFailure(f"Invalid character for number: {char}")
        return False


class StringParser(IncrementalParser):
    def __init__(self) -> None:
        super().__init__()
        self._parsed = '"'
        self._escape_next = False

    def _copy_from(self, other: "StringParser"):
        super()._copy_from(other)
        self._escape_next = other._escape_next

    def _append(self, char: str) -> bool:
        if self._escape_next:
            self._parsed += char
            self._escape_next = False
        elif char == SpecialChar.QUOTE.value:
            self._parsed += char
            return True
        elif char == SpecialChar.ESCAPE.value:
            self._escape_next = True
        else:
            self._parsed += char
        return False


class SpecialChar(Enum):
    ESCAPE = "\\"
    PERIOD = "."
    OPEN_OBJECT = "{"
    CLOSE_OBJECT = "}"
    OPEN_ARRAY = "["
    CLOSE_ARRAY = "]"
    QUOTE = '"'
    COMMA = ","
    COLON = ":"
    ZERO = "0"


class ObjectParseStatus(Enum):
    OPENED = 0
    AWAITING_KEY = 1
    AWAITING_VALUE = 2
    IN_KEY_SUBPARSER = 3
    IN_VALUE_SUBPARSER = 4
    FINISHED_KEY = 5
    FINISHED_VALUE = 6
    PARSE_COMPLETE = 7
