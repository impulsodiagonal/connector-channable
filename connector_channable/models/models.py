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
        if not 'orders' in res:
            return
        done = self.env['sale.order'].search_read([('origin', '!=', False)], ['origin'])
        for order in res['orders']:
            if order['id'] not in done:
                self.process_order(order).with_delay()

    def find_product(self, line):
        if 'ean' in line:
            p = self.env['product.product'].search([('ean', '=', line['ean'])])
            if p:
                return p
        if 'article_number' in line:
            p = self.env['product.product'].search([('barcode', '=', line['article_number'])])
            if p:
                return p
        if 'reference_code' in line:
            p = self.env['product.product'].search([('defaul_code', '=', line['reference_code'])])
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
        #create/set partner
        p = order['customer']
        p_data = {
            'name': p['fist_name']+ ' ' + p['last_name'],
            'phone': p['phone'],
            'mobile': p['mobile'],
            'email': p['email'],
            'company_type': 'company',
        }
        partner = self.env['res.partner'].create(p_data)
        #create/set billing address
        b = order['billing']
        b_data = {
            'name': b['fist_name']+ ' ' + b['last_name'],
            'street': b['address1'],
            'steet2': b['address2'],
            'city': b['city'],
            'zip': b['zip_code'],
            'parent_id': partner.id,
            'email': b['email'],
            'company_type': 'invoice',
            'vat': b['vat_number']
        }
        zip_id = self.env['res.city.zip'].search([('name', '=', b['zip_code'])])
        if zip_id and len(zip_id) == 1:
            b_data['zip_id'] = zip_id.id
        else:
            b_data['country_id'] = self.env['res.country'].search([('code', '=', b['country_code'])]) or None
            b_data['state_id'] = self.env['res.country.state'].search([('code', '=', b['region_code'])]) or None
        billing = self.env['res.partner'].create(b_data)

       #create/set shipping address
        s = order['shipping']
        s_data = {
            'name': s['fist_name']+ ' ' + s['last_name'],
            'street': s['address1'],
            'steet2': s['address2'],
            'city': s['city'],
            'zip': s['zip_code'],
            'parent_id': partner.id,
            'email': s['email'],
            'company_type': 'delivery',
            'vat': s['vat_number']
        }
        zip_id = self.env['res.city.zip'].search([('name', '=', s['zip_code'])])
        if zip_id and len(zip_id) == 1:
            s_data['zip_id'] = zip_id.id
        else:
            s_data['country_id'] = self.env['res.country'].search([('code', '=', s['country_code'])]) or None
            s_data['state_id'] = self.env['res.country.state'].search([('code', '=', s['region_code'])]) or None
        delivery = self.env['res.partner'].create(s_data)

        #create order data
        saleorder_data = {}
        saleorder_data['name'] = order['id']
        saleorder_data['origin'] = order['id']
        saleorder_data['partner_id'] = partner.id
        saleorder_data['partner_invoice_id'] = billing.id
        saleorder_data['partner_shipping_id'] = delivery.id
        saleorder_data['date_order'] = datetime.strptime(order['created'], '%Y-%m-%dT%H:%M:%S')
        saleorder_data['user_id'] = 1
        o_saleorder = self.env['sale.order'].create(saleorder_data)

        #create order lines
        for line in order['products']:
            product = find_product(line)
            line_data = {
                'order_id': o_saleorder.id,
                'name': line['title'],
                'product_id': product.id or None,
                'product_qty': line['quantity'],
                'price_unit': line['price'],
                'tax_id' : [(6, 0, [GLOBAL_TAX_ID])]
            }
            o_saleorder_line = self.env['sale.order.line'].create(line_data)
        #finish order
        return 


    def fetch_channable_orders(self):
        for record in self:
            headers = {'Authorization': "Bearer {}".format(record.api_token)}
            req = '/%s/companies/%s/projects/%s/orders?%s' % (record.url, record.company, record.project, record.params)
            self.queue_request(req, headers).with_delay()
            

