from . import SyntaxConstraint

from ..incremental_parse.json import JSONParser
from ..incremental_parse.json.parser import JSONParser as ConstrainedParser
from ..incremental_parse.json.schema import JSONSchemaParser


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


def force_json_schema(schema: str) -> SyntaxConstraint:
    schema_parser = JSONSchemaParser()
    schema_parser.append(schema)
    json_schema = schema_parser.get_schema()
    return SyntaxConstraint(
        ConstrainedParser(schema=json_schema)
    )
