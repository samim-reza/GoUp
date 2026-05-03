from __future__ import annotations

import secrets
from django.db import transaction
from django.utils import timezone

from accounts.models import Account, AccountInvitation, AccountMembership

class InvitationError(Exception):
    pass


@transaction.atomic
def ensure_personal_account(user) -> Account:
    membership = (
        AccountMembership.objects.select_related("account")
        .filter(user=user, is_active=True)
        .order_by("-id")
        .first()
    )
    if membership:
        return membership.account

    account = Account.objects.create(name=f"{user.get_username()} Workspace")
    AccountMembership.objects.create(account=account, user=user, role=AccountMembership.ROLE_OWNER, is_active=True)
    return account


def get_active_membership(user) -> AccountMembership | None:
    return (
        AccountMembership.objects.select_related("account")
        .filter(user=user, is_active=True)
        .order_by("-id")
        .first()
    )


def get_account_owner_membership(account: Account) -> AccountMembership | None:
    return (
        AccountMembership.objects.select_related("user")
        .filter(account=account, is_active=True, role=AccountMembership.ROLE_OWNER)
        .first()
    )


def get_account_owner_user(account: Account):
    owner = get_account_owner_membership(account)
    return owner.user if owner else None


def is_account_owner(user, account: Account) -> bool:
    return AccountMembership.objects.filter(
        account=account,
        user=user,
        is_active=True,
        role=AccountMembership.ROLE_OWNER,
    ).exists()


@transaction.atomic
def accept_invitation(token: str, user) -> AccountMembership:
    invitation = AccountInvitation.objects.select_for_update().filter(token=token).first()
    if not invitation:
        raise InvitationError("Invitation not found.")
    if invitation.revoked_at:
        raise InvitationError("Invitation was revoked.")
    if invitation.accepted_at:
        raise InvitationError("Invitation already accepted.")
    if invitation.expires_at <= timezone.now():
        raise InvitationError("Invitation has expired.")
    if (user.email or "").strip().lower() != invitation.email.strip().lower():
        raise InvitationError("Signed-in email does not match invitation email.")

    membership, _ = AccountMembership.objects.update_or_create(
        account=invitation.account,
        user=user,
        defaults={
            "role": AccountMembership.ROLE_MEMBER,
            "is_active": True,
            "invited_by": invitation.invited_by,
        },
    )

    invitation.accepted_at = timezone.now()
    invitation.accepted_by = user
    invitation.save(update_fields=["accepted_at", "accepted_by"])
    return membership


@transaction.atomic
def transfer_owner(account: Account, current_owner, target_membership_id: int) -> None:
    owner_membership = AccountMembership.objects.select_for_update().get(
        account=account,
        user=current_owner,
        role=AccountMembership.ROLE_OWNER,
        is_active=True,
    )
    target = AccountMembership.objects.select_for_update().get(
        id=target_membership_id,
        account=account,
        is_active=True,
    )

    owner_membership.role = AccountMembership.ROLE_MEMBER
    owner_membership.save(update_fields=["role"])

    target.role = AccountMembership.ROLE_OWNER
    target.save(update_fields=["role"])


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)
