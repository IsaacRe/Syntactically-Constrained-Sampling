import unittest
from scs.incremental_parse.json.schema import ObjectSchemaParser, JSONKey, JSONValue, BaseType, ObjectSchema, JSONSchemaParser


class TestJSONParser(unittest.TestCase):

    def test_parse_object_schema(self):
        parser = ObjectSchemaParser()
        test_data = """{
            name: string,
            age: number,
            city?: string
        }"""
        for char in test_data[1:]:  # ObjectSchemaParser begins parsing from inside curly bracket
            done = parser._append(char)
        self.assertTrue(done)

        # Assert the parsed schema
        data = ObjectSchema()
        for k, v in [
            (JSONKey("name"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("age"), JSONValue(BaseType.NUMBER.schema())),
            (JSONKey("city", optional=True), JSONValue(BaseType.STRING.schema())),
        ]:
            data.add_prop(k, v)

        self.assertEqual(parser.value, data)
    

    def test_parse_json_schema(self):
        parser = JSONSchemaParser()
        test_data = """{
            name: string,
            age: number,
            city?: string
        }"""
        for char in test_data:
            done = parser._append(char)
        self.assertTrue(done)

        # Assert the parsed schema
        data = ObjectSchema()
        for k, v in [
            (JSONKey("name"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("age"), JSONValue(BaseType.NUMBER.schema())),
            (JSONKey("city", optional=True), JSONValue(BaseType.STRING.schema())),
        ]:
            data.add_prop(k, v)

        self.assertEqual(parser.get_schema(), data)


    def test_parse_object_schema_with_optional_properties(self):
        parser = JSONSchemaParser()
        test_data = """{
            name: string,
            age: number,
            city: string,
            country?: string
        }"""
        for char in test_data:
            done = parser._append(char)
        self.assertTrue(done)

        # Assert the parsed schema
        data = ObjectSchema()
        for k, v in [
            (JSONKey("name"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("age"), JSONValue(BaseType.NUMBER.schema())),
            (JSONKey("city"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("country", optional=True), JSONValue(BaseType.STRING.schema()))
        ]:
            data.add_prop(k, v)

        self.assertEqual(parser.get_schema(), data)


    def test_parse_object_schema_with_nested_objects(self):
        parser = ObjectSchemaParser()
        test_data = """{
            name: string,
            age: number,
            address: {
                street: string,
                city: string,
                country?: string
            }
        }"""
        for char in test_data[1:]:
            done = parser._append(char)
        self.assertTrue(done)

        # Assert the parsed schema
        data = ObjectSchema()
        address_data = ObjectSchema()
        for k, v in [
            (JSONKey("street"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("city"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("country", optional=True), JSONValue(BaseType.STRING.schema())),
        ]:
            address_data.add_prop(k, v)
        for k, v in [
            (JSONKey("name"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("age"), JSONValue(BaseType.NUMBER.schema())),
            (JSONKey("address"), JSONValue(address_data)),
        ]:
            data.add_prop(k, v)

        self.assertEqual(parser.value, data)
