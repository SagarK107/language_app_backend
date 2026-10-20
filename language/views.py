import random

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import questions
from .models import Course, Lesson, UserActiveCourse
from .serializers import (
    ActiveCourseSerializer,
    AnswerSerializer,
    CourseDetailSerializer,
    CourseSerializer,
    LessonDetailSerializer,
)

# Create your views here.


class CoursesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Course.objects.all()
    serializer_class = CourseSerializer


class CourseDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CourseDetailSerializer
    queryset = Course.objects.prefetch_related("lessons")


class ActiveCourseView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = ActiveCourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = serializer.validated_data["course"]
        active_course, created = UserActiveCourse.objects.update_or_create(
            user=request.user, defaults={"course": course}
        )

        return Response(ActiveCourseSerializer(active_course).data)


class LessonDetailView(generics.RetrieveAPIView):
    queryset = Lesson.objects.prefetch_related("items")
    permission_classes = [IsAuthenticated]
    serializer_class = LessonDetailSerializer


class LessonQuestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        lesson = get_object_or_404(Lesson, pk=pk)
        # Quiz shuffling, not security: the answers are protected by the signed token.
        rng = random.Random()  # noqa: S311
        built = questions.build_questions(lesson, rng)
        return Response([questions.public_question(q, lesson) for q in built])


class LessonAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = AnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = questions.check_answer(
                serializer.validated_data["token"],
                pk,
                serializer.validated_data["choice"],
            )
        except questions.InvalidTokenError:
            return Response(
                {"token": ["Invalid or expired question token."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)
