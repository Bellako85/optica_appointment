# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta
import time as time_module
import hashlib
import requests
import logging
import pytz
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

PIXEL_ID = "TU_PIXEL_ID"
TOKEN = "TU_TOKEN_CAPI"

class OpticaAppointment(models.Model):
    """Appointment agenda for optical-store patients."""

    _name = "optica.appointment"
    _description = "Cita Óptica"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "appointment_datetime desc, id desc"

    patient_name = fields.Char(string="Nombre del paciente", required=True, tracking=True)
    partner_id = fields.Many2one("res.partner", string="Paciente", tracking=True)
    phone = fields.Char(string="Teléfono", tracking=True)
    whatsapp = fields.Char(string="WhatsApp", required=True, tracking=True)
    email = fields.Char(string="Email", required=True, tracking=True)

    appointment_origin = fields.Selection(
        [
            ("website", "Sitio web"),
            ("backend", "Backend"),
        ],
        string="Origen de la cita",
        default="backend",
        required=True,
        copy=False,
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
        tracking=True,
    )

    appointment_date = fields.Date(string="Fecha de cita", required=True, tracking=True)
    appointment_time = fields.Float(
        string="Hora de cita",
        required=True,
        tracking=True,
        help="Hora en formato 24 horas. Ejemplo: 14.50 equivale a 14:30.",
    )
    duration = fields.Float(string="Duración", default=0.5, required=True, tracking=True)
    
    appointment_datetime = fields.Datetime(string="Inicio de cita", compute="_compute_appointment_datetime", store=True, index=True)
    appointment_end_datetime = fields.Datetime(string="Fin de cita", compute="_compute_appointment_end_datetime", store=True, index=True)
    
    reason = fields.Text(string="Motivo de la cita", tracking=True)

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

    internal_notes = fields.Text(string="Notas internas")
    calendar_event_id = fields.Many2one("calendar.event", string="Evento de calendario", readonly=True, copy=False)
    crm_lead_id = fields.Many2one("crm.lead", string="Oportunidad CRM", readonly=True, copy=False)
    x_meta_event_id = fields.Char(string="Meta Event ID", copy=False, readonly=True)

    @api.depends("appointment_date", "appointment_time")
    def _compute_appointment_datetime(self):
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
            local_datetime = datetime.combine(local_date, time(hour=hours, minute=minutes))
            user_tz = pytz.timezone("America/Mexico_City")
            localized_datetime = user_tz.localize(local_datetime)
            utc_datetime = localized_datetime.astimezone(pytz.UTC).replace(tzinfo=None)
            appointment.appointment_datetime = utc_datetime

    @api.depends("appointment_datetime", "duration")
    def _compute_appointment_end_datetime(self):
        for appointment in self:
            if appointment.appointment_datetime:
                appointment.appointment_end_datetime = appointment.appointment_datetime + timedelta(hours=appointment.duration or 0.5)
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
                raise ValidationError("Ya existe una cita registrada en ese horario. Elige otra hora.")

    @api.constrains("duration")
    def _check_duration(self):
        for appointment in self:
            if appointment.duration <= 0:
                raise ValidationError("La duración de la cita debe ser mayor a 0.")

    def _get_or_create_partner(self):
        self.ensure_one()
        partner = False
        if self.email:
            partner = self.env["res.partner"].search([("email", "=", self.email)], limit=1)
        if not partner and self.phone:
            partner = self.env["res.partner"].search(["|", ("phone", "=", self.phone), ("mobile", "=", self.phone)], limit=1)
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
        partner_ids = [self.partner_id.id] if self.partner_id else []
        event = self.env["calendar.event"].create({
            "name": "Cita óptica - %s" % self.patient_name,
            "start": self.appointment_datetime,
            "stop": self.appointment_end_datetime,
            "partner_ids": [(6, 0, partner_ids)] if partner_ids else False,
            "description": self.reason or "",
        })
        self.write({"calendar_event_id": event.id})
        return event

    def _create_crm_opportunity(self):
        self.ensure_one()
        if self.crm_lead_id:
            return self.crm_lead_id
        stage = self.env["crm.stage"].search([("name", "=", "Lead calificado")], limit=1)
        hours = int(self.appointment_time)
        minutes = int(round((self.appointment_time - hours) * 60))
        time_str = f"{hours:02d}:{minutes:02d}"
        lead = self.env["crm.lead"].sudo().create({
            "name": "Cita óptica - %s" % self.patient_name,
            "type": "opportunity",
            "partner_id": self.partner_id.id if self.partner_id else False,
            "partner_name": self.patient_name,
            "contact_name": self.patient_name,
            "phone": self.phone,
            "mobile": self.whatsapp or self.phone,
            "email_from": self.email,
            "stage_id": stage.id if stage else False,
            "expected_revenue": 600.0,
            "description": """
Tipo de cita: %s
Fecha: %s a las %s hrs.
Motivo: %s
            """ % (
                dict(self._fields["appointment_type"].selection).get(self.appointment_type),
                self.appointment_date,
                time_str,
                self.reason or "",
            ),
        })
        self.write({"crm_lead_id": lead.id})
        return lead

    def _meta_send_schedule_capi(self, appointment, event_id, event_time):
        try:
            httprequest = request.httprequest if request else None
            user_data = {}
            if appointment.email:
                user_data["em"] = [hashlib.sha256(appointment.email.lower().encode()).hexdigest()]
            if appointment.phone or appointment.whatsapp:
                phone = ''.join(filter(str.isdigit, appointment.phone or appointment.whatsapp))
                user_data["ph"] = [hashlib.sha256(phone.encode()).hexdigest()]
            if httprequest:
                if httprequest.cookies.get('_fbp'):
                    user_data["fbp"] = httprequest.cookies.get('_fbp')
                if httprequest.cookies.get('_fbc'):
                    user_data["fbc"] = httprequest.cookies.get('_fbc')
                event_source_url = httprequest.url
            else:
                event_source_url = "https://optica-zamora.com/cita/gracias"
            payload = {
              "data": [{
                "event_name": "Schedule",
                "event_time": event_time,
                "event_id": event_id,
                "action_source": "website",
                "event_source_url": event_source_url,
                "user_data": user_data
              }]
            }
            requests.post(
              f"https://graph.facebook.com/v19.0/{PIXEL_ID}/events?access_token={TOKEN}",
              json=payload, timeout=5
            )
        except Exception as e:
            _logger.warning("CAPI Schedule failed: %s", e)

    def action_confirm(self):
        for appointment in self:
            if not appointment.partner_id:
                appointment.partner_id = appointment._get_or_create_partner().id
            appointment._create_calendar_event()
            appointment._create_crm_opportunity()
        
        self.write({"state": "confirmed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_done(self):
        self.write({"state": "done"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})

    
