# -*- coding: utf-8 -*-
{
    "name": "Citas Óptica",
    "summary": "Agenda de citas para pacientes de una óptica desde backend y website.",
    "description": """
Sistema simple para gestionar citas de pacientes de una óptica.
Permite crear citas desde el backend y desde una página pública del website.
    """,
    "version": "17.0.1.0.0",
    "category": "Services/Appointment",
    "author": "Bellako85",
    "license": "LGPL-3",
    "depends": ["base", "mail", "website"],
    "data": [
        "security/ir.model.access.csv",
        "views/optica_appointment_views.xml",
        "views/website_appointment_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "optica_appointment/static/src/scss/appointment.scss",
        ],
    },
    "application": True,
    "installable": True,
}
