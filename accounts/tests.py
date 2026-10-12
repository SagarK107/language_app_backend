from rest_framework.test import APITestCase

from .models import User

PASSWORD = "Xk9!long-pass"


class SignupTests(APITestCase):
    def signup(self, **overrides):
        data = {"username": "sagar", "email": "sagar@example.com", "password": PASSWORD}
        data.update(overrides)
        return self.client.post("/api/signup/", data, format="json")

    def test_signup_creates_user_and_logs_in(self):
        response = self.signup()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data,
            {
                "id": response.data["id"],
                "username": "sagar",
                "email": "sagar@example.com",
            },
        )
        self.assertNotIn("password", response.data)
        self.assertEqual(self.client.get("/api/me/").status_code, 200)

    def test_signup_hashes_password(self):
        self.signup()

        user = User.objects.get(username="sagar")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_signup_lowercases_email(self):
        self.signup(email="Sagar@Example.COM")

        self.assertTrue(User.objects.filter(email="sagar@example.com").exists())

    def test_signup_rejects_duplicate_email_in_any_case(self):
        self.signup()

        response = self.signup(username="other", email="SAGAR@example.com")

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_signup_rejects_at_sign_in_username(self):
        response = self.signup(username="sagar@home")

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)

    def test_signup_rejects_weak_password(self):
        response = self.signup(password="123")

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.exists())


class LoginTests(APITestCase):
    def setUp(self):
        User.objects.create_user(
            username="sagar", email="sagar@example.com", password=PASSWORD
        )

    def login(self, username, password=PASSWORD):
        return self.client.post(
            "/api/login/", {"username": username, "password": password}, format="json"
        )

    def test_login_with_username(self):
        response = self.login("sagar")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "sagar")
        self.assertEqual(self.client.get("/api/me/").status_code, 200)

    def test_login_with_email_is_case_insensitive(self):
        response = self.login("Sagar@Example.com")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "sagar")

    def test_login_wrong_password_returns_401(self):
        response = self.login("sagar", password="wrong-password")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get("/api/me/").status_code, 403)

    def test_login_unknown_email_returns_401(self):
        response = self.login("nobody@example.com")

        self.assertEqual(response.status_code, 401)

    def test_inactive_user_cannot_login(self):
        User.objects.filter(username="sagar").update(is_active=False)

        response = self.login("sagar")

        self.assertEqual(response.status_code, 401)


class SessionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sagar", email="sagar@example.com", password=PASSWORD
        )

    def test_me_requires_authentication(self):
        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 403)

    def test_me_returns_current_user(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/me/")

        self.assertEqual(
            response.data,
            {
                "id": self.user.id,
                "username": "sagar",
                "email": "sagar@example.com",
                "active_course": None,
            },
        )

    def test_logout_ends_session(self):
        self.client.post(
            "/api/login/", {"username": "sagar", "password": PASSWORD}, format="json"
        )

        response = self.client.post("/api/logout/")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/me/").status_code, 403)
