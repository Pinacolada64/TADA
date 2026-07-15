# language: python
#!/usr/bin/env python3
import re
import unittest

from base_classes import Combination, CombinationTypes


class TestCombination(unittest.TestCase):
    def test_random_combination_properties_and_str(self):
        c = Combination(CombinationTypes.CASTLE)
        self.assertIsInstance(c.combination, tuple)
        self.assertEqual(len(c.combination), 3)
        for n in c.combination:
            self.assertGreaterEqual(n, 1)
            self.assertLessEqual(n, 99)

        s = str(c)
        m = re.search(r'(\d{1,2})-(\d{1,2})-(\d{1,2})$', s)
        self.assertIsNotNone(m)
        parsed = tuple(int(x) for x in m.groups())
        self.assertEqual(parsed, c.combination)

    def test_has_single_digit(self):
        c = Combination(CombinationTypes.CASTLE)
        c.combination = (1, 12, 33)
        self.assertTrue(c.has_single_digit)

        c.combination = (11, 12, 33)
        self.assertFalse(c.has_single_digit)

    def test_from_string_valid_and_name(self):
        c = Combination.from_string("08-72-49", CombinationTypes.LOCKER)
        self.assertIsNotNone(c)
        self.assertEqual(c.combination, (8, 72, 49))
        self.assertEqual(c.name, CombinationTypes.LOCKER)

    def test_from_string_various_delimiters(self):
        cases = ["8 72 49", "8.72.49", "08-72-49", "08 - 72 -49"]
        for s in cases:
            with self.subTest(s=s):
                c = Combination.from_string(s)
                self.assertIsNotNone(c)
                self.assertEqual(c.combination, (8, 72, 49))

    def test_from_string_invalid_inputs(self):
        self.assertIsNone(Combination.from_string("8-72"))
        self.assertIsNone(Combination.from_string("0-1-2"))      # 0 out of allowed range
        self.assertIsNone(Combination.from_string("100-1-2"))    # >99 out of allowed range
        self.assertIsNone(Combination.from_string("a-b-c"))

    def test_valid_combination(self):
        c = Combination(CombinationTypes.CASTLE)
        c.combination = (10, 20, 30)
        self.assertTrue(c.valid_combination((10, 20, 30)))
        self.assertFalse(c.valid_combination((1, 2, 3)))


if __name__ == "__main__":
    unittest.main()
