import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Course, Item, Lesson, UserActiveCourse

PASSWORD = "Xk9!long-pass"


class LoadLessonTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            title="Marathi from English",
            source_language="English",
            target_language="Marathi",
        )
        self.data = {
            "course": "Marathi from English",
            "order": 1,
            "title": "Letters and Basics 1",
            "items": [
                {"kind": "character", "script": "अ", "transliteration": "a"},
                {
                    "kind": "word",
                    "script": "आई",
                    "transliteration": "aaii",
                    "meaning": "mother",
                },
            ],
        }

    def load(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lesson.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            call_command("load_lesson", path, verbosity=0)

    def test_creates_lesson_with_items_in_file_order(self):
        self.load(self.data)

        lesson = Lesson.objects.get(course=self.course, order=1)
        self.assertEqual(lesson.title, "Letters and Basics 1")
        self.assertEqual(
            list(lesson.items.values_list("order", "source_language_script")),
            [(1, "अ"), (2, "आई")],
        )
        self.assertEqual(lesson.items.get(order=2).meaning, "mother")

    def test_loading_twice_replaces_items_instead_of_duplicating(self):
        self.load(self.data)
        self.data["title"] = "First vowels"
        self.data["items"].pop()

        self.load(self.data)

        self.assertEqual(Lesson.objects.count(), 1)
        self.assertEqual(Lesson.objects.get().title, "First vowels")
        self.assertEqual(Item.objects.count(), 1)

    def test_invalid_item_leaves_existing_lesson_untouched(self):
        self.load(self.data)
        self.data["title"] = "Changed"
        self.data["items"][1]["kind"] = "not-a-kind"

        with self.assertRaises(CommandError):
            self.load(self.data)

        lesson = Lesson.objects.get()
        self.assertEqual(lesson.title, "Letters and Basics 1")
        self.assertEqual(lesson.items.count(), 2)

    def test_unknown_course_is_an_error(self):
        self.data["course"] = "No such course"

        with self.assertRaises(CommandError):
            self.load(self.data)


class CourseApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sagar", email="sagar@example.com", password=PASSWORD
        )
        # Created in reverse alphabetical order, so the list test proves the API sorts.
        self.hindi_course = Course.objects.create(
            title="Marathi from Hindi",
            source_language="Hindi",
            target_language="Marathi",
        )
        self.course = Course.objects.create(
            title="Marathi from English",
            source_language="English",
            target_language="Marathi",
        )
        # Lesson 2 is created before lesson 1, so the detail test proves the API sorts.
        self.lesson_2 = Lesson.objects.create(
            course=self.course, order=2, title="Letters and Basics 2"
        )
        self.lesson_1 = Lesson.objects.create(
            course=self.course, order=1, title="Letters and Basics 1"
        )

    def test_endpoints_require_login(self):
        requests = [
            ("get", "/api/courses/"),
            ("get", f"/api/courses/{self.course.id}/"),
            ("put", "/api/active-course/"),
        ]

        for method, url in requests:
            # subTest reports each URL separately instead of stopping at the first failure.
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)

                self.assertEqual(response.status_code, 403)

    def test_course_list_returns_all_courses_sorted_by_title(self):
        # Marks the request as coming from this user, without going through login.
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/courses/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.course.id,
                    "title": "Marathi from English",
                    "source_language": "English",
                    "target_language": "Marathi",
                },
                {
                    "id": self.hindi_course.id,
                    "title": "Marathi from Hindi",
                    "source_language": "Hindi",
                    "target_language": "Marathi",
                },
            ],
        )

    def test_course_detail_includes_lessons_in_order(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(f"/api/courses/{self.course.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": self.course.id,
                "title": "Marathi from English",
                "source_language": "English",
                "target_language": "Marathi",
                "lessons": [
                    {
                        "id": self.lesson_1.id,
                        "order": 1,
                        "title": "Letters and Basics 1",
                    },
                    {
                        "id": self.lesson_2.id,
                        "order": 2,
                        "title": "Letters and Basics 2",
                    },
                ],
            },
        )

    def test_course_detail_loads_lessons_in_one_query(self):
        self.client.force_authenticate(self.user)

        # One query for the course and one for all of its lessons. More than that
        # means the prefetch was lost and lessons are being loaded one at a time.
        with self.assertNumQueries(2):
            self.client.get(f"/api/courses/{self.course.id}/")

    def test_unknown_course_returns_404(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/courses/999/")

        self.assertEqual(response.status_code, 404)


class ActiveCourseTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sagar", email="sagar@example.com", password=PASSWORD
        )
        self.other_user = User.objects.create_user(
            username="other", email="other@example.com", password=PASSWORD
        )
        self.course = Course.objects.create(
            title="Marathi from English",
            source_language="English",
            target_language="Marathi",
        )
        self.hindi_course = Course.objects.create(
            title="Marathi from Hindi",
            source_language="Hindi",
            target_language="Marathi",
        )
        self.client.force_authenticate(self.user)

    def set_active_course(self, **body):
        return self.client.put("/api/active-course/", body, format="json")

    def test_put_sets_active_course(self):
        response = self.set_active_course(course=self.course.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"course": self.course.id})
        self.assertEqual(
            UserActiveCourse.objects.get(user=self.user).course, self.course
        )

    def test_second_put_changes_course_without_adding_a_row(self):
        self.set_active_course(course=self.course.id)

        response = self.set_active_course(course=self.hindi_course.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserActiveCourse.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            UserActiveCourse.objects.get(user=self.user).course, self.hindi_course
        )

    def test_unknown_course_is_rejected_and_nothing_is_saved(self):
        response = self.set_active_course(course=999)

        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.json())
        self.assertFalse(UserActiveCourse.objects.exists())

    def test_missing_course_is_rejected(self):
        response = self.set_active_course()

        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.json())

    def test_user_id_in_body_cannot_set_another_users_course(self):
        # The request is made by self.user but names other_user in the body.
        response = self.set_active_course(
            course=self.course.id, user=self.other_user.id
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserActiveCourse.objects.filter(user=self.user).exists())
        self.assertFalse(UserActiveCourse.objects.filter(user=self.other_user).exists())

    def test_me_reports_the_active_course_id(self):
        self.assertIsNone(self.client.get("/api/me/").json()["active_course"])

        # The second course is used on purpose: its id (2) differs from the id of the
        # UserActiveCourse row (1), so returning the wrong id cannot pass by accident.
        self.set_active_course(course=self.hindi_course.id)

        self.assertEqual(
            self.client.get("/api/me/").json()["active_course"], self.hindi_course.id
        )
