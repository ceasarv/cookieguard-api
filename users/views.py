from typing import Optional
import base64, json, logging, time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.utils.text import slugify
from django.db import transaction
from django.db.models import F
from django.utils.timezone import now

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

import google.oauth2.id_token
import google.auth.transport.requests
from google.auth.exceptions import InvalidValue as GoogleInvalidValue

User = get_user_model()
log = logging.getLogger(__name__)


# ---------- helpers ----------

def has_field(model, name: str) -> bool:
	try:
		model._meta.get_field(name)
		return True
	except FieldDoesNotExist:
		return False


def unique_username_from_email(email: str, sub: Optional[str] = None) -> str:
	if not has_field(User, "username"):
		return slugify(email.split("@")[0])[:30] or "user"
	base = slugify(email.split("@")[0])[:30] or "user"
	username = base
	i = 1
	while User.objects.filter(username=username).exists():
		suffix = (sub or str(i))[:6]
		username = f"{base}-{suffix}"
		i += 1
	return username


def tokens_for(user):
	r = RefreshToken.for_user(user)
	return {"access": str(r.access_token), "refresh": str(r)}


def _peek_jwt_payload(idt: str) -> dict:
	try:
		_, payload, _ = idt.split(".")
		pad = "=" * (-len(payload) % 4)
		return json.loads(base64.urlsafe_b64decode(payload + pad).decode())
	except Exception:
		return {}


def _serialize_user(user):
	name = (
			getattr(user, "name", None)
			or f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
			or "User"
	)
	return {
		"id": str(user.id),
		"email": user.email,
		"name": name,
		"on_boarding_step": getattr(user, "on_boarding_step", 0),
		"avatar_url": getattr(user, "avatar_url", None),
	}


# ---------- views ----------

@api_view(["POST"])
def onboarding_next(request):
	if not has_field(User, "on_boarding_step"):
		return Response({"detail": "User model has no 'on_boarding_step' field."}, status=400)

	user = request.user
	expected = request.data.get("expected", None)
	max_step = request.data.get("max_step", None)

	with transaction.atomic():
		qs = User.objects.select_for_update().filter(pk=user.pk)

		if max_step is not None:
			user = qs.first()
			if user.on_boarding_step >= int(max_step):
				return Response({"on_boarding_step": user.on_boarding_step, "advanced": False})

		if expected is not None:
			qs = qs.filter(on_boarding_step=int(expected))

		updated = qs.update(on_boarding_step=F("on_boarding_step") + 1)
		user.refresh_from_db(fields=["on_boarding_step"])

	return Response({"on_boarding_step": user.on_boarding_step, "advanced": bool(updated)})


