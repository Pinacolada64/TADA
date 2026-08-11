import unittest
from unittest.mock import MagicMock, patch

from bar.charisma import charisma_check, charisma_tier
from base_classes import PlayerStat


def _player(chr_=None):
    p = MagicMock()
    p.stats = {} if chr_ is None else {PlayerStat.CHR: chr_}
    return p


class TestCharismaTier(unittest.TestCase):

    def test_low_tier(self):
        self.assertEqual(charisma_tier(_player(3)), 'low')
        self.assertEqual(charisma_tier(_player(8)), 'low')

    def test_mid_tier(self):
        self.assertEqual(charisma_tier(_player(9)), 'mid')
        self.assertEqual(charisma_tier(_player(15)), 'mid')

    def test_high_tier(self):
        self.assertEqual(charisma_tier(_player(16)), 'high')
        self.assertEqual(charisma_tier(_player(18)), 'high')

    def test_missing_stat_key_defaults_to_low_tier(self):
        # A character created before Charisma was added to the roll --
        # get_stat()-style missing key should read as CHR=0, not crash.
        self.assertEqual(charisma_tier(_player(None)), 'low')

    def test_non_dict_stats_does_not_raise(self):
        p = MagicMock()
        p.stats = MagicMock()  # unconfigured MagicMock, as in many test fixtures
        self.assertEqual(charisma_tier(p), 'low')


class TestCharismaCheck(unittest.TestCase):

    def test_high_charisma_beats_low_dc(self):
        with patch('random.randint', return_value=10):
            self.assertTrue(charisma_check(_player(18), dc=10))

    def test_low_charisma_fails_high_dc(self):
        with patch('random.randint', return_value=10):
            self.assertFalse(charisma_check(_player(3), dc=15))

    def test_average_charisma_breaks_even_on_natural_roll(self):
        with patch('random.randint', return_value=10):
            self.assertTrue(charisma_check(_player(10), dc=10))


if __name__ == '__main__':
    unittest.main()
