# -*- coding: utf-8 -*-
{
    "name": "KIO Maintenance Repair Dashboard",
    "summary": "Modern OWL analytics dashboard for maintenance and repair operations",
    "description": """
Full-width SaaS style Maintenance & Repair dashboard for Odoo 17.
    """,
    "author": "KIO",
    "website": "https://www.yourcompany.com",
    "category": "Operations/Maintenance",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "depends": ["web", "maintenance", "repair"],
    "data": [
        "security/ir.model.access.csv",
        "views/dashboard_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "web/static/lib/Chart/Chart.js",
            "kio_maintenance_repair_dashboard/static/src/js/maintenance_repair_dashboard.js",
            "kio_maintenance_repair_dashboard/static/src/xml/maintenance_repair_dashboard.xml",
            "kio_maintenance_repair_dashboard/static/src/scss/maintenance_repair_dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}
