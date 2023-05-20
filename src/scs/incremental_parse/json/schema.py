from enum import Enum
from typing import Dict, Union, Optional, List, Tuple, Iterable
from dataclasses import dataclass

from scs.incremental_parse import IncrementalParser, SpecialToken

from .. import IncrementalParser, ParseFailure, SpecialToken
from ..string_match import StringMatchParser


def isalpha(char: str) -> bool:
    return char.isalpha() or char == '_'    


class SchemaValueParser(IncrementalParser):

    def __init__(self):
        super().__init__()
        self.value: JSONSchema = None


class ObjectSchemaParser(SchemaValueParser):

    def __init__(self):
        super().__init__()
        self.value: ObjectSchema = ObjectSchema()
        self._parsed = SpecialChar.OPEN_OBJECT.value
        self._parse_status: ObjectParseStatus = ObjectParseStatus.OPENED
        self._active_subparser: Optional[SchemaValueParser] = None
        self._curr_key: JSONKey = None
        self._curr_value_basetype: BaseTypeSchema = None
        self._array_set = False

    r"""
    Opens a subparser and sends characters to it to begin parsing.
    Previous subparser should be closed before this is called."""
    def _open_subparser(self, char: str, array_set: bool = False):
        if char == SpecialChar.OPEN_OBJECT.value:  # begin parsing nested schema
            self._active_subparser = ObjectSchemaParser()
            self._parse_status = ObjectParseStatus.IN_VALUE_SUBPARSER
        elif (not array_set) and char == ControlSequences.ARRAY.value[0]:  # begin parsing array control sequence
            self._active_subparser = StringMatchParser(ControlSequences.ARRAY.value, nocase=True)
            self._active_subparser._append(char)
            self._parse_status = ObjectParseStatus.IN_ARRAY_CTR_SEQ_SUBPARSER
        elif char == ControlSequences.STRING.value[0]:
            self._active_subparser = StringMatchParser(ControlSequences.STRING.value, nocase=True)
            self._curr_value_basetype = BaseTypeSchema(BaseType.STRING)
            self._active_subparser._append(char)
            self._parse_status = ObjectParseStatus.IN_VALUE_SUBPARSER
        elif char == ControlSequences.NUMBER.value[0]:
            self._active_subparser = StringMatchParser(ControlSequences.NUMBER.value, nocase=True)
            self._curr_value_basetype = BaseTypeSchema(BaseType.NUMBER)
            self._active_subparser._append(char)
            self._parse_status = ObjectParseStatus.IN_VALUE_SUBPARSER
        else:
            raise ParseFailure(f"Expected start of value, got {char}")

    r"""
    Closes a subparser and adds its final value to current parsed
    content"""
    def _close_subparser(self, char: str):
        parsed = self._active_subparser._parsed
        self._parsed += parsed
        if self._parse_status == ObjectParseStatus.IN_ARRAY_CTR_SEQ_SUBPARSER:
            self._array_set = True
            self._parse_status = ObjectParseStatus.AWAITING_OBJECT
        elif self._parse_status == ObjectParseStatus.IN_VALUE_SUBPARSER:
            self._parse_status = ObjectParseStatus.FINISHED_VALUE
            assert self._curr_key is not None
            value = self._curr_value_basetype if self._curr_value_basetype is not None else self._active_subparser.value
            value._is_list = self._array_set
            self.value.add_prop(key=self._curr_key, value=JSONValue(value))
            self._curr_key = None
            self._curr_value_basetype = None
            self._array_set = False
        else:  # IN_KEY_SUBPARSER
            if char == SpecialChar.OPTIONAL.value:
                # TODO set optional on current key
                self._parse_status = ObjectParseStatus.FINISHED_KEY
                self._curr_key = JSONKey(name=parsed, optional=True)
            elif char == SpecialChar.COLON.value:
                self._parse_status = ObjectParseStatus.AWAITING_VALUE
                self._curr_key = JSONKey(name=parsed, optional=False)
            else:
                raise ParseFailure(f"Invalid char following key name {char}")
        self._active_subparser = None

    def _append(self, char: str) -> bool:
        if self._active_subparser is not None:
            done = self._active_subparser._append(char)
            if done:
                self._close_subparser(char)
                return self._parse_status == ObjectParseStatus.PARSE_COMPLETE
            return False

        if char.isspace():
            return False

        if self._parse_status in [ObjectParseStatus.OPENED, ObjectParseStatus.AWAITING_KEY]:
            if char == SpecialChar.CLOSE_OBJECT.value:
                self._parsed += char
                return True
            if isalpha(char):
                self._active_subparser = PropNameParser()
                self._active_subparser._append(char)
                self._parse_status = ObjectParseStatus.IN_KEY_SUBPARSER
                return False
            raise ParseFailure(f"Expected '}}' or '\"', got {char}")

        if self._parse_status == ObjectParseStatus.AWAITING_VALUE:
            self._open_subparser(char, array_set=False)
            return False
        
        if self._parse_status == ObjectParseStatus.AWAITING_OBJECT:
            self._open_subparser(char, array_set=True)
            return False

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


