from typing import List

from . import SyntaxConstraint

from ..incremental_parse.string_match import MultiStringMatchParser


def one_of(match_strings: List[str] = []) -> SyntaxConstraint:
    return SyntaxConstraint(
        MultiStringMatchParser(match_strings=match_strings)
    )
