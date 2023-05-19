import unittest
from scs.incremental_parse.json import JSONParser, StringParser, NumberParser, ObjectParser, ArrayParser, SpecialToken, ParseFailure
from scs.constraint.json import valid_json


class TestJSONParser(unittest.TestCase):

    def test_parse_object(self):
        parser = ObjectParser()
        test_data = '{"name":"John Smith","age":35,"city":"New York"}'
        for char in test_data[1:]:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_nested_objects(self):
        parser = ObjectParser()
        test_data = '{"person":{"name":"John Smith","age":35,"city":"New York"}}'
        for char in test_data[1:]:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_array(self):
        parser = ArrayParser()
        test_data = '["apple","banana","cherry"]'
        for char in test_data[1:]:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_nested_arrays(self):
        parser = ArrayParser()
        test_data = '[["apple","banana"],["cherry","orange"]]'
        for char in test_data[1:]:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_string(self):
        parser = StringParser()
        test_data = '"Hello, world!"'
        for char in test_data[1:]:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_number(self):
        parser = NumberParser()
        test_data = '42'
        for char in test_data:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_float(self):
        parser = NumberParser()
        test_data = '3.14'
        for char in test_data:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_invalid_number(self):
        parser = NumberParser()
        test_data = '3.14.159'
        with self.assertRaises(ParseFailure):
            for char in test_data:
                parser.append(char)

    def test_parse_leading_zero_integer(self):
        parser = NumberParser()
        test_data = '01234'
        with self.assertRaises(ParseFailure):
            for char in test_data:
                parser.append(char)

    def test_parse_leading_period(self):
        parser = NumberParser()
        test_data = '.01234'
        with self.assertRaises(ParseFailure):
            for char in test_data:
                parser.append(char)

    def test_parse_invalid_object(self):
        parser = ObjectParser()
        test_data = '{"name":"John Smith","age":35"city":"New York"}' # no ',' after '35'
        with self.assertRaises(ParseFailure):
            for char in test_data[1:]:
                parser.append(char)

    def test_parse_invalid_array(self):
        parser = ArrayParser()
        test_data = '["a""b"]'
        with self.assertRaises(ParseFailure):
            for char in test_data[1:]:
                parser.append(char)

    def test_parse_object_with_spaces(self):
        parser = ObjectParser()
        test_data = '{"name": "John Smith", "age": 35, "city": "New York"}' # no ',' after '35'
        with self.assertRaises(ParseFailure):
            for char in test_data[1:]:
                parser.append(char)

    def test_parse_array_with_spaces(self):
        parser = ArrayParser()
        test_data = '["a", "b"]'
        with self.assertRaises(ParseFailure):
            for char in test_data[1:]:
                parser.append(char)

    def test_parse_empty_object(self):
        parser = ObjectParser()
        test_data = '{}'
        for char in test_data[1:]:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_empty_array(self):
        parser = ArrayParser()
        test_data = '[]'
        for char in test_data[1:]:
            parser.append(char)
        self.assertEqual(parser._parsed, test_data)

    def test_parse_object_with_eos(self):
        parser = JSONParser()
        test_data = list('{"name":"John Smith","age":35,"city":"New York"}') + [SpecialToken.EOS]
        parser.append(test_data)

    def test_parse_array_with_eos(self):
        parser = JSONParser()
        test_data = list('["apple","banana","cherry"]') + [SpecialToken.EOS]
        parser.append(test_data)

    def test_parse_object_with_extra(self):
        parser = JSONParser()
        test_data = list('{"name":"John Smith","age": 35,"city":"New York"}') + list("extra data")
        with self.assertRaises(ParseFailure):
            parser.append(test_data)

    def test_parse_array_with_extra(self):
        parser = JSONParser()
        test_data = list('["apple","banana","cherry"]') + list("extra data")
        with self.assertRaises(ParseFailure):
            parser.append(test_data)

    def test_parse_object_with_space_after_number(self):
        parser = JSONParser()
        test_data = list('{"name":"John Smith","age":35]')
        with self.assertRaises(ParseFailure):
            parser.append(test_data)

    def test_parse_invalid_array_close_after_number(self):
        parser = JSONParser()
        test_data = list('[35}')
        with self.assertRaises(ParseFailure):
            parser.append(test_data)

    def test_disallow_empty_object(self):
        parser = JSONParser(allow_empty=False)
        test_data = list('{}')
        with self.assertRaises(ParseFailure):
            parser.append(test_data)

    def test_disallow_empty_array(self):
        parser = JSONParser(allow_empty=False)
        test_data = list('[]')
        with self.assertRaises(ParseFailure):
            parser.append(test_data)

    def test_disallow_empty_object_child(self):
        parser = JSONParser(allow_empty_children=False)
        test_data = list('{"a":[]}')
        with self.assertRaises(ParseFailure):
            parser.append(test_data)

    def test_disallow_empty_array_child(self):
        parser = JSONParser(allow_empty_children=False)
        test_data = list('[[]]')
        with self.assertRaises(ParseFailure):
            parser.append(test_data)


