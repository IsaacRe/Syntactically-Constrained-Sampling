from enum import Enum
from typing import Union, List


class IncrementalParser:

    def __init__(self):
        self._parsed = ""

    def _copy_from(self, other: "IncrementalParser"):
        self._parsed = other._parsed

    def get_parsed(self) -> str:
        return self._parsed
    
    r"""
    Returns a copy of this ParseState
    
    Return:
        (ParseState):
        Copy of this ParseState object"""
    def copy(self) -> "IncrementalParser":
        copy = type(self)()
        copy._copy_from(self)
        return copy

    r"""
    Continues parsing with the provided character. Returns a boolean
    indicating whether parsing of the value has concluded

    Parameters:
        char (str):
            Next character to parse

    Raise:
        ParseFailure:
            Raised if parsing fails for the provided character

    Return:
        bool:
        Boolean specifying whether parsing of this value is complete"""
    def _append(self, char: Union[str, "SpecialToken"]):
        raise NotImplementedError()
    
    def append(self, chars: Union[List[str], "SpecialToken"]):
        for c in chars:
            self._append(c)


class ParseFailure(Exception):
    pass


class SpecialToken(Enum):
    EOS = 0
