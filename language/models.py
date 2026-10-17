from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager


class Kind(models.TextChoices):
    CHARACTER = "character", "Character"
    WORD = "word", "Word"
    SENTENCE = "sentence", "Sentence"


# Create your models here.


class Course(models.Model):
    title = models.CharField(max_length=100, unique=True)
    source_language = models.CharField(max_length=50)
    target_language = models.CharField(max_length=50)

    # Reverse side of Lesson.course (related_name="lessons"), declared for type checkers.
    lessons: RelatedManager[Lesson]

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    grammar_note = models.TextField(blank=True)

    # Reverse side of Item.lesson (related_name="items"), declared for type checkers.
    items: RelatedManager[Item]

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "order"], name="course_order_constraint"
            )
        ]

    def __str__(self):
        return f"Lesson {self.order} : {self.title}"


class Item(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=15, choices=Kind.choices)
    # The item in the target language's own script, e.g. "आई".
    text = models.CharField(max_length=200)
    # How `text` is written in the learner's script, e.g. "aaii".
    transliteration = models.CharField(max_length=200)
    meaning = models.CharField(max_length=200, blank=True)
    hint = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "order"], name="lesson_order_constraint"
            )
        ]

    def __str__(self):
        return f"{self.text} ({self.transliteration}) - {self.kind}"


class UserActiveCourse(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="active_course"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="active_users",
    )

    def __str__(self):
        return f"User {self.user} -> {self.course}"