class JSONSchemaParser(ObjectSchemaParser):

    """
    Parser for outer JSON. Effectively an ObjectSchemaParser that is initialized with AWAITING_VALUE status
    and closes once the first value has been parsed."""
    def __init__(self):
        super().__init__()
        self._curr_key = JSONKey("")
        self._parsed = ""
        self._parse_status: ObjectParseStatus = ObjectParseStatus.AWAITING_VALUE
        self._active_subparser: Optional[SchemaValueParser] = None
        self._done = False

    def _append(self, char: str | SpecialToken) -> bool:
        if self._done:
            if char == SpecialToken.EOS:
                return True
            raise ParseFailure("Got EOS before schema was complete")
        super()._append(char)
        if self._parse_status == ObjectParseStatus.FINISHED_VALUE:
            self._done = True
            return True
        return False
    
    def get_schema(self) -> "JSONSchema":
        for _, value in self.value._child_schemas:
            return value.value_def


class PropNameParser(IncrementalParser):
    def __init__(self) -> None:
        super().__init__()
        self._parsed = ""

    def valid_char(self, char: str):
        if len(self._parsed) > 0:
            return char.isalnum() or char == SpecialChar.UNDERSCORE.value
        return char.isalpha() or char == SpecialChar.UNDERSCORE.value

    def _append(self, char: str) -> bool:
        if not self.valid_char(char):
            return True
        self._parsed += char
        return False


class JSONSchema:
    
    def __init__(self, is_list: bool = False) -> None:
        self._is_list = is_list


class BaseTypeSchema(JSONSchema):
    
    def __init__(self, type: "BaseType", is_list: bool = False):
        super().__init__(is_list=is_list)
        self.type = type

    def __eq__(self, __value: object) -> bool:
        return (
            isinstance(__value, BaseTypeSchema) and
            self.type == __value.type and
            self._is_list == __value._is_list
        )

    def __repr__(self) -> str:
        return ('[]' if self._is_list else '') + self.type.value


# TODO  add this
class StringEnumSchema(JSONSchema):

    def __init__(self, options: List[str] = [], is_list: bool = False) -> None:
        super().__init__(is_list=is_list)
        self.options = options

    def __eq__(self, __value: object) -> bool:
        return (
            isinstance(__value, StringEnumSchema) and
            self._is_list == __value._is_list and
            len(set(self.options).intersection(set(__value.options))) == len(self.options)
        )


class ObjectSchema(JSONSchema):

    def __init__(self, is_list: bool = False):
        super().__init__(is_list=is_list)
        self._child_schemas: List[Tuple[JSONKey, JSONValue]] = []

    def add_prop(self, key: "JSONKey", value: "JSONValue"):
        self._child_schemas += [(key, value)]

    def get_keys(self, optional: Optional[bool] = None) -> Iterable["JSONKey"]:
        for k, _ in self._child_schemas:
            if optional is None or k.optional == optional:
                yield k

    def get_items(self) -> Iterable[Tuple["JSONKey", "JSONValue"]]:
        for k, v in self._child_schemas:
            yield k, v

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, ObjectSchema):
            return False
        if self._is_list != __value._is_list:
            return False
        for (k1, v1), (k2, v2) in zip(self._child_schemas, __value._child_schemas):
            if k1 != k2 or v1 != v2:
                return False
        return True


@dataclass
class JSONKey:
    name: str
    optional: bool = False


@dataclass
class JSONValue:
    value_def: JSONSchema


class BaseType(Enum):
    STRING = "string"
    NUMBER = "number"

    def schema(self, is_list: bool = False) -> BaseTypeSchema:
        return BaseTypeSchema(type=self, is_list=is_list)


class SpecialChar(Enum):
    OPEN_OBJECT = "{"
    CLOSE_OBJECT = "}"
    COMMA = ","
    COLON = ":"
    OPTIONAL = "?"
    UNDERSCORE = "_"


class ControlSequences(Enum):
    STRING = "string"
    NUMBER = "number"
    ONE_OF = "oneof"
    ARRAY = "[]"


class ObjectParseStatus(Enum):
    OPENED = 0
    AWAITING_KEY = 1
    AWAITING_VALUE = 2
    AWAITING_OBJECT = 3
    IN_KEY_SUBPARSER = 4
    IN_ARRAY_CTR_SEQ_SUBPARSER = 5
    IN_VALUE_SUBPARSER = 6
    FINISHED_KEY = 7
    FINISHED_VALUE = 8
    PARSE_COMPLETE = 9
