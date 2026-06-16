# -*- coding: utf-8 -*-

from odoo import api, fields, models


class OpticaAppointment(models.Model):
    """Appointment agenda for optical-store patients."""

    _name = "optica.appointment"
    _description = "Cita Óptica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "appointment_datetime desc, id desc"

    patient_name = fields.Char(
        string="Nombre del paciente",
        required=True,
        tracking=True,
    )
    phone = fields.Char(
        string="Teléfono",
        required=True,
        tracking=True,
    )
    whatsapp = fields.Char(
        string="WhatsApp",
        tracking=True,
    )
    email = fields.Char(
        string="Email",
        required=True,
        tracking=True,
    )
    appointment_date = fields.Date(
        string="Fecha de cita",
        required=True,
        tracking=True,
    )
    appointment_time = fields.Float(
        string="Hora de cita",
        required=True,
        tracking=True,
        help="Hora en formato 24 horas. Ejemplo: 14.50 equivale a 14:30.",
    )
    appointment_datetime = fields.Datetime(
        string="Fecha y hora",
        compute="_compute_appointment_datetime",
        store=True,
        index=True,
    )
    reason = fields.Text(
        string="Motivo de la cita",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("confirmed", "Confirmada"),
            ("cancelled", "Cancelada"),
            ("done", "Realizada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    internal_notes = fields.Text(string="Notas internas")

    @api.depends("appointment_date", "appointment_time")
    def _compute_appointment_datetime(self):
        """Build a datetime useful for calendar/list ordering from date and decimal hour."""
        for appointment in self:
            if not appointment.appointment_date:
                appointment.appointment_datetime = False
                continue

            hour_float = appointment.appointment_time or 0.0
            hours = int(hour_float)
            minutes = int(round((hour_float - hours) * 60))
            if minutes >= 60:
                hours += 1
                minutes -= 60
            hours = min(max(hours, 0), 23)
            minutes = min(max(minutes, 0), 59)
            appointment.appointment_datetime = fields.Datetime.to_datetime(
                appointment.appointment_date
            ).replace(hour=hours, minute=minutes, second=0)

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_done(self):
        self.write({"state": "done"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})
