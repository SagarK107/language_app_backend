from rest_framework import serializers

from .models import Course, Lesson, UserActiveCourse


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
