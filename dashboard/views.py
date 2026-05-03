from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, TemplateView

from accounts.models import AccountInvitation, AccountMembership
from accounts.services import ensure_personal_account, generate_invitation_token, get_active_membership, get_account_owner_user, transfer_owner
from automations.models import AutomationRule, MessageTemplate
from dashboard.forms import AutomationRuleForm, DashboardSignupForm, DummyLeadSubmissionForm, MessageTemplateForm
from facebook_integration.models import ConnectedFacebookAccount, FacebookPage, LeadForm
from facebook_integration.services.meta_graph import MetaAPIError, MetaGraphClient
from leads.models import Lead
from messaging.models import MessageLog
from messaging.tasks import send_messages_for_rule


User = get_user_model()


class DashboardLoginView(LoginView):
    template_name = "dashboard/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        ensure_personal_account(self.request.user)
        return response


class DashboardSignupView(CreateView):
    template_name = "dashboard/signup.html"
    form_class = DashboardSignupForm

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard-shell")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        next_url = (self.request.GET.get("next") or "").strip()
        base = f"{reverse_lazy('dashboard-login')}?registered=1"
        if next_url:
            base += f"&next={quote(next_url, safe='')}"
        return base

    def form_valid(self, form):
        response = super().form_valid(form)
        ensure_personal_account(self.object)
        return response


class DashboardLogoutView(LogoutView):
    next_page = "dashboard-login"


class DashboardShellView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/shell.html"
    login_url = "dashboard-login"


def _require_auth(request: HttpRequest) -> HttpResponse | None:
    if request.user.is_authenticated:
        return None
    return HttpResponse(status=401)


def _account_scope(request: HttpRequest) -> tuple[AccountMembership, object, object, bool]:
    account = ensure_personal_account(request.user)
    membership = get_active_membership(request.user)
    if not membership:
        membership = AccountMembership.objects.get(account=account, user=request.user, is_active=True)
    owner_user = get_account_owner_user(account) or request.user
    return membership, account, owner_user, membership.role == AccountMembership.ROLE_OWNER


def _overview_context(request: HttpRequest) -> dict:
    _, _, owner_user, _ = _account_scope(request)
    return {
        "page_count": FacebookPage.objects.filter(user=owner_user).count(),
        "form_count": LeadForm.objects.filter(page__user=owner_user).count(),
        "rule_count": AutomationRule.objects.filter(user=owner_user).count(),
        "template_count": MessageTemplate.objects.filter(user=owner_user).count(),
        "lead_count": Lead.objects.filter(user=owner_user).count(),
        "log_count": MessageLog.objects.filter(lead__user=owner_user).count(),
    }


