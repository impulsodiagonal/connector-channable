# -*- coding: utf-8 -*-
# from odoo import http


# class ConnectorChannable(http.Controller):
#     @http.route('/connector_channable/connector_channable/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/connector_channable/connector_channable/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('connector_channable.listing', {
#             'root': '/connector_channable/connector_channable',
#             'objects': http.request.env['connector_channable.connector_channable'].search([]),
#         })

#     @http.route('/connector_channable/connector_channable/objects/<model("connector_channable.connector_channable"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('connector_channable.object', {
#             'object': obj
#         })
