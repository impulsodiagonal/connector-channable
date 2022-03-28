# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json
import requests
from odoo.addons.queue_job.job import job
from datetime import datetime


class ConnectorChannableConnection(models.Model):
    _name = 'connector.channable.connection'
    _description = 'Connector Chanable Connection'

    name = fields.Char('Name', required=True)
    api_token = fields.Char('Token', required=True)
    company = fields.Char('Company', required=True)
    project = fields.Char('Project', required=True)
    active = fields.Boolean('State', default=False)
    url = fields.Char('Url', default='https://api.channable.com/v1')
    params = fields.Char('Parameters', default='limit=100')

    
    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False

    def queue_request(self, req, headers):
        res = requests.get(req, headers=headers).json()
        if not 'orders' in res:
            return
        done = self.env['sale.order'].search_read([('origin', '!=', False)], ['origin'])
        for order in res['orders']:
            if order['id'] not in done:
                self.with_delay().process_order(order)

    def find_product(self, line):
        if 'ean' in line:
            p = self.env['product.product'].search([('barcode', '=', line['ean'])])
            if p:
                return p
        if 'article_number' in line:
            p = self.env['product.product'].search([('barcode', '=', line['article_number'])])
            if p:
                return p
        if 'reference_code' in line:
            p = self.env['product.product'].search([('default_code', '=', line['reference_code'])])
            if p:
                return p
        if 'title' in line:
            p = self.env['product.product'].search([('name', '=', line['title'])])
            if p:
                return p
        return False

    def process_order(self, order):
        #TODO process json
        GLOBAL_TAX_ID = 1
        vat_error = False
        #create/set partner
        p = order['data']['customer']
        p_data = {
            'name': p['first_name']+ ' ' + p['last_name'],
            'phone': p['phone'],
            'mobile': p['mobile'],
            'email': p['email'],
            'company_type': 'company',
        }
        partner = self.env['res.partner'].create(p_data)
        #create/set billing address
        b = order['data']['billing']
        b_data = {
            'name': b['first_name']+ ' ' + b['last_name'],
            'street': b['address1'],
            'street2': b['address2'],
            'city': b['city'],
            'zip': b['zip_code'],
            'parent_id': partner.id,
            'email': b['email'],
            'type': 'invoice',
            'company_type': 'person',
            # 'vat': b['vat_number']
        }
        zip_id = self.env['res.city.zip'].search([('name', '=', b['zip_code'])])
        if zip_id and len(zip_id) == 1:
            b_data['zip_id'] = zip_id.id
        else:
            b_data['country_id'] = self.env['res.country'].search([('code', '=', b['country_code'])]).id or None
            if b_data['country_id']:
                b_data['state_id'] = self.env['res.country.state'].search([('country_id', '=', b_data['country_id']),('code', '=', b['region_code'])]).id or None
        billing = self.env['res.partner'].create(b_data)
        try:
            billing.vat = b['vat_number']
        except:
            vat_error = True

       #create/set shipping address
        s = order['data']['shipping']
        s_data = {
            'name': s['first_name']+ ' ' + s['last_name'],
            'street': s['address1'],
            'street2': s['address2'],
            'city': s['city'],
            'zip': s['zip_code'],
            'parent_id': partner.id,
            'email': s['email'],
            'type': 'delivery',
            'company_type': 'person',
            # 'vat': s['vat_number']
        }
        zip_id = self.env['res.city.zip'].search([('name', '=', s['zip_code'])])
        if zip_id and len(zip_id) == 1:
            s_data['zip_id'] = zip_id.id
        else:
            s_data['country_id'] = self.env['res.country'].search([('code', '=', s['country_code'])]).id or None
            if s_data['country_id']:
                s_data['state_id'] = self.env['res.country.state'].search([('country_id', '=', s_data['country_id']),('code', '=', s['region_code'])]).id or None
        delivery = self.env['res.partner'].create(s_data)
        try:
            delivery.vat = s['vat_number']
        except:
            vat_error = True

        #create order data
        saleorder_data = {}
        saleorder_data['name'] = order['id']
        saleorder_data['origin'] = order['id']
        saleorder_data['partner_id'] = partner.id
        saleorder_data['partner_invoice_id'] = billing.id
        saleorder_data['partner_shipping_id'] = delivery.id
        saleorder_data['date_order'] = datetime.strftime(datetime.fromisoformat(order['created']),'%Y-%m-%d %H:%M:%S')
        saleorder_data['user_id'] = 1
        o_saleorder = self.env['sale.order'].create(saleorder_data)

        #create order lines
        for line in order['data']['products']:
            product = self.find_product(line)
            line_data = {
                'order_id': o_saleorder.id,
                'name': line['title'],
                'product_uom_qty': line['quantity'],
                'price_unit': line['price'],
                'tax_id' : [(6, 0, [GLOBAL_TAX_ID])]
            }
            if product:
                line_data['product_id'] = product.id
            o_saleorder_line = self.env['sale.order.line'].create(line_data)
        #finish order
        return 


    def fetch_channable_orders(self):
        print('entro cron', self)
        conns = self.env['connector.channable.connection'].search([])
        for record in conns:
            print('inside',2)
            headers = {'Authorization': "Bearer {}".format(record.api_token)}
            req = '%s/companies/%s/projects/%s/orders?%s' % (record.url, record.company, record.project, record.params)
            self.with_delay().queue_request(req, headers)
            

