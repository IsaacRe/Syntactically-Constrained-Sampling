from . import SyntaxConstraint

from ..incremental_parse.json import JSONParser


def valid_json() -> SyntaxConstraint:
    return SyntaxConstraint(JSONParser())
