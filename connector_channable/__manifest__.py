# Copyright 2021 - Impulso Diagonal
# Copyright 2022 - Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Connector Channable",
    "summary": "Module to manage connection between Channable and Odoo",
    "author": "Impulso Diagonal SLU,Tecnativa",
    "website": "https://www.impulso.xyz",
    "category": "Sale",
    "license": "AGPL-3",
    "version": "13.0.1.0.1",
    "depends": ["sale", "queue_job"],
    "data": [
        "security/ir.model.access.csv",
        "views/connector_channable_views.xml",
        "data/cron.xml",
    ],
}
