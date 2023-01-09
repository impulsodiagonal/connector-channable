# Copyright 2021 - Impulso Diagonal
# Copyright 2022 - Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import requests

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tests import Form


class ChannableChannels(models.Model):
    _name = "connector.channable.connection.channel"
    _description = "Connector Chanable Connection Channel"

    name = fields.Char("Name", required=True)
    medium_id = fields.Many2one("utm.medium")
    category_ids = fields.Many2many(
        "res.partner.category",
        column1="channel_id",
        column2="category_id",
        string="Channel Partner Tags",
    )
    connection_id = fields.Many2one(comodel_name="connector.channable.connection")
    user_id = fields.Many2one("res.users")


class ConnectorChannableConnection(models.Model):
    _name = "connector.channable.connection"
    _description = "Connector Chanable Connection"

    name = fields.Char("Name", required=True)
    api_token = fields.Char("Token", required=True)
    company = fields.Char("Company", required=True)
    project = fields.Char("Project", required=True)
    active = fields.Boolean("State", default=False)
    url = fields.Char("Url", default="https://api.channable.com/v1")
    params = fields.Char("Parameters", default="limit=100")
    channel_ids = fields.One2many(
        comodel_name="connector.channable.connection.channel",
        inverse_name="connection_id",
        string="Channels",
    )

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False

    def queue_request(self, req, headers):
        res = requests.get(req, headers=headers).json()
        if "orders" not in res:
            return
        SaleOrder = self.env["sale.order"]
        QueueJob = self.env["queue.job"]
        for order in res["orders"]:
            # Search existing sales order
            if SaleOrder.search([("origin", "=", str(order["id"]))]):
                continue
            # Search existing pending jobs
            if QueueJob.search(
                [
                    ("func_string", "like", f"'id': {order['id']},"),
                    ("state", "in", ["pending", "failed", "enqueued", "started"]),
                ]
            ):
                continue
            self.with_delay().process_order(order)

    def find_product(self, line):
        # do main search following channable rules ->
        # article_number = official identifier
        if "article_number" in line:
            p = self.env["product.product"].search(
                [("amazon_id", "=", line["article_number"])]
            )
            if p and len(p) == 1:
                return p
        if "id" in line:
            p = self.env["product.product"].search([("default_code", "=", line["id"])])
            if p:
                return p
        # do extendend search
        if "ean" in line:
            p = self.env["product.product"].search([("barcode", "=", line["ean"])])
            if p:
                return p
        if "reference_code" in line:
            p = self.env["product.product"].search(
                [("default_code", "=", line["reference_code"])]
            )
            if p:
                return p
        if "title" in line:
            p = self.env["product.product"].search([("name", "=", line["title"])])
            if p:
                return p
        return False

    def find_partner(self, data, parent_id=None, partner_type=None):
        filters = [("email", "=", data["email"])]
        if parent_id:
            filters += [
                ("parent_id", "=", parent_id),
                (
                    "name",
                    "=",
                    (
                        "%s %s" % (data["first_name"] or "", data["last_name"] or "")
                    ).strip(),
                ),
                ("street", "=", data["address1"]),
                ("street2", "=", data["address2"]),
                ("zip", "=", data["zip_code"]),
            ]
        else:
            filters += [("type", "=", "contact")]
        if partner_type == "invoice":
            filters += [("type", "=", "invoice")]
        elif partner_type == "delivery":
            filters += [("type", "=", "delivery")]
        res = self.env["res.partner"].search(filters)
        return res

    def create_partner(self, data, extra, parent=None, partner_type=None):
        # search category first
        category_id = self.env["res.partner.category"].search([("name", "=", extra["label"])])

        if not category_id:
            category_id = self.env["res.partner.category"].create({
                "name": extra["label"]
            })
        # prepare partner data
        partner_data = {
            "name": (
                "%s %s" % (data["first_name"] or "", data["last_name"] or "")
            ).strip(),
            "email": data["email"],
            "category_id": [(4, category_id.id)]
        }
        if not partner_type:
            partner_data["phone"] = data["phone"]
            partner_data["mobile"] = data["mobile"]
            partner_data["company_type"] = (
                "company" if data.get("business_order") else "person"
            )
        else:
            partner_data["street"] = data["address1"]
            partner_data["street2"] = data["address2"]
            if parent:
                partner_data.update(
                    {
                        "parent_id": parent.id,
                        "phone": parent.phone,
                        "mobile": parent.mobile,
                    }
                )
            partner_data["company_type"] = "person"
            partner_data["type"] = partner_type
            zip_id = self.env["res.city.zip"].search([("name", "=", data["zip_code"])])
            if zip_id and len(zip_id) == 1:
                partner_data["zip_id"] = zip_id.id
                partner_data["zip"] = zip_id.name
                partner_data["state_id"] = zip_id.city_id.state_id.id
                partner_data["country_id"] = zip_id.city_id.country_id.id
                partner_data["city_id"] = zip_id.city_id.id
                partner_data["city"] = zip_id.city_id.name
            else:
                partner_data["country_id"] = (
                    self.env["res.country"]
                    .search([("code", "=", data["country_code"])])
                    .id
                    or None
                )
                partner_data["city"] = data["city"]
                partner_data["zip"] = data["zip_code"]
                if partner_data["country_id"]:
                    partner_data["state_id"] = (
                        self.env["res.country.state"]
                        .search(
                            [
                                ("country_id", "=", partner_data["country_id"]),
                                ("code", "=", data["region_code"]),
                            ]
                        )
                        .id
                        or None
                    )
        res = self.env["res.partner"].create(partner_data)

        # TODO: change order and create vat in dict?
        try:
            res.vat = data["vat_number"]
        except Exception:
            pass
        return res

    def process_order(self, order):
        # TODO process json
        medium = self.env["connector.channable.connection.channel"].search(
            [("name", "=", order["channel_name"])]
        )
        # create/set partner
        p = order["data"]["customer"]
        e = order["data"]["extra"]
        partner = self.find_partner(p)
        if not partner:
            partner = self.create_partner(p, e)
        # create/set billing address
        b = order["data"]["billing"]
        billing = self.find_partner(b, partner.id, "invoice")
        if not billing:
            billing = self.create_partner(b, e, parent=partner, partner_type="invoice")
        # create/set shipping address
        s = order["data"]["shipping"]
        delivery = self.find_partner(s, partner.id, "delivery")
        if not delivery:
            delivery = self.create_partner(s, e, parent=partner, partner_type="delivery")
        # create order data
        order_form = Form(self.env["sale.order"])
        order_form.partner_id = partner
        order_form.partner_invoice_id = billing
        order_form.partner_shipping_id = delivery
        order_form.origin = order["id"]
        order_form.date_order = order["created"][:19].replace("T", " ")
        order_form.user_id = self.env["res.users"].browse(1)
        if order["channel_name"] == "amazon" and order["channel_id"]:
            # TODO: Don't hardcode values, but for now, there's no specific channel
            if order["channel_id"].endswith("-AFN"):
                # Marketplace LDTL
                order_form.warehouse_id = self.env["stock.warehouse"].browse(31)
        if medium:
            order_form.medium_id = medium.medium_id
            if medium.user_id:
                order_form.user_id = medium.user_id
        # create order lines
        confirm_order = True
        for line in order["data"]["products"]:
            product = self.find_product(line)
            if not product:
                raise UserError(_("Channable error: Missing product %s!" % line))
            if len(product) != 1:
                raise UserError(_("Channable error: Too many products %s" % line))
            with order_form.order_line.new() as line_form:
                line_form.product_id = product
                line_form.name = line["title"]
                line_form.product_uom_qty = line["quantity"]
                if not line.get("price_tax"):
                    # Orders with no tax defined
                    line_form.price_unit = line["price"]
                    confirm_order = False
                else:
                    line_form.price_unit = line["price"] - line["price_tax"]
        order_vals = order_form._values_to_save(all_fields=True)
        if order["channel_name"] == "mirakl_carrefour" and order["platform_id"]:
            order_vals["name"] = order["platform_id"]
        elif order.get("channel_id"):
            # Use this default value, that matches with Amazon, PC Componentes...
            order_vals["name"] = order["channel_id"]
        sale_order = self.env["sale.order"].create(order_vals)
        # finish order only if everything went well
        if confirm_order:
            sale_order.action_confirm()
        return sale_order

    def fetch_channable_orders(self):
        conns = self.env["connector.channable.connection"].search([])
        for record in conns:
            headers = {"Authorization": "Bearer {}".format(record.api_token)}
            req = "%s/companies/%s/projects/%s/orders?%s" % (
                record.url,
                record.company,
                record.project,
                record.params,
            )
            self.with_delay().queue_request(req, headers)
