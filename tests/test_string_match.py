import unittest
from scs.incremental_parse.string_match import StringMatchParser, MultiStringMatchParser
from scs.incremental_parse import SpecialToken, ParseFailure

class TestStringMatchParser(unittest.TestCase):

    def test_match_success(self):
        parser = StringMatchParser("hello")
        self.assertFalse(parser._append("h"))
        self.assertFalse(parser._append("e"))
        self.assertFalse(parser._append("l"))
        self.assertFalse(parser._append("l"))
        self.assertTrue(parser._append("o"))
        self.assertTrue(parser._append(SpecialToken.EOS))

    def test_match_failure(self):
        parser = StringMatchParser("hello")
        with self.assertRaises(ParseFailure):
            parser._append("h")
            parser._append("e")
            parser._append("l")
            parser._append("l")
            parser._append("x")  # Mismatched character

    def test_match_nocase(self):
        parser = StringMatchParser("hello", nocase=True)
        parser._append("H")


class TestMultiStringMatchParser(unittest.TestCase):

    def test_match_success(self):
        parser = MultiStringMatchParser(["hello", "hello world"])
        self.assertFalse(parser._append("h"))
        self.assertFalse(parser._append("e"))
        self.assertFalse(parser._append("l"))
        self.assertFalse(parser._append("l"))
        self.assertTrue(parser._append("o"))  # First match completed, second match ongoing
        self.assertFalse(parser._append(" "))
        self.assertFalse(parser._append("w"))
        with self.assertRaises(ParseFailure):
            self.assertFalse(parser._append("x"))  # Second match failed

    def test_match_failure(self):
        parser = MultiStringMatchParser(["hello", "world"])
        with self.assertRaises(ParseFailure):
            parser._append("h")
            parser._append("e")
            parser._append("l")
            parser._append("l")
            parser._append("x")  # First match failed

    def test_invalid_mixed_string(self):
        parser = MultiStringMatchParser(["George", "Isaac"])
        test_data = "IGsaeoac"
        with self.assertRaises(ParseFailure):
            parser.append(test_data)


if __name__ == '__main__':
    unittest.main()