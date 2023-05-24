from typing import Union, List

from ..incremental_parse import IncrementalParser, ParseFailure, SpecialToken
from ..incremental_parse import EmptyTokenGroup


class SyntaxConstraint:

    def __init__(self, parser: IncrementalParser):
        self.parser = parser

    def update_parser(self, next_chars: Union[List[str], "SpecialToken"]):
        self.parser.append(next_chars)
    
    def check_next(self, chars: Union[List[str], "SpecialToken"]) -> bool:
        if not chars:
            return False
        parser_copy = self.parser.copy()
        try:
            parser_copy.append(chars)
            return True
        except ParseFailure:
            return False
        
    def get_next(self) -> List[str]:
        return self.parser.get_next()
        
    def invalid_token_group(self):
        return self.parser.invalid_token_group()
    
    def valid_token_group(self):
        return self.parser.valid_token_group()
