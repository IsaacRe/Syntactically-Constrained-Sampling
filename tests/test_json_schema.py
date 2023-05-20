import unittest
from scs.incremental_parse.json.schema import ObjectSchemaParser, JSONKey, JSONValue, BaseType, ObjectSchema, JSONSchemaParser
from scs.incremental_parse.json.parser import JSONParser


class TestJSONSchema(unittest.TestCase):

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


    def test_parse_json_basetype_list(self):
        parser = JSONSchemaParser()
        test_data = """{
            name: []string,
            age: []number,
            city?: string
        }"""
        for char in test_data:
            done = parser._append(char)
        self.assertTrue(done)

        # Assert the parsed schema
        data = ObjectSchema()
        for k, v in [
            (JSONKey("name"), JSONValue(BaseType.STRING.schema(is_list=True))),
            (JSONKey("age"), JSONValue(BaseType.NUMBER.schema(is_list=True))),
            (JSONKey("city", optional=True), JSONValue(BaseType.STRING.schema())),
        ]:
            data.add_prop(k, v)

        self.assertEqual(parser.get_schema(), data)


    def test_parse_json_outer_list(self):
        parser = JSONSchemaParser()
        test_data = """[]{
            name: string,
            age: number,
            city?: string
        }"""
        for char in test_data:
            done = parser._append(char)
        self.assertTrue(done)

        # Assert the parsed schema
        data = ObjectSchema(is_list=True)
        for k, v in [
            (JSONKey("name"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("age"), JSONValue(BaseType.NUMBER.schema())),
            (JSONKey("city", optional=True), JSONValue(BaseType.STRING.schema())),
        ]:
            data.add_prop(k, v)

        self.assertEqual(parser.get_schema(), data)


    def test_parse_json_with_underscore(self):
        parser = JSONSchemaParser()
        test_data = """[]{
            my_name: string,
            age: number,
            city?: string
        }"""
        for char in test_data:
            done = parser._append(char)
        self.assertTrue(done)

        # Assert the parsed schema
        data = ObjectSchema(is_list=True)
        for k, v in [
            (JSONKey("my_name"), JSONValue(BaseType.STRING.schema())),
            (JSONKey("age"), JSONValue(BaseType.NUMBER.schema())),
            (JSONKey("city", optional=True), JSONValue(BaseType.STRING.schema())),
        ]:
            data.add_prop(k, v)

        self.assertEqual(parser.get_schema(), data)


class TestJSONParser(unittest.TestCase):

    def test_parse_json(self):
        schema_parser = JSONSchemaParser()
        test_schema = """{
            name: string,
            age: number,
            city?: string
        }"""
        schema_parser.append(test_schema)
        schema = schema_parser.get_schema()

        test_json = '{"name":"John","age":35,"city":"Atlanta"}'

        json_parser = JSONParser(schema=schema)

        for char in test_json:
            done = json_parser._append(char)
        self.assertTrue(done)


    def test_parse_json_without_optional_value(self):
        schema_parser = JSONSchemaParser()
        test_schema = """{
            name: string,
            age: number,
            city?: string
        }"""
        schema_parser.append(test_schema)
        schema = schema_parser.get_schema()

        test_json = '{"name":"John","age":35}'

        json_parser = JSONParser(schema=schema)

        for char in test_json:
            done = json_parser._append(char)
        self.assertTrue(done)


    def test_parse_json_with_nested_objects(self):
        schema_parser = JSONSchemaParser()
        test_schema = """{
            name: string,
            age: number,
            address: {
                street: string,
                city: string,
                country?: string
            }
        }"""
        schema_parser.append(test_schema)
        schema = schema_parser.get_schema()

        test_json = '{"name":"John","age":35,"address":{"street":"1st Ave","city":"New York"}}'

        json_parser = JSONParser(schema=schema)

        for char in test_json:
            done = json_parser._append(char)
        self.assertTrue(done)

    
    def test_parse_json_with_basetype_list(self):
        schema_parser = JSONSchemaParser()
        test_schema = """{
            name: []string,
            age: []number,
            city?: string
        }"""
        schema_parser.append(test_schema)
        schema = schema_parser.get_schema()

        test_json = '{"name":["John","Jimmy"],"age":[35,12]}'

        json_parser = JSONParser(schema=schema)

        for char in test_json:
            done = json_parser._append(char)
        self.assertTrue(done)


    def test_parse_json_with_outer_list(self):
        schema_parser = JSONSchemaParser()
        test_schema = """[]{
            name: string,
            age: number,
            city?: string
        }"""
        schema_parser.append(test_schema)
        schema = schema_parser.get_schema()

        test_json = '[{"name":"John","age":35},{"name":"George","age":23,"city":"Austin"}]'

        json_parser = JSONParser(schema=schema)

        for char in test_json:
            done = json_parser._append(char)
        self.assertTrue(done)


    def test_parse_json_with_outer_list_of_basetypes(self):
        schema_parser = JSONSchemaParser()
        test_schema = """[]number"""
        schema_parser.append(test_schema)
        schema = schema_parser.get_schema()

        test_json = '[1,2,3,4]'

        json_parser = JSONParser(schema=schema)

        for char in test_json:
            done = json_parser._append(char)
        self.assertTrue(done)

    
    def test_parse_json_incremental(self):
        schema_parser = JSONSchemaParser()
        test_schema = """[]{
            name: string,
            age: number,
            city?: string
        }"""
        schema_parser.append(test_schema)
        schema = schema_parser.get_schema()

        test_json = '[{"name":"John","age":35},{"name":"George","age":23,"city":"Austin"}]'

        json_parser = JSONParser(schema=schema)

        for char in test_json:
            json_parser = json_parser.copy()
            done = json_parser._append(char)

        self.assertTrue(done)
