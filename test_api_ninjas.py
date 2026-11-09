import unittest
from unittest.mock import patch

from api_ninjas import APINinjasClient


class APINinjasCredentialTests(unittest.TestCase):
    def test_constructor_trims_surrounding_credential_whitespace(self):
        with patch.dict("os.environ", {"API_NINJAS_API_KEY": "  test-key-value\n"}):
            client = APINinjasClient()
        try:
            self.assertEqual(client.api_key, "test-key-value")
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
