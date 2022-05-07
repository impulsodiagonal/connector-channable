from odoo import models, fields, api
import json
import requests
from datetime import datetime


class ChannableChannels(models.Model):
    _name = 'connector.channable.connection.channel'
    _description = 'Connector Chanable Connection Channel'

    name = fields.Char('Name', required=True)
    medium_id = fields.Many2one('utm.medium')
    category_ids = fields.Many2many('res.partner.category', 
                                    column1='channel_id',
                                    column2='category_id', 
                                    string='Channel Partner Tags')
    connection_id = fields.Many2one(comodel_name='connector.channable.connection')

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
    channel_ids = fields.One2many(
                                comodel_name='connector.channable.connection.channel',
                                inverse_name='connection_id', 
                                string='Channels')

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False

    def queue_request(self, req, headers):
        res = requests.get(req, headers=headers).json()
        if not 'orders' in res:
            return
        done = [order['origin'] for order in self.env['sale.order'].search_read(
            [('origin', '!=', False)], ['origin'])]
        for order in res['orders']:
            if str(order['id']) not in done:
                self.with_delay().process_order(order)

    def find_product(self, line):
        #do main search following channable rules ->
        #article_number = official identifier
        if 'article_number' in line:
            p = self.env['product.product'].search(
                [('barcode', '=', line['article_number'])])
            if p:
                return p
        if 'article_number' in line:
            p = self.env['product.product'].search(
                [('amazon_id', '=', line['article_number'])])
            if p:
                return p
        #do extendend search
        if 'ean' in line:
            p = self.env['product.product'].search(
                [('barcode', '=', line['ean'])])
            if p:
                return p
        if 'reference_code' in line:
            p = self.env['product.product'].search(
                [('default_code', '=', line['reference_code'])])
            if p:
                return p
        if 'title' in line:
            p = self.env['product.product'].search(
                [('name', '=', line['title'])])
            if p:
                return p
        return False

    def find_partner(self, data, parent_id=None, partner_type=None):
        filters = [('email', '=', data['email'])]
        if parent_id:
            filters += [
                ('parent_id', '=', parent_id),
                ('name', '=', data['first_name']+ ' ' + data['last_name']),
                ('street','=', data['address1']),
                ('street2', '=', data['address2']),
                ('zip', '=', data['zip_code']),
            ]
        else:
            filters += [('type', '=', 'contact')]
        if partner_type == 'invoice':
            filters += [('type', '=', 'invoice')]
        elif partner_type == 'delivery': 
            filters += [('type', '=', 'delivery')]

        res = self.env['res.partner'].search(filters)
        return res

    def create_partner(self, data, parent_id=None, partner_type=None):
        partner_data = {
            'name': data['first_name']+ ' ' + data['last_name'],
            'email': data['email'],
        }
        if not partner_type:
            partner_data['phone'] = data['phone']
            partner_data['mobile'] = data['mobile']
            partner_data['company_type'] = 'company'

        else:
            partner_data['street'] = data['address1']
            partner_data['street2'] = data['address2']
            partner_data['parent_id'] = parent_id
            partner_data['company_type'] = 'person'

            if partner_type == 'invoice':
                partner_data['type'] = 'invoice'
            elif partner_type == 'delivery':
                partner_data['type'] = 'delivery'

            zip_id = self.env['res.city.zip'].search(
                [('name', '=', data['zip_code'])])
            if zip_id and len(zip_id) == 1:
                partner_data['zip_id'] = zip_id.id
                partner_data['zip'] = zip_id.name
                partner_data['state_id'] = zip_id.city_id.state_id.id
                partner_data['country_id'] = zip_id.city_id.country_id.id
                partner_data['city_id'] = zip_id.city_id.id
                partner_data['city'] = zip_id.city_id.name
            else:
                partner_data['country_id'] = self.env['res.country'].search(
                    [('code', '=', data['country_code'])]).id or None
                partner_data['city'] = data['city']
                partner_data['zip'] = data['zip_code']
                if partner_data['country_id']:
                    partner_data['state_id'] = self.env['res.country.state'].search(
                        [('country_id', '=', partner_data['country_id']),
                        ('code', '=', data['region_code'])]).id or None
        
        res = self.env['res.partner'].create(partner_data)
        try:
            res.vat = data['vat_number']
        except:
            vat_error = True
        return res

    def process_order(self, order):
        #TODO process json
        GLOBAL_TAX_ID = 1
        GLOBAL_TAX_PRCT = 1.21
        vat_error = False
        MEDIUM = self.env['connector.channable.connection.channel'].search(
            [('name', '=', order['channel_name'])])

        #create/set partner
        p = order['data']['customer']
        partner = self.find_partner(p)
        if not partner:
            partner = self.create_partner(p)
            
        #create/set billing address
        b = order['data']['billing']
        billing = self.find_partner(b, partner.id, 'invoice')
        if not billing:
            billing = self.create_partner(b, partner.id, 'invoice')

        #create/set shipping address
        s = order['data']['shipping']
        delivery = self.find_partner(s, partner.id, 'delivery')
        if not delivery:
            delivery = self.create_partner(s, partner.id, 'delivery')

        #create order data
        saleorder_data = {}
        # saleorder_data['name'] = order['id']
        saleorder_data['origin'] = order['id']
        saleorder_data['partner_id'] = partner.id
        saleorder_data['partner_invoice_id'] = billing.id
        saleorder_data['partner_shipping_id'] = delivery.id
        saleorder_data['date_order'] = order['created'][:19].replace('T', ' ')
        saleorder_data['user_id'] = 1
        saleorder_data['fiscal_position_id'] = 1
        
        #detect fiscal position and OSS stuff
        country_fp = self.env['account.fiscal.position'].search(
            [('country_id', '=', delivery.country_id.id)])
        if country_fp and len(country_fp) == 1:
            saleorder_data['fiscal_position_id'] = country_fp.id
            GLOBAL_TAX_ID = country_fp.tax_ids[0].tax_dest_id.id
            GLOBAL_TAX_PRCT = country_fp.tax_ids[0].tax_dest_id.amount

        if MEDIUM:
            saleorder_data['medium_id'] = MEDIUM.medium_id.id

        o_saleorder = self.env['sale.order'].create(saleorder_data)

        #create order lines
        for line in order['data']['products']:
            product = self.find_product(line)
            if not product:
                raise UserError(_('Channable error: Missing product %s!' % line))
            if len(product) !=1:
                raise UserError(_('Channable error: Too many products %s' % line))
            line_data = {
                'order_id': o_saleorder.id,
                'name': line['title'],
                'product_uom_qty': line['quantity'],
                'product_id': product.id,
            }

            #analyze taxes, subtotal and guess it if necessary
            if line['price_tax']:
                #case1 has taxes, hurray!
                base = (line['price'] - line['price_tax']) / line['quantity']
            else:
                #case2 don't have taxes, infere it
                base = line['price'] / line['quantity']
                base = base / (GLOBAL_TAX_PRCT/100+1)
            line_data['price_unit'] =  base
            line_data['tax_id'] = [(6, 0, [GLOBAL_TAX_ID])]

            o_saleorder_line = self.env['sale.order.line'].create(line_data)
        #finish order
        return 


    def fetch_channable_orders(self):
        conns = self.env['connector.channable.connection'].search([])
        for record in conns:
            headers = {'Authorization': "Bearer {}".format(record.api_token)}
            req = '%s/companies/%s/projects/%s/orders?%s' % (
                record.url,
                record.company, 
                record.project, 
                record.params)
            self.with_delay().queue_request(req, headers)
            

