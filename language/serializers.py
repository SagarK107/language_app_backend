from rest_framework import serializers

from .models import Course, Item, Lesson, UserActiveCourse


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "title", "source_language", "target_language"]


class LessonSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ["id", "order", "title"]


class CourseDetailSerializer(serializers.ModelSerializer):
    lessons = LessonSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = ["id", "title", "source_language", "target_language", "lessons"]


class ActiveCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActiveCourse
        fields = ["course"]


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "kind", "text", "transliteration", "meaning", "hint", "order"]


class AnswerSerializer(serializers.Serializer):
    """Input for POST /lessons/<id>/answer/. Not a ModelSerializer: nothing is saved."""

    token = serializers.CharField()
    choice = serializers.IntegerField(min_value=0, max_value=3)


class LessonDetailSerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = ["id", "course", "title", "order", "grammar_note", "items"]
