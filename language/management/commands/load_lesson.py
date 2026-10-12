import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from language.models import Course, Item, Lesson


class Command(BaseCommand):
    help = "Load one lesson and its items from a JSON content file."

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path, help="Path to the lesson JSON file")

    def handle(self, *args, **options):
        data = self.read_file(options["path"])

        try:
            course = Course.objects.get(title=data["course"])
        except Course.DoesNotExist as error:
            raise CommandError(f'Course "{data["course"]}" does not exist') from error

        # All or nothing: one bad item leaves the lesson exactly as it was.
        with transaction.atomic():
            lesson, created = Lesson.objects.update_or_create(
                course=course,
                order=data["order"],
                defaults={
                    "title": data["title"],
                    "grammar_note": data.get("grammar_note", ""),
                },
            )
            lesson.full_clean()

            # Replace the items, so loading the same file twice gives the same result.
            lesson.items.all().delete()
            for position, entry in enumerate(data["items"], start=1):
                self.create_item(lesson, position, entry)

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} {lesson} ({len(data['items'])} items)")
        )

    def read_file(self, path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CommandError(f"File not found: {path}") from error
        except json.JSONDecodeError as error:
            raise CommandError(f"{path} is not valid JSON: {error}") from error

    def create_item(self, lesson, position, entry):
        try:
            item = Item(
                lesson=lesson,
                order=position,
                kind=entry["kind"],
                source_language_script=entry["script"],
                target_language_transliteration=entry["transliteration"],
                meaning=entry.get("meaning", ""),
                hint=entry.get("hint", ""),
            )
            item.full_clean()
        except KeyError as error:
            raise CommandError(f"Item {position} is missing {error}") from error
        except ValidationError as error:
            raise CommandError(
                f"Item {position} is invalid: {error.message_dict}"
            ) from error
        item.save()
