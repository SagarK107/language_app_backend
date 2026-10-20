import json
import random
import tempfile
from pathlib import Path

from django.core import signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APITestCase

from accounts.models import User

from . import questions
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
            list(lesson.items.values_list("order", "text")),
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
            ("get", f"/api/lessons/{self.lesson_1.id}/"),
            ("get", f"/api/lessons/{self.lesson_1.id}/questions/"),
            ("post", f"/api/lessons/{self.lesson_1.id}/answer/"),
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


class LessonAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sagar", email="sagar@example.com", password=PASSWORD
        )
        self.course = Course.objects.create(
            title="Marathi from English",
            source_language="English",
            target_language="Marathi",
        )
        self.lesson = Lesson.objects.create(
            course=self.course, order=1, title="Letters and Basics 1"
        )
        # Created out of order, so the ordering test proves the API sorts the items.
        self.item_2 = Item.objects.create(
            lesson=self.lesson,
            order=2,
            kind="word",
            text="आई",
            transliteration="aaii",
            meaning="mother",
        )
        self.item_1 = Item.objects.create(
            lesson=self.lesson,
            order=1,
            kind="character",
            text="अ",
            transliteration="a",
            hint="The first vowel.",
        )
        self.client.force_authenticate(self.user)

    def test_unknown_lesson_returns_404(self):
        response = self.client.get("/api/lessons/999/")

        self.assertEqual(response.status_code, 404)

    def test_lesson_detail_includes_items_in_order(self):
        response = self.client.get(f"/api/lessons/{self.lesson.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": self.lesson.id,
                "course": self.course.id,
                "title": "Letters and Basics 1",
                "order": 1,
                "grammar_note": "",
                "items": [
                    {
                        "id": self.item_1.id,
                        "kind": "character",
                        "text": "अ",
                        "transliteration": "a",
                        "meaning": "",
                        "hint": "The first vowel.",
                        "order": 1,
                    },
                    {
                        "id": self.item_2.id,
                        "kind": "word",
                        "text": "आई",
                        "transliteration": "aaii",
                        "meaning": "mother",
                        "hint": "",
                        "order": 2,
                    },
                ],
            },
        )

    def test_lesson_detail_loads_items_in_one_query(self):
        # One query for the lesson and one for all of its items.
        with self.assertNumQueries(2):
            self.client.get(f"/api/lessons/{self.lesson.id}/")


def make_quiz_course():
    """Lesson 1 and 2 of a course, enough items that every question gets 4 options."""
    course = Course.objects.create(
        title="Marathi from English",
        source_language="English",
        target_language="Marathi",
    )
    lesson_1 = Lesson.objects.create(course=course, order=1, title="Lesson 1")
    lesson_2 = Lesson.objects.create(course=course, order=2, title="Lesson 2")
    characters = [
        ("अ", "a"),
        ("आ", "aa"),
        ("इ", "i"),
        ("ई", "ii"),
        ("उ", "u"),
        ("ऊ", "uu"),
    ]
    words = [
        ("आई", "aaii", "mother"),
        ("आंबा", "aambaa", "mango"),
        ("उशी", "ushii", "pillow"),
        ("ऊस", "uus", "sugarcane"),
    ]
    order = 1
    for text, transliteration in characters:
        Item.objects.create(
            lesson=lesson_1,
            order=order,
            kind="character",
            text=text,
            transliteration=transliteration,
        )
        order += 1
    for text, transliteration, meaning in words:
        Item.objects.create(
            lesson=lesson_1,
            order=order,
            kind="word",
            text=text,
            transliteration=transliteration,
            meaning=meaning,
        )
        order += 1
    Item.objects.create(
        lesson=lesson_2, order=1, kind="character", text="ए", transliteration="e"
    )
    return lesson_1, lesson_2


