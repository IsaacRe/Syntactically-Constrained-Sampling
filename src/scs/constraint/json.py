from . import SyntaxConstraint

from ..incremental_parse.json import JSONParser


def valid_json(
    allow_outer_list: bool = True,
    allow_empty: bool = True,
    allow_empty_children: bool = True,
    allow_whitespace_formatting: bool = False,
) -> SyntaxConstraint:
    return SyntaxConstraint(
        JSONParser(
            allow_outer_list=allow_outer_list,
            allow_empty=allow_empty,
            allow_empty_children=allow_empty_children,
            allow_whitespace_formatting=allow_whitespace_formatting,
        )
    )
