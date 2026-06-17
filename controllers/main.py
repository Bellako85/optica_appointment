# -*- coding: utf-8 -*-

from odoo import fields, http
from odoo.http import request


class OpticaAppointmentController(http.Controller):
    """Public website routes to schedule optical appointments."""

    def _parse_float_time(self, value):
        if not value:
            return 0.0
        if ":" in value:
            hours, minutes = value.split(":", 1)
            return int(hours) + (int(minutes) / 60.0)
        return float(value)

    def _prepare_appointment_values(self, post):
        return {
            "patient_name": post.get("patient_name", "").strip(),
            "phone": post.get("phone", "").strip(),
            "whatsapp": post.get("whatsapp", "").strip(),
            "email": post.get("email", "").strip(),
            "appointment_date": post.get("appointment_date"),
            "appointment_time": self._parse_float_time(post.get("appointment_time")),
            "reason": post.get("reason", "").strip(),
            "state": "draft",
        }

    def _validate_appointment_form(self, post):
        errors = {}
        required_fields = {
            "patient_name": "El nombre es obligatorio.",
            "phone": "El teléfono es obligatorio.",
            "email": "El email es obligatorio.",
            "appointment_date": "La fecha deseada es obligatoria.",
            "appointment_time": "La hora deseada es obligatoria.",
            "reason": "El motivo de la cita es obligatorio.",
        }
        for field_name, message in required_fields.items():
            if not post.get(field_name):
                errors[field_name] = message

        if post.get("appointment_date"):
            try:
                fields.Date.to_date(post.get("appointment_date"))
            except ValueError:
                errors["appointment_date"] = "La fecha indicada no es válida."

        try:
            appointment_time = self._parse_float_time(post.get("appointment_time"))
        except ValueError:
            errors["appointment_time"] = "La hora indicada no es válida."
        else:
            if post.get("appointment_time") and not 0.0 <= appointment_time <= 23.99:
                errors["appointment_time"] = "La hora debe estar entre 00:00 y 23:59."

        return errors

    @http.route("/agendar-cita", type="http", auth="public", website=True, methods=["GET", "POST"])
    def appointment_form(self, **post):
        values = {"errors": {}, "form_values": post}
        if request.httprequest.method == "POST":
            errors = self._validate_appointment_form(post)
            if errors:
                values["errors"] = errors
                return request.render("optica_appointment.appointment_form", values)

            request.env["optica.appointment"].sudo().create(
                self._prepare_appointment_values(post)
            )
            return request.redirect("/agendar-cita/gracias")

        return request.render("optica_appointment.appointment_form", values)

    @http.route("/agendar-cita/gracias", type="http", auth="public", website=True)
    def appointment_success(self, **kwargs):
        return request.render("optica_appointment.appointment_success")
