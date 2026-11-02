import unittest

from scripts import qadbkey


class QADBKeyTests(unittest.TestCase):
    def test_published_interoperability_vectors(self):
        for challenge, expected in {"12345678": "0jXKXQwSwMxYoeg",
                                    "15478726": "n9Qq0s1x4LtgAvt",
                                    "31711264": "SV3LHz1ynUZZmYU"}.items():
            self.assertEqual(qadbkey.derive(challenge), expected)

    def test_no_injection_unknown_format_or_ambiguous_challenge(self):
        for value in ("1234", "12345678\nAT+CFUN=1,1", "P1KR27_13_27_17", None):
            with self.assertRaises(ValueError):
                qadbkey.derive(value)
        for reply in ("+QADBKEY: 12345678", "+QADBKEY: 12345678\nERROR\nOK",
                      "+QADBKEY: 12345678\n+QADBKEY: 87654321\nOK",
                      "+QADBKEY: unknown\nOK"):
            with self.assertRaises(ValueError) as error:
                qadbkey.parse_challenge(reply)
            self.assertNotIn("12345678", str(error.exception))

    def test_query_echo_and_unsolicited_lines_do_not_become_challenge(self):
        self.assertEqual(qadbkey.parse_challenge(
            "AT+QADBKEY?\r\n+QIND: READY\r\n+QADBKEY: 12345678\r\nOK\r\n"), "12345678")
