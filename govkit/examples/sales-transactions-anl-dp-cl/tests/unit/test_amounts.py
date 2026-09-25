import unittest

from shared.libraries.amounts import net_amount


class TestNetAmount(unittest.TestCase):
    def test_discount_applied(self):
        self.assertEqual(net_amount(1000.0, 150.0), 850.0)

    def test_missing_discount(self):
        self.assertEqual(net_amount(1000.0, None), 1000.0)
