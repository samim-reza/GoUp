from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Account(models.Model):
	name = models.CharField(max_length=160)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["name", "id"]

	def __str__(self) -> str:
		return self.name


class AccountMembership(models.Model):
	ROLE_OWNER = "owner"
	ROLE_MEMBER = "member"
	ROLE_CHOICES = [
		(ROLE_OWNER, "Owner"),
		(ROLE_MEMBER, "Member"),
	]

	account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="memberships")
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_memberships")
	role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
	is_active = models.BooleanField(default=True)
	invited_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="account_memberships_invited",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["account", "user"], name="unique_account_user_membership"),
			models.UniqueConstraint(
				fields=["account"],
				condition=Q(role="owner", is_active=True),
				name="unique_active_owner_per_account",
			),
		]

	def __str__(self) -> str:
		return f"{self.account_id}:{self.user_id}:{self.role}"


class AccountInvitation(models.Model):
	ROLE_MEMBER = AccountMembership.ROLE_MEMBER
	ROLE_OWNER = AccountMembership.ROLE_OWNER
	ROLE_CHOICES = [
		(ROLE_MEMBER, "Member"),
		(ROLE_OWNER, "Owner"),
	]

	account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="invitations")
	email = models.EmailField()
	role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
	token = models.CharField(max_length=128, unique=True)
	invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_account_invitations")
	accepted_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="accepted_account_invitations",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	expires_at = models.DateTimeField()
	accepted_at = models.DateTimeField(null=True, blank=True)
	revoked_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		indexes = [models.Index(fields=["token"]), models.Index(fields=["email"])]

	def __str__(self) -> str:
		return f"{self.email} -> {self.account_id}"

	@property
	def is_pending(self) -> bool:
		return not self.accepted_at and not self.revoked_at and self.expires_at > timezone.now()

	@classmethod
	def default_expiry(cls):
		return timezone.now() + timedelta(days=7)
