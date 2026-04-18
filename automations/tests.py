from django.test import SimpleTestCase

from automations.services.template_renderer import render_template


class TemplateRendererTests(SimpleTestCase):
    def test_renders_allowed_variables(self):
        template = "Hi {{name}}, thanks for contacting {{page_name}} via {{form_name}}."
        result = render_template(
            template,
            {
                "name": "Alex",
                "page_name": "Acme Dental",
                "form_name": "Consultation",
            },
        )
        self.assertEqual(result, "Hi Alex, thanks for contacting Acme Dental via Consultation.")

    def test_unknown_variables_are_removed(self):
        template = "{{name}} {{unknown}}"
        result = render_template(template, {"name": "Alex"})
        self.assertEqual(result, "Alex ")
