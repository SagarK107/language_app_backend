from django.contrib import admin

from .models import Course, Item, Lesson, UserActiveCourse

# Register your models here.


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    pass


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    pass


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    pass


@admin.register(UserActiveCourse)
class UserActiveCourseAdmin(admin.ModelAdmin):
    list_select_related = ["user", "course"]
