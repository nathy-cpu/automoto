from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse


class AuthenticationFlowTests(TestCase):
    def test_protected_dashboard_redirects_to_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_login_accepts_email_and_password(self):
        user = get_user_model().objects.create_user(
            email="owner@example.com", password="testpass123"
        )

        response = self.client.post(
            reverse("login"),
            {"username": user.email, "password": "testpass123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_logout_redirects_back_to_login(self):
        user = get_user_model().objects.create_user(
            email="owner@example.com", password="testpass123"
        )
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

    def test_authenticated_user_can_change_password(self):
        user = get_user_model().objects.create_user(
            email="owner@example.com", password="testpass123"
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "testpass123",
                "new_password1": "newpass12345",
                "new_password2": "newpass12345",
            },
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("password_change_done"))
        self.assertTrue(user.check_password("newpass12345"))

    def test_login_normalizes_email_case_and_spacing(self):
        user = get_user_model().objects.create_user(
            email="owner@example.com", password="testpass123"
        )

        response = self.client.post(
            reverse("login"),
            {"username": "  OWNER@example.com  ", "password": "testpass123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    @override_settings(LOGIN_RATE_LIMIT=2, LOGIN_RATE_WINDOW_SECONDS=60)
    def test_login_rate_limit_returns_429_after_repeated_attempts(self):
        for _ in range(2):
            response = self.client.post(
                reverse("login"),
                {"username": "owner@example.com", "password": "wrongpass"},
                REMOTE_ADDR="10.0.0.1",
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("login"),
            {"username": "owner@example.com", "password": "wrongpass"},
            REMOTE_ADDR="10.0.0.1",
        )

        self.assertEqual(response.status_code, 429)

    @override_settings(REQUEST_RATE_LIMIT=2, REQUEST_RATE_WINDOW_SECONDS=60)
    def test_request_rate_limit_returns_429_after_burst(self):
        for _ in range(2):
            response = self.client.get(reverse("login"), REMOTE_ADDR="10.0.0.2")
            self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("login"), REMOTE_ADDR="10.0.0.2")

        self.assertEqual(response.status_code, 429)


class SeedDemoDataCommandTests(TestCase):
    def test_seed_demo_data_creates_user_and_sample_records(self):
        call_command(
            "seed_demo_data",
            email="seed@example.com",
            password="seedpass123",
        )

        user = get_user_model().objects.get(email="seed@example.com")

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("seedpass123"))

        from job_scraper.models import CustomWebsite

        self.assertEqual(CustomWebsite.objects.filter(is_active=True).count(), 5)