class TestJSONConstraint(unittest.TestCase):

    def test_update_parser(self):
        test_data = '{"name":"John Smith","ag', 'e":35,"city":"New York"}'
        constraint = valid_json()
        constraint.update_parser(test_data[0])
        self.assertEqual(constraint.parser.get_parsed(), test_data[0])

    def test_check_next(self):
        test_data = '{"name":"John Smith","ag', 'e":35,"city":"New York"}'
        constraint = valid_json()
        constraint.update_parser(test_data[0])
        self.assertTrue(constraint.check_next(test_data[1]))
        self.assertEqual(constraint.parser.get_parsed(), test_data[0])

    def test_check_next_invalid(self):
        test_data = 'invalid'
        constraint = valid_json()
        self.assertFalse(constraint.check_next(test_data))

    def test_check_next_with_extra(self):
        test_data = '{}', 'extra data'
        constraint = valid_json()
        constraint.update_parser(test_data[0])
        self.assertFalse(constraint.check_next(test_data[1]))

    def test_check_next_with_eos(self):
        test_data = '{}', [SpecialToken.EOS]
        constraint = valid_json()
        constraint.update_parser(test_data[0])
        self.assertTrue(constraint.check_next(test_data[1]))

    def test_check_next_start_with_eos(self):
        test_data = [SpecialToken.EOS]
        constraint = valid_json()
        self.assertFalse(constraint.check_next(test_data))

    def test_check_next_close_object_after_number(self):
        test_data = '[50]\n\n," and "\n\n," which are also used in the other'
        constraint = valid_json()
        self.assertFalse(constraint.check_next(test_data))

    def test_check_next_close_array_after_number(self):
        test_data = '{"a": 50}\n\n," and "\n\n," which are also used in the other'
        constraint = valid_json()
        self.assertFalse(constraint.check_next(test_data))

    def test_check_next_empty_string(self):
        test_data = ''
        constraint = valid_json()
        self.assertFalse(constraint.check_next(test_data))

    def test_check_next_eos_when_incomplete(self):
        test_data = '{', [SpecialToken.EOS]
        constraint = valid_json()
        constraint.update_parser(test_data[0])
        self.assertFalse(constraint.check_next(test_data[1]))

    def test_check_next_allow_whitespace(self):
        test_data = '{"name": "Barbara"}'
        constraint = valid_json(allow_whitespace_formatting=True)
        self.assertTrue(constraint.check_next(test_data))

        test_data = '["Barbara", "Alex"]'
        constraint = valid_json(allow_whitespace_formatting=True)
        self.assertTrue(constraint.check_next(test_data))

    def test_check_next_disallow_whitespace(self):
        test_data = '{"name":  "Barbara"}'
        constraint = valid_json()
        self.assertFalse(constraint.check_next(test_data))

        test_data = '["Barbara",  "Alex"]'
        constraint = valid_json()
        self.assertFalse(constraint.check_next(test_data))

    def test_disallow_array_in_outer_json(self):
        test_data = '[[]]'
        constraint = valid_json(allow_outer_list=False)
        self.assertFalse(constraint.check_next(test_data))
    

if __name__ == '__main__':
    unittest.main()