class BuildQuestionsTests(TestCase):
    def setUp(self):
        self.lesson_1, self.lesson_2 = make_quiz_course()

    def test_questions_are_well_formed_for_any_seed(self):
        lesson_item_ids = set(self.lesson_1.items.values_list("id", flat=True))

        for seed in range(10):
            with self.subTest(seed=seed):
                built = questions.build_questions(self.lesson_1, random.Random(seed))

                # One question per item of this lesson, and none from other lessons.
                self.assertEqual({q["item"].id for q in built}, lesson_item_ids)
                for question in built:
                    labels = [option["main"] for option in question["options"]]
                    self.assertEqual(len(labels), 4)
                    self.assertEqual(len(set(labels)), 4)
                    correct = question["options"][question["answer"]]
                    self.assertIn(correct["main"], vars(question["item"]).values())

    def test_same_seed_gives_same_questions(self):
        first = questions.build_questions(self.lesson_1, random.Random(1))
        second = questions.build_questions(self.lesson_1, random.Random(1))

        self.assertEqual(first, second)

    def test_later_lesson_uses_earlier_items_as_wrong_options(self):
        # Lesson 2 has a single character, so its wrong options must come from lesson 1.
        built = questions.build_questions(self.lesson_2, random.Random(0))

        self.assertEqual(len(built), 1)
        self.assertEqual(len(built[0]["options"]), 4)


class QuestionApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sagar", email="sagar@example.com", password=PASSWORD
        )
        self.lesson_1, self.lesson_2 = make_quiz_course()
        self.client.force_authenticate(self.user)

    def get_questions(self, lesson):
        return self.client.get(f"/api/lessons/{lesson.id}/questions/")

    def answer(self, lesson, **body):
        return self.client.post(
            f"/api/lessons/{lesson.id}/answer/", body, format="json"
        )

    def make_token(self, lesson, answer):
        """A real token whose answer the test knows, since the API never reveals it."""
        item = lesson.items.first()
        return signing.dumps(
            {"lesson": lesson.id, "item": item.id, "answer": answer},
            salt=questions.ANSWER_TOKEN_SALT,
        )

    def test_unknown_lesson_returns_404(self):
        self.assertEqual(
            self.client.get("/api/lessons/999/questions/").status_code, 404
        )

    def test_questions_do_not_reveal_the_answer(self):
        response = self.get_questions(self.lesson_1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 10)
        for question in response.json():
            self.assertEqual(set(question), {"token", "type", "prompt", "options"})

    def test_questions_load_in_two_queries(self):
        # One for the lesson and one for every candidate item.
        with self.assertNumQueries(2):
            self.get_questions(self.lesson_1)

    def test_token_from_the_questions_endpoint_can_be_answered(self):
        token = self.get_questions(self.lesson_1).json()[0]["token"]

        response = self.answer(self.lesson_1, token=token, choice=0)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"correct", "correct_choice"})

    def test_correct_choice(self):
        token = self.make_token(self.lesson_1, answer=2)

        response = self.answer(self.lesson_1, token=token, choice=2)

        self.assertEqual(response.json(), {"correct": True, "correct_choice": 2})

    def test_wrong_choice_reports_the_correct_one(self):
        token = self.make_token(self.lesson_1, answer=2)

        response = self.answer(self.lesson_1, token=token, choice=0)

        self.assertEqual(response.json(), {"correct": False, "correct_choice": 2})

    def test_tampered_token_is_rejected(self):
        token = self.make_token(self.lesson_1, answer=2)
        # Change one character of the signature at the end.
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

        response = self.answer(self.lesson_1, token=tampered, choice=2)

        self.assertEqual(response.status_code, 400)
        self.assertIn("token", response.json())

    def test_token_signed_with_another_salt_is_rejected(self):
        token = signing.dumps({"lesson": self.lesson_1.id, "item": 1, "answer": 0})

        response = self.answer(self.lesson_1, token=token, choice=0)

        self.assertEqual(response.status_code, 400)

    def test_token_from_another_lesson_is_rejected(self):
        token = self.make_token(self.lesson_1, answer=2)

        response = self.answer(self.lesson_2, token=token, choice=2)

        self.assertEqual(response.status_code, 400)

    def test_choice_out_of_range_is_rejected(self):
        token = self.make_token(self.lesson_1, answer=2)

        for choice in (-1, 4):
            with self.subTest(choice=choice):
                response = self.answer(self.lesson_1, token=token, choice=choice)

                self.assertEqual(response.status_code, 400)
                self.assertIn("choice", response.json())
