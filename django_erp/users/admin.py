from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from .models import User
from unfold.admin import ModelAdmin


@admin.register(User)
class CustomAdminClass(ModelAdmin):
    pass


