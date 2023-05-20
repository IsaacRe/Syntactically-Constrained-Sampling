from enum import Enum
from typing import Dict, Union, Optional, List
from copy import deepcopy, copy

from scs.incremental_parse import IncrementalParser

from .. import IncrementalParser, ParseFailure, SpecialToken
from ..string_match import MultiStringMatchParser
from .schema import JSONSchema, ObjectSchema, BaseType


class JSONParser(IncrementalParser):
    def __init__(
        self,
        schema: JSONSchema = None,
    ):
        super().__init__()
        self._schema = schema
        self._subparser = None
        self._complete = False

    def _copy_from(self, other: "JSONParser"):
        super()._copy_from(other)
        self._schema = other._schema
        self._subparser = other._subparser.copy() if other._subparser else None
        self._complete = other._complete

    def _append(self, char: Union[str, SpecialToken]) -> bool:
        if self._subparser is None:
            if char == SpecialChar.OPEN_ARRAY.value and self._schema._is_list:
                self._subparser = ArrayParser(schema=self._schema)
            elif char == SpecialChar.OPEN_OBJECT.value and not self._schema._is_list:
                self._subparser = ObjectParser(schema=self._schema)
            else:  # disallow empty space characters
                raise ParseFailure(f"Expected {('[' if self._schema._is_list else '{')}, got {char}")
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


class ObjectOrArrayParser(IncrementalParser):
    def __init__(
        self,
        schema: JSONSchema = None,
    ):
        super().__init__()
        self._schema = schema
        self._parse_status: ObjectParseStatus = ObjectParseStatus.OPENED
        self._active_subparser: Optional[IncrementalParser] = None

    def _copy_from(self, other: "ObjectParser"):
        super()._copy_from(other)
        self._schema = other._schema
        self._parse_status = other._parse_status
        self._active_subparser = (
            other._active_subparser.copy() if other._active_subparser else None
        )

    def get_parsed(self) -> str:
        parsed = self._parsed
        if self._active_subparser:
            parsed += self._active_subparser.get_parsed()
        return parsed