@api_view(["GET", "PATCH"])
def me(request):
	user = request.user

	if request.method == "GET":
		return Response(_serialize_user(user))

	# PATCH — allow a few safe fields (on_boarding_step, and optional name-ish fields if they exist)
	updates = {}

	if "on_boarding_step" in request.data:
		try:
			step = int(request.data.get("on_boarding_step"))
		except (TypeError, ValueError):
			return Response({"on_boarding_step": ["Must be an integer."]}, status=400)
		if step < 0:
			return Response({"on_boarding_step": ["Must be >= 0."]}, status=400)
		updates["on_boarding_step"] = step

	# These only apply if your model actually has them.
	for fld in ("name", "first_name", "last_name", "avatar_url"):
		if fld in request.data:
			if not has_field(User, fld):
				return Response({fld: ["This field cannot be updated."]}, status=400)
			val = request.data.get(fld)
			if isinstance(val, str):
				val = val.strip()
			updates[fld] = val

	if not updates:
		return Response({"detail": "No valid fields to update."}, status=400)

	for k, v in updates.items():
		setattr(user, k, v)
	user.save(update_fields=list(updates.keys()))

	return Response(_serialize_user(user))


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
	from .serializers import RegisterSerializer
	serializer = RegisterSerializer(data=request.data)
	if not serializer.is_valid():
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
	user = serializer.save()
	return Response({
		"message": "User created successfully",
		"user": {"id": str(user.id), "email": user.email},
		"tokens": tokens_for(user),
	}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
	from .serializers import LoginSerializer
	serializer = LoginSerializer(data=request.data)
	if not serializer.is_valid():
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
	user = serializer.validated_data.get("user") if isinstance(serializer.validated_data,
															   dict) else serializer.validated_data
	return Response({
		"user": {"id": str(user.id), "email": user.email},
		"tokens": tokens_for(user),
	})


@api_view(["POST"])
@permission_classes([AllowAny])
def google_login(request):
	raw = request.data.get("credential") or request.data.get("id_token")
	if not raw:
		return Response({"detail": "Missing Google ID token"}, status=400)

	allowed_auds = []
	if getattr(settings, "GOOGLE_CLIENT_IDS", ""):
		allowed_auds = [s.strip() for s in settings.GOOGLE_CLIENT_IDS.split(",") if s.strip()]
	elif getattr(settings, "GOOGLE_CLIENT_ID", ""):
		allowed_auds = [settings.GOOGLE_CLIENT_ID]

	if settings.DEBUG:
		log.info("Google token payload (peek): %s", _peek_jwt_payload(raw))

	req = google.auth.transport.requests.Request()

	try:
		try:
			info = google.oauth2.id_token.verify_oauth2_token(raw, req, audience=None)
		except GoogleInvalidValue as e:
			if "Token used too early" in str(e):
				time.sleep(1)
				info = google.oauth2.id_token.verify_oauth2_token(raw, req, audience=None)
			else:
				raise

		iss = info.get("iss")
		aud = info.get("aud")
		if iss not in ("https://accounts.google.com", "accounts.google.com"):
			return Response({"detail": "Invalid issuer"}, status=400)
		if allowed_auds and aud not in allowed_auds:
			return Response({"detail": "Audience mismatch", "aud": aud}, status=400)

		email = info.get("email")
		if not email or not info.get("email_verified"):
			return Response({"detail": "Email not verified by Google"}, status=400)

		hd_required = getattr(settings, "GOOGLE_HD", None)
		if hd_required and info.get("hd") != hd_required:
			return Response({"detail": "Unauthorized domain"}, status=403)

	except Exception as e:
		log.error("Google verify failed", exc_info=True)
		return Response(
			{"detail": f"Invalid Google token: {e}" if settings.DEBUG else "Invalid Google token"},
			status=400,
		)

	sub = info.get("sub")
	given = (info.get("given_name") or "")[:30]
	family = (info.get("family_name") or "")[:150]

	defaults = {}
	if has_field(User, "username"):
		defaults["username"] = unique_username_from_email(email, sub)
	if has_field(User, "first_name"):
		defaults["first_name"] = given
	if has_field(User, "last_name"):
		defaults["last_name"] = family
	if has_field(User, "name"):
		defaults["name"] = (f"{given} {family}".strip() or email.split("@")[0])[:150]

	user, created = User.objects.get_or_create(email=email, defaults=defaults)

	# Make sure federated accounts don't accidentally have a usable local password
	from django.contrib.auth.hashers import identify_hasher
	def _ensure_unusable_password(u):
		try:
			identify_hasher(u.password)
		except Exception:
			u.set_unusable_password()
			u.save(update_fields=["password"])

	_ensure_unusable_password(user)

	user.last_login = now()
	user.save(update_fields=["last_login"])

	return Response({
		"user": {
			"id": str(user.pk),
			"email": user.email,
			"on_boarding_step": user.on_boarding_step,
			"first_name": getattr(user, "first_name", ""),
			"last_name": getattr(user, "last_name", ""),
			"name": getattr(user, "name", ""),
		},
		"tokens": tokens_for(user),
	}, status=status.HTTP_200_OK)
