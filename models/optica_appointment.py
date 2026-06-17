# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    partner_id = fields.Many2one(
        "res.partner",
        string="Paciente",
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

    appointment_type = fields.Selection(
        selection=[
            ("exam", "Examen visual"),
            ("delivery", "Entrega de lentes"),
            ("adjustment", "Ajuste de armazón"),
            ("warranty", "Garantía"),
            ("progressive_adaptation", "Adaptación de progresivos"),
            ("other", "Otro"),
        ],
        string="Tipo de cita",
        default="exam",
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

    duration = fields.Float(
        string="Duración",
        default=0.5,
        required=True,
        tracking=True,
        help="Duración en horas. 0.5 equivale a 30 minutos.",
    )

    appointment_datetime = fields.Datetime(
        string="Inicio de cita",
        compute="_compute_appointment_datetime",
        store=True,
        index=True,
    )

    appointment_end_datetime = fields.Datetime(
        string="Fin de cita",
        compute="_compute_appointment_end_datetime",
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
            ("draft", "Pendiente"),
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

    internal_notes = fields.Text(
        string="Notas internas",
    )

    calendar_event_id = fields.Many2one(
        "calendar.event",
        string="Evento de calendario",
        readonly=True,
        copy=False,
    )

    @api.depends("appointment_date", "appointment_time")
    def _compute_appointment_datetime(self):
        """Build appointment datetime using the user's local timezone and store it in UTC."""
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

            local_date = fields.Date.to_date(appointment.appointment_date)
            local_datetime = datetime.combine(
                local_date,
                time(hour=hours, minute=minutes),
            )

            user_tz_name = self.env.user.tz or "UTC"
            user_tz = pytz.timezone(user_tz_name)

            localized_datetime = user_tz.localize(local_datetime)
            utc_datetime = localized_datetime.astimezone(pytz.UTC).replace(tzinfo=None)

            appointment.appointment_datetime = utc_datetime

    @api.depends("appointment_datetime", "duration")
    def _compute_appointment_end_datetime(self):
        for appointment in self:
            if appointment.appointment_datetime:
                appointment.appointment_end_datetime = (
                    appointment.appointment_datetime
                    + timedelta(hours=appointment.duration or 0.5)
                )
            else:
                appointment.appointment_end_datetime = False

    @api.constrains("appointment_datetime", "appointment_end_datetime", "state")
    def _check_appointment_overlap(self):
        for appointment in self:
            if not appointment.appointment_datetime or not appointment.appointment_end_datetime:
                continue

            if appointment.state == "cancelled":
                continue

            overlapping = self.search_count([
                ("id", "!=", appointment.id),
                ("state", "in", ["draft", "confirmed"]),
                ("appointment_datetime", "<", appointment.appointment_end_datetime),
                ("appointment_end_datetime", ">", appointment.appointment_datetime),
            ])

            if overlapping:
                raise ValidationError(
                    "Ya existe una cita registrada en ese horario. Elige otra hora."
                )

    @api.constrains("duration")
    def _check_duration(self):
        for appointment in self:
            if appointment.duration <= 0:
                raise ValidationError("La duración de la cita debe ser mayor a 0.")

    def _get_or_create_partner(self):
        self.ensure_one()

        partner = False

        if self.email:
            partner = self.env["res.partner"].search([
                ("email", "=", self.email),
            ], limit=1)

        if not partner and self.phone:
            partner = self.env["res.partner"].search([
                "|",
                ("phone", "=", self.phone),
                ("mobile", "=", self.phone),
            ], limit=1)

        if not partner:
            partner = self.env["res.partner"].create({
                "name": self.patient_name,
                "phone": self.phone,
                "mobile": self.whatsapp or self.phone,
                "email": self.email,
                "customer_rank": 1,
            })

        return partner

    def _create_calendar_event(self):
        self.ensure_one()

        if self.calendar_event_id:
            return self.calendar_event_id

        if not self.appointment_datetime or not self.appointment_end_datetime:
            return False

        partner_ids = []
        if self.partner_id:
            partner_ids = [self.partner_id.id]

        event = self.env["calendar.event"].create({
            "name": "Cita óptica - %s" % self.patient_name,
            "start": self.appointment_datetime,
            "stop": self.appointment_end_datetime,
            "partner_ids": [(6, 0, partner_ids)] if partner_ids else False,
            "description": self.reason or "",
        })

        self.calendar_event_id = event.id
        return event

    def action_confirm(self):
        for appointment in self:
            if not appointment.partner_id:
                appointment.partner_id = appointment._get_or_create_partner().id

            appointment._create_calendar_event()

        self.write({"state": "confirmed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_done(self):
        self.write({"state": "done"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})
