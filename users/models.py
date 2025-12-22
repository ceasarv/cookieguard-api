from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid
import secrets


class UserManager(BaseUserManager):
	def create_user(self, email, password=None, **extra_fields):
		if not email:
			raise ValueError('The Email field is required')
		email = self.normalize_email(email)
		user = self.model(email=email, **extra_fields)
		user.set_password(password)
		user.save()
		return user

	def create_superuser(self, email, password=None, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	email = models.EmailField(unique=True)
	is_active = models.BooleanField(default=True)
	is_staff = models.BooleanField(default=False)
	date_joined = models.DateTimeField(default=timezone.now, editable=False)
	on_boarding_step = models.SmallIntegerField(default=0)
	is_blocked = models.BooleanField(default=False, help_text="Block account and disable access to all services.")

	objects = UserManager()

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = []

	def __str__(self):
		return self.email


class Team(models.Model):
	"""
	Team for Agency plan users to collaborate with team members.
	Each Agency user can have one team with up to 3 members.
	"""
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	owner = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='owned_team',
	)
	name = models.CharField(max_length=100, default="My Team")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.name} (owner: {self.owner.email})"

	@property
	def member_count(self):
		return self.members.count()


class TeamMember(models.Model):
	"""
	Team membership for Agency plan collaboration.
	All members have admin access (full CRUD on domains/banners).
	"""
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='team_memberships',
	)
	role = models.CharField(max_length=20, default='admin')  # All admins for now
	invited_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ['team', 'user']

	def __str__(self):
		return f"{self.user.email} in {self.team.name}"


class TeamInvite(models.Model):
	"""
	Pending team invitation for Agency plan users.
	"""
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='invites')
	email = models.EmailField()
	token = models.CharField(max_length=64, unique=True)
	created_at = models.DateTimeField(auto_now_add=True)
	expires_at = models.DateTimeField()
	accepted = models.BooleanField(default=False)

	class Meta:
		unique_together = ['team', 'email']

	def save(self, *args, **kwargs):
		if not self.token:
			self.token = secrets.token_urlsafe(48)
		if not self.expires_at:
			self.expires_at = timezone.now() + timezone.timedelta(days=7)
		super().save(*args, **kwargs)

	def __str__(self):
		return f"Invite to {self.email} for {self.team.name}"

	@property
	def is_expired(self):
		return timezone.now() > self.expires_at
