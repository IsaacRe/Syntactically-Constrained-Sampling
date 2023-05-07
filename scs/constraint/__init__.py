from typing import Union, List

from ..incremental_parse import IncrementalParser, ParseFailure, SpecialToken


class SyntaxConstraint:

    def __init__(self, parser: IncrementalParser):
        self.parser = parser

    def update_parser(self, next_chars: Union[List[str], "SpecialToken"]):
        self.parser.append(next_chars)
    
    def check_next(self, chars: Union[List[str], "SpecialToken"]) -> bool:
        parser_copy = self.parser.copy()
        try:
            parser_copy.append(chars)
            return True
        except ParseFailure:
            return False