@require_GET
def overview_section(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp
    return render(request, "dashboard/partials/overview.html", _overview_context(request))


@require_GET
def pages_section(request: HttpRequest) -> HttpResponse:
    return _render_pages_section(request)


def _render_pages_section(request: HttpRequest, error_message: str = "") -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp
    _, _, owner_user, is_owner = _account_scope(request)

    pages = FacebookPage.objects.filter(user=owner_user).order_by("name")
    has_account = ConnectedFacebookAccount.objects.filter(user=owner_user, is_active=True).exists()
    return render(
        request,
        "dashboard/partials/pages.html",
        {
            "pages": pages,
            "has_account": has_account,
            "is_owner": is_owner,
            "error_message": error_message,
        },
    )


@require_POST
def sync_pages_action(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp
    _, _, owner_user, is_owner = _account_scope(request)
    if not is_owner:
        return _render_pages_section(request, error_message="Only the account owner can sync pages.")

    account = ConnectedFacebookAccount.objects.filter(user=owner_user, is_active=True).order_by("-updated_at").first()
    if account:
        client = MetaGraphClient(access_token=account.access_token)
        try:
            pages = client.list_pages()
        except MetaAPIError as exc:
            return _render_pages_section(
                request,
                error_message=f"Facebook page sync failed. Please reconnect your Facebook account. Details: {exc}",
            )

        for page in pages:
            FacebookPage.objects.update_or_create(
                page_id=page["id"],
                defaults={
                    "user": owner_user,
                    "connected_account": account,
                    "name": page.get("name", "Unknown page"),
                    "page_access_token": page.get("access_token", ""),
                },
            )

    return _render_pages_section(request)


@require_GET
def forms_section(request: HttpRequest) -> HttpResponse:
    selected_page_id = request.GET.get("page")
    return _render_forms_section(request, selected_page_id=selected_page_id)


def _render_forms_section(
    request: HttpRequest,
    selected_page_id: str | None = None,
    error_message: str = "",
) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp
    _, _, owner_user, _ = _account_scope(request)

    forms_qs = (
        LeadForm.objects.filter(page__user=owner_user)
        .select_related("page")
        .annotate(lead_count=Count("leads"))
        .order_by("page__name", "name")
    )
    if selected_page_id:
        forms_qs = forms_qs.filter(page_id=selected_page_id)

    pages = FacebookPage.objects.filter(user=owner_user).order_by("name")
    return render(
        request,
        "dashboard/partials/forms.html",
        {
            "forms": forms_qs,
            "pages": pages,
            "selected_page_id": selected_page_id or "",
            "error_message": error_message,
        },
    )


@require_GET
def leads_section(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)

    selected_page_id = request.GET.get("page", "")
    selected_form_id = request.GET.get("form", "")
    query = request.GET.get("q", "").strip()

    leads_qs = Lead.objects.filter(user=owner_user).select_related("page", "lead_form").order_by("-created_at")

    if selected_page_id:
        leads_qs = leads_qs.filter(page_id=selected_page_id)
    if selected_form_id:
        leads_qs = leads_qs.filter(lead_form_id=selected_form_id)
    if query:
        leads_qs = leads_qs.filter(
            Q(full_name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query)
        )

    leads = list(leads_qs[:200])
    now = timezone.now()
    total_leads = leads_qs.count()
    email_count = leads_qs.exclude(email="").count()
    phone_count = leads_qs.exclude(phone="").count()
    recent_count = leads_qs.filter(created_at__gte=now - timedelta(days=1)).count()

    form_stats = (
        leads_qs.values("page__name", "lead_form__name")
        .annotate(total=Count("id"))
        .order_by("-total", "page__name", "lead_form__name")[:10]
    )

    pages = FacebookPage.objects.filter(user=owner_user).order_by("name")
    forms_qs = LeadForm.objects.filter(page__user=owner_user).select_related("page").order_by("page__name", "name")
    if selected_page_id:
        forms_qs = forms_qs.filter(page_id=selected_page_id)

    return render(
        request,
        "dashboard/partials/leads.html",
        {
            "leads": leads,
            "pages": pages,
            "forms": forms_qs,
            "selected_page_id": selected_page_id,
            "selected_form_id": selected_form_id,
            "query": query,
            "total_leads": total_leads,
            "email_count": email_count,
            "phone_count": phone_count,
            "recent_count": recent_count,
            "form_stats": form_stats,
        },
    )


@require_POST
def sync_forms_action(request: HttpRequest, page_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, is_owner = _account_scope(request)
    if not is_owner:
        return _render_forms_section(request, error_message="Only the account owner can sync forms.")

    page = get_object_or_404(FacebookPage, id=page_pk, user=owner_user)
    client = MetaGraphClient(access_token=page.page_access_token)
    try:
        forms = client.list_forms(page.page_id)
    except MetaAPIError as exc:
        return _render_forms_section(
            request,
            selected_page_id=str(page.id),
            error_message=(
                "Facebook form sync failed. Reconnect Facebook with pages_manage_ads permission and "
                f"ensure you have full control on the page. Details: {exc}"
            ),
        )

    for form in forms:
        LeadForm.objects.update_or_create(
            form_id=form["id"],
            defaults={
                "page": page,
                "name": form.get("name", "Unnamed form"),
                "status": form.get("status", "ACTIVE"),
            },
        )

    return _render_forms_section(request, selected_page_id=str(page.id))


@require_POST
def toggle_form_action(request: HttpRequest, form_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)
    lead_form = get_object_or_404(LeadForm, id=form_pk, page__user=owner_user)
    lead_form.is_selected = not lead_form.is_selected
    lead_form.save(update_fields=["is_selected"])

    page_id = request.POST.get("page")
    return _render_forms_section(request, selected_page_id=page_id)


def _templates_context(request: HttpRequest, form: MessageTemplateForm | None = None) -> dict:
    _, _, owner_user, _ = _account_scope(request)
    templates = MessageTemplate.objects.filter(user=owner_user).order_by("-updated_at")
    return {
        "templates": templates,
        "form": form or MessageTemplateForm(),
    }


@require_GET
def templates_section(request: HttpRequest) -> HttpResponse:
    return _render_templates_section(request)


def _render_templates_section(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp
    return render(request, "dashboard/partials/templates.html", _templates_context(request))


@require_POST
def create_template_action(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)

    form = MessageTemplateForm(request.POST)
    if form.is_valid():
        template = form.save(commit=False)
        template.user = owner_user
        template.save()
        form = MessageTemplateForm()

    return render(request, "dashboard/partials/templates.html", _templates_context(request, form=form))


@require_POST
def toggle_template_action(request: HttpRequest, template_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)
    template = get_object_or_404(MessageTemplate, id=template_pk, user=owner_user)
    template.is_active = not template.is_active
    template.save(update_fields=["is_active"])
    return _render_templates_section(request)


@require_POST
def delete_template_action(request: HttpRequest, template_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)
    template = get_object_or_404(MessageTemplate, id=template_pk, user=owner_user)
    template.delete()
    return _render_templates_section(request)


def _rules_context(request: HttpRequest, form: AutomationRuleForm | None = None) -> dict:
    _, _, owner_user, _ = _account_scope(request)
    rules = (
        AutomationRule.objects.filter(user=owner_user)
        .select_related("page", "email_template", "sms_template", "whatsapp_template")
        .prefetch_related("lead_forms")
        .order_by("priority", "id")
    )
    return {
        "rules": rules,
        "form": form or AutomationRuleForm(owner_user),
    }


@require_GET
def rules_section(request: HttpRequest) -> HttpResponse:
    return _render_rules_section(request)


def _render_rules_section(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp
    return render(request, "dashboard/partials/rules.html", _rules_context(request))


@require_POST
def create_rule_action(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)

    form = AutomationRuleForm(owner_user, request.POST)
    if form.is_valid():
        rule = form.save(commit=False)
        rule.user = owner_user
        rule.save()
        form.save_m2m()
        form = AutomationRuleForm(owner_user)

    return render(request, "dashboard/partials/rules.html", _rules_context(request, form=form))


@require_POST
def toggle_rule_action(request: HttpRequest, rule_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)
    rule = get_object_or_404(AutomationRule, id=rule_pk, user=owner_user)
    rule.enabled = not rule.enabled
    rule.save(update_fields=["enabled"])
    return _render_rules_section(request)


@require_POST
def delete_rule_action(request: HttpRequest, rule_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)
    rule = get_object_or_404(AutomationRule, id=rule_pk, user=owner_user)
    rule.delete()
    return _render_rules_section(request)


@require_GET
def logs_section(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)

    channel = request.GET.get("channel", "")
    status = request.GET.get("status", "")

    logs = (
        MessageLog.objects.filter(lead__user=owner_user)
        .select_related("lead", "rule")
        .order_by("-created_at")
    )
    if channel:
        logs = logs.filter(channel=channel)
    if status:
        logs = logs.filter(status=status)

    logs = logs[:200]

    return render(
        request,
        "dashboard/partials/logs.html",
        {
            "logs": logs,
            "channel": channel,
            "status": status,
            "channels": MessageLog.CHANNEL_CHOICES,
            "statuses": MessageLog.STATUS_CHOICES,
        },
    )


def _dummy_form_context(
    request: HttpRequest,
    form: DummyLeadSubmissionForm | None = None,
    result_logs=None,
    result_error: str = "",
) -> dict:
    _, _, owner_user, _ = _account_scope(request)
    recent_logs = MessageLog.objects.filter(lead__user=owner_user).select_related("lead", "rule").order_by("-created_at")[:20]
    return {
        "form": form or DummyLeadSubmissionForm(),
        "result_logs": list(result_logs or []),
        "result_error": result_error,
        "recent_logs": recent_logs,
    }


@require_GET
def dummy_lead_section(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp
    return render(request, "dashboard/partials/dummy_form.html", _dummy_form_context(request))


@require_POST
def submit_dummy_lead_action(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, _, owner_user, _ = _account_scope(request)

    form = DummyLeadSubmissionForm(request.POST)
    result_logs = []
    result_error = ""

    if form.is_valid():
        data = form.cleaned_data

        dummy_account, _ = ConnectedFacebookAccount.objects.get_or_create(
            user=owner_user,
            facebook_user_id=f"dummy-user-{owner_user.id}",
            defaults={
                "display_name": "Dashboard Dummy Account",
                "email": owner_user.email or "",
                "access_token": "",
                "is_active": False,
            },
        )

        page, _ = FacebookPage.objects.update_or_create(
            page_id=f"dummy-page-{owner_user.id}",
            defaults={
                "user": owner_user,
                "connected_account": dummy_account,
                "name": "Dashboard Dummy Page",
                "page_access_token": "",
                "is_selected": True,
            },
        )

        lead_form, _ = LeadForm.objects.update_or_create(
            form_id=f"dummy-form-{owner_user.id}",
            defaults={
                "page": page,
                "name": "Dashboard Dummy Form",
                "status": "ACTIVE",
                "is_selected": True,
            },
        )

        sms_template = None
        email_template = None
        whatsapp_template = None

        if data.get("send_sms"):
            sms_template, _ = MessageTemplate.objects.update_or_create(
                user=owner_user,
                name="Dashboard Dummy SMS",
                channel=MessageTemplate.CHANNEL_SMS,
                defaults={
                    "subject": "",
                    "body": data.get("sms_body", ""),
                    "is_active": True,
                },
            )

        if data.get("send_email"):
            email_template, _ = MessageTemplate.objects.update_or_create(
                user=owner_user,
                name="Dashboard Dummy Email",
                channel=MessageTemplate.CHANNEL_EMAIL,
                defaults={
                    "subject": data.get("email_subject", ""),
                    "body": data.get("email_body", ""),
                    "is_active": True,
                },
            )

        if data.get("send_whatsapp"):
            whatsapp_template, _ = MessageTemplate.objects.update_or_create(
                user=owner_user,
                name="Dashboard Dummy WhatsApp",
                channel=MessageTemplate.CHANNEL_WHATSAPP,
                defaults={
                    "subject": "",
                    "body": data.get("whatsapp_body", ""),
                    "twilio_content_sid": data.get("whatsapp_content_sid", ""),
                    "twilio_content_variables": data.get("whatsapp_content_variables") or {},
                    "is_active": True,
                },
            )

        rule, _ = AutomationRule.objects.update_or_create(
            user=owner_user,
            page=page,
            name="Dashboard Dummy Rule",
            defaults={
                "email_template": email_template,
                "sms_template": sms_template,
                "whatsapp_template": whatsapp_template,
                "require_email_opt_in": False,
                "require_sms_opt_in": False,
                "enabled": True,
                "priority": 1,
            },
        )
        rule.lead_forms.set([lead_form])

        lead = Lead.objects.create(
            user=owner_user,
            page=page,
            lead_form=lead_form,
            leadgen_id=f"dummy-{uuid4().hex[:20]}",
            full_name=data.get("full_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            consent_email=data.get("consent_email", False),
            consent_sms=data.get("consent_sms", False),
            raw_answers={
                "full_name": data.get("full_name", ""),
                "email": data.get("email", ""),
                "phone": data.get("phone", ""),
            },
            captured_at=timezone.now(),
        )

        try:
            # Run synchronously so local testing works without a Celery worker.
            send_messages_for_rule.run(lead.id, rule.id)
        except Exception as exc:
            result_error = str(exc)

        result_logs = MessageLog.objects.filter(lead=lead).select_related("rule").order_by("-created_at")
        form = DummyLeadSubmissionForm()

    return render(
        request,
        "dashboard/partials/dummy_form.html",
        _dummy_form_context(request, form=form, result_logs=result_logs, result_error=result_error),
    )


def _team_context(request: HttpRequest, error_message: str = "", info_message: str = "") -> dict:
    membership, account, owner_user, is_owner = _account_scope(request)
    members = (
        AccountMembership.objects.filter(account=account, is_active=True)
        .select_related("user")
        .order_by("role", "user__username")
    )
    pending_invitations = (
        AccountInvitation.objects.filter(
            account=account,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
    )
    return {
        "account": account,
        "owner_user": owner_user,
        "members": members,
        "pending_invitations": pending_invitations,
        "is_owner": is_owner,
        "current_membership": membership,
        "error_message": error_message,
        "info_message": info_message,
    }


@require_GET
def team_section(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp
    return render(request, "dashboard/partials/team.html", _team_context(request))


@require_POST
def invite_member_action(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, account, _, is_owner = _account_scope(request)
    if not is_owner:
        return render(request, "dashboard/partials/team.html", _team_context(request, error_message="Only the owner can invite members."))

    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return render(request, "dashboard/partials/team.html", _team_context(request, error_message="Email is required."))

    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user and AccountMembership.objects.filter(account=account, user=existing_user, is_active=True).exists():
        return render(
            request,
            "dashboard/partials/team.html",
            _team_context(request, error_message="This user already has access to the account."),
        )

    token = generate_invitation_token()
    invitation = AccountInvitation.objects.create(
        account=account,
        email=email,
        role=AccountInvitation.ROLE_MEMBER,
        token=token,
        invited_by=request.user,
        expires_at=AccountInvitation.default_expiry(),
    )

    accept_url = request.build_absolute_uri(reverse("account-invitation-accept", args=[invitation.token]))
    try:
        send_mail(
            subject=f"Invitation to join {account.name}",
            message=(
                f"You have been invited to join {account.name}.\n\n"
                f"Accept invitation: {accept_url}\n\n"
                "If you don't have an account yet, sign up and then open this link again."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:
        invitation.delete()
        return render(
            request,
            "dashboard/partials/team.html",
            _team_context(request, error_message=f"Failed to send invitation email: {exc}"),
        )

    return render(
        request,
        "dashboard/partials/team.html",
        _team_context(request, info_message=f"Invitation sent to {email}."),
    )


@require_POST
def remove_member_action(request: HttpRequest, membership_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, account, _, is_owner = _account_scope(request)
    if not is_owner:
        return render(request, "dashboard/partials/team.html", _team_context(request, error_message="Only the owner can remove members."))

    target = get_object_or_404(AccountMembership, id=membership_pk, account=account, is_active=True)
    if target.role == AccountMembership.ROLE_OWNER:
        return render(
            request,
            "dashboard/partials/team.html",
            _team_context(request, error_message="Owner cannot be removed. Transfer ownership first."),
        )

    target.is_active = False
    target.save(update_fields=["is_active"])
    return render(request, "dashboard/partials/team.html", _team_context(request, info_message="Member access removed."))


@require_POST
def transfer_owner_action(request: HttpRequest, membership_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    _, account, _, is_owner = _account_scope(request)
    if not is_owner:
        return render(request, "dashboard/partials/team.html", _team_context(request, error_message="Only the owner can transfer ownership."))

    try:
        transfer_owner(account, request.user, membership_pk)
    except Exception as exc:
        return render(
            request,
            "dashboard/partials/team.html",
            _team_context(request, error_message=f"Failed to transfer ownership: {exc}"),
        )
    return render(
        request,
        "dashboard/partials/team.html",
        _team_context(request, info_message="Ownership transferred successfully."),
    )
