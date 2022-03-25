# -*- coding: utf-8 -*-
{
    'name': "Connector Channable",

    'summary': """
        Module to manage connection between Channable and Odoo
        """,

    'description': """
        Module to manage connection between Channable and Odoo
    """,

    'author': "Impulso Diagonal,SLU",
    'website': "https://www.impulso.xyz",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sale',
    'version': '13.0.1.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale', 'queue_job'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'data/cron.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
