import unittest
from scs.incremental_parse.json.schema import ObjectSchemaParser, JSONKey, JSONValue, BaseType, ObjectSchema, JSONSchemaParser
from scs.incremental_parse.json.parser import JSONParser
from scs.handler import SyntaxValidityCheckHandler, JSONSchemaCheckFactory, SyntaxConstraint

#              0     1    2    3    4    5      6    7    8    9    10       11   12   13
TEST_VOCAB = ['{"', '{', '}', '[', ']', 'key', '1', '2', '3', '"', 'value', ':', ',', ' ']
TEST_SCHEMA = """[]{
    key2: string,
    key3?: number
}"""

class TestJSONSchema(unittest.TestCase):

    def test_json_schema_check_handler(self):
        handler = SyntaxValidityCheckHandler(
            TEST_VOCAB,
            JSONSchemaCheckFactory(schema=TEST_SCHEMA),
            num_workers=4,
        )
        json = '[{"key2":"value"}]'
        tokenized = [3, 0, 5, 7, 9, 11, 9, 10, 9, 2, 4]
        print(''.join(TEST_VOCAB[i] for i in tokenized))

        for tok in tokenized:
            l = list(handler.await_invalid_next_tokens())
            if l:
                _, _, suppress = l[0]
                if not suppress:
                    self.assertTrue(tok in [i[1] for i in l])
            handler.update([tok])
            handler.process_invalid_next_tokens()
