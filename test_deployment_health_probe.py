import unittest

from deployment_health_probe import classify_probe_response


class DeploymentHealthProbeTests(unittest.TestCase):
    def test_http_200_ok_confirms_health(self):
        report = classify_probe_response(200, body="ok")
        self.assertEqual(report["deployment_health"], "healthy")
        self.assertTrue(report["health_endpoint_confirmed"])
        self.assertTrue(report["healthy"])

    def test_streamlit_auth_redirect_is_protected_and_reachable(self):
        report = classify_probe_response(
            303,
            redirect_location=(
                "https://share.streamlit.io/-/auth/app?"
                "redirect_uri=https%3A%2F%2Fexample.streamlit.app%2F_stcore%2Fhealth"
            ),
        )
        self.assertEqual(report["deployment_health"], "protected_reachable")
        self.assertEqual(report["application_status"], "authentication_required")
        self.assertEqual(report["authentication"], "required")
        self.assertTrue(report["deployment_reachable"])
        self.assertIsNone(report["healthy"])
        self.assertFalse(report["health_endpoint_confirmed"])

    def test_unauthorized_or_forbidden_response_is_protected(self):
        for status in (401, 403):
            with self.subTest(status=status):
                report = classify_probe_response(status)
                self.assertEqual(report["deployment_health"], "protected_reachable")
                self.assertTrue(report["deployment_reachable"])

    def test_server_error_is_degraded(self):
        report = classify_probe_response(503)
        self.assertEqual(report["deployment_health"], "degraded")
        self.assertFalse(report["healthy"])
        self.assertEqual(report["error"], "HTTP 503")

    def test_unexpected_non_server_response_remains_unverified(self):
        report = classify_probe_response(404, body="not found")
        self.assertEqual(report["deployment_health"], "reachable_unverified")
        self.assertTrue(report["deployment_reachable"])
        self.assertIsNone(report["healthy"])


if __name__ == "__main__":
    unittest.main()
