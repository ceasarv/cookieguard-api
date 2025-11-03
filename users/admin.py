from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


class UserAdmin(BaseUserAdmin):
	model = User
	list_display = ('email', 'is_staff', 'is_active', 'date_joined')
	list_filter = ('is_staff', 'is_active')
	search_fields = ('email',)
	ordering = ('-date_joined',)
	readonly_fields = ('date_joined', 'last_login')

	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Important dates', {'fields': ('last_login', 'date_joined')}),
		('Is Blocked', {'fields': 'is_blocked'}),
		('Permissions', {'fields': ('is_staff', 'is_active', 'groups', 'user_permissions')}),
	)
	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active'),
		}),
	)


admin.site.register(User, UserAdmin)
