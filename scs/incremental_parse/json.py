from enum import Enum
from typing import Dict, Union, Optional
from copy import deepcopy

from . import IncrementalParser, ParseFailure, SpecialToken


class JSONParser(IncrementalParser):
    
    def __init__(self):
        super().__init__()
        self._subparser = None
        self._complete = False
    
    def _append(self, char: Union[str, SpecialToken]) -> bool:
        if self._subparser is None:
            if char == SpecialChar.OPEN_ARRAY.value:
                self._subparser = ArrayParser()
            elif char == SpecialChar.OPEN_OBJECT.value:
                self._subparser = ObjectParser()
            return False
        if self._complete:
            if char == SpecialToken.EOS:
                return True
            raise ParseFailure("Expected end of sequence after close.")
        if isinstance(char, SpecialToken):
            return False
        done = self._subparser._append(char)
        if done:
            self._parsed += self._subparser._parsed
            self._complete = True
            return True
        return False
    
    def get_parsed(self) -> str:
        if self._subparser is None:
            return ""
        else:
            return self._subparser.get_parsed()


class ObjectParser(IncrementalParser):

    def __init__(self):
        super().__init__()
        self._parsed = SpecialChar.OPEN_OBJECT.value
        self.state: Dict[str, Union[int, float, str, ObjectParser]] = {}
        self._parse_status: ObjectParseStatus = ObjectParseStatus.OPENED
        self._active_subparser: Optional[IncrementalParser] = None

    def _copy_from(self, other: "ObjectParser"):
        super()._copy_from(other)
        self.state = deepcopy(other.state)
        self._parse_status = other._parse_status
        self._active_subparser = other._active_subparser.copy() if other._active_subparser else None

    def get_parsed(self) -> str:
        parsed = self._parsed
        if self._parse_status in [ObjectParseStatus.IN_KEY_SUBPARSER, ObjectParseStatus.IN_VALUE_SUBPARSER]:
            parsed += self._active_subparser.get_parsed()
        return parsed

    r"""
    Opens a subparser and sends characters to it to begin parsing.
    Previous subparser should be closed before this is called."""
    def _open_subparser(self, char: str):
        if char == SpecialChar.OPEN_OBJECT.value:  # begin parsing object
            self._active_subparser = ObjectParser()
        elif char == SpecialChar.OPEN_ARRAY.value:  # begin parsing array
            self._active_subparser = ArrayParser()
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
        if isinstance(self._active_subparser, NumberParser) and not self._active_subparser.closing_char.isspace():
            # infer current parse state based on how number parser was terminated
            self._parsed += self._active_subparser.closing_char
            if self._active_subparser.closing_char == SpecialChar.COMMA.value:
                self._parse_status = ObjectParseStatus.AWAITING_KEY
            elif self._active_subparser.closing_char == SpecialChar.CLOSE_OBJECT.value:
                self._parse_status = ObjectParseStatus.PARSE_COMPLETE
        elif self._parse_status == ObjectParseStatus.IN_VALUE_SUBPARSER:
            self._parse_status = ObjectParseStatus.FINISHED_VALUE
        else:
            self._parse_status = ObjectParseStatus.FINISHED_KEY
        self._active_subparser = None

    def _append(self, char: str) -> bool:
        if self._parse_status in [ObjectParseStatus.IN_VALUE_SUBPARSER, ObjectParseStatus.IN_KEY_SUBPARSER]:
            done = self._active_subparser._append(char)
            if done:
                self._close_subparser()
            return False

        if char.isspace():
            self._parsed += char
            return False
        
        if self._parse_status == ObjectParseStatus.OPENED:
            if char == SpecialChar.CLOSE_OBJECT.value:
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
    
    def __init__(self):
        super().__init__()
        self._parsed = SpecialChar.OPEN_ARRAY.value

    def _close_subparser(self):
        self._parsed += self._active_subparser._parsed
        if isinstance(self._active_subparser, NumberParser) and not self._active_subparser.closing_char.isspace():
            # infer current parse state based on how number parsing was terminated
            self._parsed += self._active_subparser.closing_char
            if self._active_subparser.closing_char == SpecialChar.COMMA.value:
                self._parse_status = ObjectParseStatus.AWAITING_VALUE
            elif self._active_subparser.closing_char == SpecialChar.CLOSE_ARRAY.value:
                self._parse_status = ObjectParseStatus.PARSE_COMPLETE
        else:
            self._parse_status = ObjectParseStatus.FINISHED_VALUE
        self._active_subparser = None

    def _append(self, char: str) -> bool:
        if self._parse_status == ObjectParseStatus.IN_VALUE_SUBPARSER:
            done = self._active_subparser._append(char)
            if done:
                self._close_subparser()
                self._parse_status = ObjectParseStatus.FINISHED_VALUE
            return False
        
        if char.isspace():
            self._parsed += char
            return False
        
        if self._parse_status == ObjectParseStatus.OPENED:
            if char == SpecialChar.CLOSE_ARRAY.value:
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
        self._is_valid = True
        self.closing_char = None  # appended to outer parser after closing
    
    def _copy_from(self, other: "NumberParser") -> "NumberParser":
        super()._copy_from(other)
        self._has_period = other._has_period
        self._is_valid = other._is_valid
    
    def _append(self, char: str) -> bool:
        if char.isnumeric():
            self._parsed += char
            self._is_valid = True
        elif char == SpecialChar.PERIOD.value:
            if (not self._has_period) and len(self._parsed) > 0:  # cannot begin with '.'
                self._parsed += char
                self._has_period = True
                self._is_valid = False  # cannot end with '.'
            else:
                raise ParseFailure("Invalid position for '.' in number")
        elif char in NumberParser._END_CHARS or char.isspace():
            if self._is_valid:
                self.closing_char = char
                return True
            raise ParseFailure(f"End character '{char}' after invalid number {self._parsed}")
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


class JSONType(Enum):
    NUMBER: NumberParser
    STRING: StringParser
    OBJECT: ObjectParser


class ObjectParseStatus(Enum):
    OPENED = 0
    AWAITING_KEY = 1
    AWAITING_VALUE = 2
    IN_KEY_SUBPARSER = 3
    IN_VALUE_SUBPARSER = 4
    FINISHED_KEY = 5
    FINISHED_VALUE = 6
    PARSE_COMPLETE = 7
