from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Course, UserActiveCourse
from .serializers import (
    ActiveCourseSerializer,
    CourseDetailSerializer,
    CourseSerializer,
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