class ObjectParser(ObjectOrArrayParser):
    def __init__(
        self,
        schema: ObjectSchema = None,
    ):
        super().__init__(schema=schema)
        self._schema: ObjectSchema
        self._parsed = SpecialChar.OPEN_OBJECT.value
        self._current_key = None
        self._schema_dict, self._remaining_required_keys, self._remaining_optional_keys = None, None, None
        if self._schema:
            self._schema_dict = {k.name: v.value_def for k, v in self._schema.get_items()}
            self._remaining_required_keys = {k.name for k in self._schema.get_keys(optional=False)}
            self._remaining_optional_keys = {k.name for k in self._schema.get_keys(optional=True)}

    @property
    def _current_value_schema(self) -> JSONSchema:
        return self._schema_dict[self._current_key]
    
    @property
    def _remaining_keys(self) -> List[str]:
        return list(self._remaining_required_keys) + list(self._remaining_optional_keys)
    
    def _update_remaining(self, key: str):
        try:
            self._remaining_required_keys.remove(key)
        except KeyError:
            self._remaining_optional_keys.remove(key)
    
    def _is_complete(self) -> bool:
        return len(self._remaining_required_keys) == 0
    
    def _copy_from(self, other: "ObjectParser"):
        super()._copy_from(other)
        self._current_key = other._current_key
        self._schema_dict = copy(other._schema_dict)
        self._remaining_required_keys = copy(other._remaining_required_keys)
        self._remaining_optional_keys = copy(other._remaining_optional_keys)

    r"""
    Opens a subparser and sends characters to it to begin parsing.
    Previous subparser should be closed before this is called."""
    def _open_subparser(self, char: str):
        if self._parse_status == ObjectParseStatus.AWAITING_VALUE:
            if self._current_value_schema._is_list:
                if char != SpecialChar.OPEN_ARRAY.value:
                    raise ParseFailure(f"Expected '[' got {char}")
                self._active_subparser = ArrayParser(schema=self._current_value_schema)
            elif char == SpecialChar.OPEN_OBJECT.value and isinstance(self._current_value_schema, ObjectSchema):
                self._active_subparser = ObjectParser(schema=self._current_value_schema)
            elif char == SpecialChar.QUOTE.value and self._current_value_schema == BaseType.STRING.schema():
                self._active_subparser = StringParser()
            elif char.isnumeric() and self._current_value_schema == BaseType.NUMBER.schema():
                self._active_subparser = NumberParser()
                self._active_subparser._append(char)
            else:
                raise ParseFailure(f"Expected start of value, got {char}")
            self._parse_status = ObjectParseStatus.IN_VALUE_SUBPARSER
        elif self._parse_status == ObjectParseStatus.AWAITING_KEY and char == SpecialChar.QUOTE.value:
            self._active_subparser = MultiStringMatchParser(match_strings=self._remaining_keys)
            self._parse_status = ObjectParseStatus.IN_KEY_SUBPARSER
        else:
            raise ParseFailure(f"Invalid parse status for opening subparser: {self._parse_status}")

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
            self._update_remaining(self._current_key)
            if self._active_subparser.closing_char == SpecialChar.COMMA.value:
                self._parse_status = ObjectParseStatus.AWAITING_KEY
            elif self._active_subparser.closing_char == SpecialChar.CLOSE_OBJECT.value:
                if not self._is_complete():
                    raise ParseFailure("Attempted close before all required keys parsed")
                self._parse_status = ObjectParseStatus.PARSE_COMPLETE
            else:
                raise ParseFailure(
                    f"Expected ',' or '}}', got {self._active_subparser.closing_char}"
                )
        elif self._parse_status == ObjectParseStatus.IN_VALUE_SUBPARSER:
            self._update_remaining(self._current_key)
            self._parse_status = ObjectParseStatus.FINISHED_VALUE
        else:
            # defer updating parse status to FINISHED_KEY until we receive closing quote
            self._current_key = self._active_subparser._parsed
        self._active_subparser = None

    def _append(self, char: str) -> bool:
        if self._active_subparser:
            done = self._active_subparser._append(char)
            if done:
                self._close_subparser()
                return self._parse_status == ObjectParseStatus.PARSE_COMPLETE
            return False

        if char.isspace():
            raise ParseFailure(
                "Got whitespace in JSON body"
            )
        
        remaining_keys = self._remaining_keys

        if self._parse_status == ObjectParseStatus.OPENED:
            if char == SpecialChar.CLOSE_OBJECT.value:
                if not self._is_complete():
                    raise ParseFailure(
                        "Got empty object"
                    )
                self._parsed += char
                return True
            if char == SpecialChar.QUOTE.value:
                if not remaining_keys:
                    raise ParseFailure("No keys remaining to parse")
                self._active_subparser = MultiStringMatchParser(match_strings=remaining_keys)
                self._parse_status = ObjectParseStatus.IN_KEY_SUBPARSER
                return False
            raise ParseFailure(f"Expected '}}' or '\"', got {char}")

        if self._parse_status in [ObjectParseStatus.AWAITING_VALUE, ObjectParseStatus.AWAITING_KEY]:
            self._open_subparser(char)
            return False

        if self._parse_status == ObjectParseStatus.FINISHED_VALUE:
            if char == SpecialChar.COMMA.value and remaining_keys:
                self._parsed += char
                self._parse_status = ObjectParseStatus.AWAITING_KEY
                return False
            if char == SpecialChar.CLOSE_OBJECT.value and self._is_complete():
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
        
        if self._parse_status == ObjectParseStatus.IN_KEY_SUBPARSER:
            if char == SpecialChar.QUOTE.value:
                self._parsed += char
                self._parse_status = ObjectParseStatus.FINISHED_KEY
                return False
            raise ParseFailure(f"Expected '\"' after parsed key, got {char}")

        raise Exception("Something went wrong")


class ArrayParser(ObjectOrArrayParser):
    def __init__(
        self,
        schema: JSONSchema = None,
    ):
        super().__init__(schema=schema)
        self._parsed = SpecialChar.OPEN_ARRAY.value

    def _open_subparser(self, char: str):
        if char == SpecialChar.OPEN_OBJECT.value and isinstance(self._schema, ObjectSchema):
            self._active_subparser = ObjectParser(schema=self._schema)
        elif char == SpecialChar.QUOTE.value and self._schema == BaseType.STRING.schema(is_list=True):
            self._active_subparser = StringParser()
        elif char.isnumeric() and self._schema == BaseType.NUMBER.schema(is_list=True):
            self._active_subparser = NumberParser()
            self._active_subparser._append(char)
        else:
            raise ParseFailure(f"Expected start of value, got {char}")
        self._parse_status = ObjectParseStatus.IN_VALUE_SUBPARSER

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
            raise ParseFailure(
                "Got whitespace in JSON body. If expected set allow_whitespace_formatting accordingly."
            )

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
