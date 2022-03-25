# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import requests
from odoo.addons.queue_job.job import job


class ConnectorChannableConnection(models.Model):
    _name = 'connector.channable.connection'
    _description = 'Connector Chanable Connection'

    name = fields.Char('Name', required=True)
    api_token = fields.Char('Token', required=True)
    company = fields.Char('Company', required=True)
    project = fields.Char('Project', required=True)
    state = fields.Boolean('State', default=True)
    url = fields.Char('Url', default='https://api.channable.com/v1')
    params = fields.Char('Parameters', default='limit=100')

    

    def queue_request(self, req, headers):
        res = requests.get(req, headers=headers).json()
        for order in res:
            self.process_order(order).with_delay()

    def process_order(self, order):
       #TODO process json
       return 


    def fetch_channable_orders(self):
        for record in self:
            headers = {'Authorization': "Bearer {}".format(record.api_token)}
            req = '%s/companies/%s/projects/%s/orders?%s' % (record.url, record.company, record.project, record.params)
            self.queue_request(req, headers).with_delay()
            

