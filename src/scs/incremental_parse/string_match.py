from typing import List, Optional, Union
from scs.incremental_parse import IncrementalParser, SpecialToken
from . import IncrementalParser, ParseFailure, SpecialToken, TokenGroup


class StringMatchParser(IncrementalParser):

    def __init__(self, match_string: str = "", nocase: bool = False):
        super().__init__()
        self.match_string = match_string.lower() if nocase else match_string
        self._nocase = nocase
        self._parse_idx = 0
        self._done = False

    def _copy_from(self, other: "StringMatchParser"):
        super()._copy_from(other)
        self.match_string = other.match_string
        self._parse_idx = other._parse_idx
        self._done = other._done

    def _append(self, char: str | SpecialToken) -> bool:
        if self._nocase:
            char = char.lower()
        if isinstance(char, SpecialToken):
            if char != SpecialToken.EOS or not self._done:
                raise ParseFailure("Got special token before match completion")
            return True
        if len(self.match_string) <= self._parse_idx:
            raise ParseFailure("Parse idx out of bounds")
        if self.match_string[self._parse_idx] != char:
            raise ParseFailure("Found character mismatch")
        self._parsed += char
        self._parse_idx += 1
        self._done = self._parse_idx == len(self.match_string)
        return self._done

    def get_next(self) -> List[str]:
        return [self.match_string[self._parse_idx:]]
    
    def invalid_token_groups(self) -> TokenGroup:
        return NonAlnumGroup


class MultiStringMatchParser(IncrementalParser):

    def __init__(self, match_strings: List[str] = []):
        super().__init__()
        self._done = False
        self._sub_parsers: List[StringMatchParser] = [StringMatchParser(match_string) for match_string in match_strings]
        self._running_parsers = list(range(len(self._sub_parsers)))

    def _copy_from(self, other: "MultiStringMatchParser"):
        super()._copy_from(other)
        self._done = other._done
        self._sub_parsers = [s.copy() for s in other._sub_parsers]
        self._running_parsers = [i for i in other._running_parsers]

    def _append(self, char: str | SpecialToken) -> bool:
        if len(self._running_parsers) == 0:
            raise ParseFailure("No remaining subparsers to match")
        not_failed = []
        failures = []
        done = False
        for i in self._running_parsers:
            try:
                done = self._sub_parsers[i]._append(char) or done
                not_failed += [i]
            except ParseFailure as e:
                failures += [str(e)]
        self._running_parsers = not_failed
        if len(not_failed) == 0:
            raise ParseFailure(f"Failure(s) in string match subparsers: {', '.join(failures)}")
        self._parsed = self._sub_parsers[self._running_parsers[0]]._parsed
        return done
    
    def get_next(self) -> List[str]:
        next_ = []
        for i in self._running_parsers:
            next_ += self._sub_parsers[i].get_next()
        return next_
    
    def invalid_token_groups(self) -> TokenGroup:
        return NonAlnumGroup


class NonAlnumGroup(TokenGroup):

    @staticmethod
    def filter(token: str) -> bool:
        for c in token:
            if not (c.isalnum() or c == "_"):
                return True
        return False
