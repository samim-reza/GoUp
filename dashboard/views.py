from __future__ import annotations

from uuid import uuid4

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from automations.models import AutomationRule, MessageTemplate
from dashboard.forms import AutomationRuleForm, DummyLeadSubmissionForm, MessageTemplateForm
from facebook_integration.models import ConnectedFacebookAccount, FacebookPage, LeadForm
from facebook_integration.services.meta_graph import MetaAPIError, MetaGraphClient
from leads.models import Lead
from messaging.models import MessageLog
from messaging.tasks import send_messages_for_rule


class DashboardLoginView(LoginView):
    template_name = "dashboard/login.html"
    redirect_authenticated_user = True


class DashboardLogoutView(LogoutView):
    next_page = "dashboard-login"


class DashboardShellView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/shell.html"
    login_url = "dashboard-login"


def _require_auth(request: HttpRequest) -> HttpResponse | None:
    if request.user.is_authenticated:
        return None
    return HttpResponse(status=401)


def _overview_context(request: HttpRequest) -> dict:
    return {
        "page_count": FacebookPage.objects.filter(user=request.user).count(),
        "form_count": LeadForm.objects.filter(page__user=request.user).count(),
        "rule_count": AutomationRule.objects.filter(user=request.user).count(),
        "template_count": MessageTemplate.objects.filter(user=request.user).count(),
        "lead_count": Lead.objects.filter(user=request.user).count(),
        "log_count": MessageLog.objects.filter(lead__user=request.user).count(),
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

    pages = FacebookPage.objects.filter(user=request.user).order_by("name")
    has_account = ConnectedFacebookAccount.objects.filter(user=request.user, is_active=True).exists()
    return render(
        request,
        "dashboard/partials/pages.html",
        {
            "pages": pages,
            "has_account": has_account,
            "error_message": error_message,
        },
    )


@require_POST
def sync_pages_action(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    account = ConnectedFacebookAccount.objects.filter(user=request.user, is_active=True).order_by("-updated_at").first()
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
                    "user": request.user,
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

    forms_qs = LeadForm.objects.filter(page__user=request.user).select_related("page").order_by("page__name", "name")
    if selected_page_id:
        forms_qs = forms_qs.filter(page_id=selected_page_id)

    pages = FacebookPage.objects.filter(user=request.user).order_by("name")
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


@require_POST
def sync_forms_action(request: HttpRequest, page_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    page = get_object_or_404(FacebookPage, id=page_pk, user=request.user)
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

    lead_form = get_object_or_404(LeadForm, id=form_pk, page__user=request.user)
    lead_form.is_selected = not lead_form.is_selected
    lead_form.save(update_fields=["is_selected"])

    page_id = request.POST.get("page")
    return _render_forms_section(request, selected_page_id=page_id)


def _templates_context(request: HttpRequest, form: MessageTemplateForm | None = None) -> dict:
    templates = MessageTemplate.objects.filter(user=request.user).order_by("-updated_at")
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

    form = MessageTemplateForm(request.POST)
    if form.is_valid():
        template = form.save(commit=False)
        template.user = request.user
        template.save()
        form = MessageTemplateForm()

    return render(request, "dashboard/partials/templates.html", _templates_context(request, form=form))


@require_POST
def toggle_template_action(request: HttpRequest, template_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    template = get_object_or_404(MessageTemplate, id=template_pk, user=request.user)
    template.is_active = not template.is_active
    template.save(update_fields=["is_active"])
    return _render_templates_section(request)


@require_POST
def delete_template_action(request: HttpRequest, template_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    template = get_object_or_404(MessageTemplate, id=template_pk, user=request.user)
    template.delete()
    return _render_templates_section(request)


def _rules_context(request: HttpRequest, form: AutomationRuleForm | None = None) -> dict:
    rules = (
        AutomationRule.objects.filter(user=request.user)
        .select_related("page", "email_template", "sms_template", "whatsapp_template")
        .prefetch_related("lead_forms")
        .order_by("priority", "id")
    )
    return {
        "rules": rules,
        "form": form or AutomationRuleForm(request.user),
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

    form = AutomationRuleForm(request.user, request.POST)
    if form.is_valid():
        rule = form.save(commit=False)
        rule.user = request.user
        rule.save()
        form.save_m2m()
        form = AutomationRuleForm(request.user)

    return render(request, "dashboard/partials/rules.html", _rules_context(request, form=form))


@require_POST
def toggle_rule_action(request: HttpRequest, rule_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    rule = get_object_or_404(AutomationRule, id=rule_pk, user=request.user)
    rule.enabled = not rule.enabled
    rule.save(update_fields=["enabled"])
    return _render_rules_section(request)


@require_POST
def delete_rule_action(request: HttpRequest, rule_pk: int) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    rule = get_object_or_404(AutomationRule, id=rule_pk, user=request.user)
    rule.delete()
    return _render_rules_section(request)


@require_GET
def logs_section(request: HttpRequest) -> HttpResponse:
    auth_resp = _require_auth(request)
    if auth_resp:
        return auth_resp

    channel = request.GET.get("channel", "")
    status = request.GET.get("status", "")

    logs = (
        MessageLog.objects.filter(lead__user=request.user)
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
    recent_logs = MessageLog.objects.filter(lead__user=request.user).select_related("lead", "rule").order_by("-created_at")[:20]
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

    form = DummyLeadSubmissionForm(request.POST)
    result_logs = []
    result_error = ""

    if form.is_valid():
        data = form.cleaned_data

        dummy_account, _ = ConnectedFacebookAccount.objects.get_or_create(
            user=request.user,
            facebook_user_id=f"dummy-user-{request.user.id}",
            defaults={
                "display_name": "Dashboard Dummy Account",
                "email": request.user.email or "",
                "access_token": "",
                "is_active": False,
            },
        )

        page, _ = FacebookPage.objects.update_or_create(
            page_id=f"dummy-page-{request.user.id}",
            defaults={
                "user": request.user,
                "connected_account": dummy_account,
                "name": "Dashboard Dummy Page",
                "page_access_token": "",
                "is_selected": True,
            },
        )

        lead_form, _ = LeadForm.objects.update_or_create(
            form_id=f"dummy-form-{request.user.id}",
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
                user=request.user,
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
                user=request.user,
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
                user=request.user,
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
            user=request.user,
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
            user=request.user,
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
