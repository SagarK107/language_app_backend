from django.urls import path

from . import views

urlpatterns = [
    path("courses/", views.CoursesView.as_view()),
    path("courses/<int:pk>/", views.CourseDetailView.as_view()),
    path("active-course/", views.ActiveCourseView.as_view()),
]
