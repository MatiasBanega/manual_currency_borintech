# -*- coding: utf-8 -*-

from odoo import fields, models,api, _
from odoo.exceptions import Warning

class SaleOrder(models.Model):
    _inherit ='sale.order'
    
    sale_manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
    sale_manual_currency_rate = fields.Float('Rate', digits=(12, 6))


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}
        vals = {}
        domain = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
            vals['product_uom_qty'] = 1.0

        product = self.product_id.with_context(
            lang=self.order_id.partner_id.lang,
            partner=self.order_id.partner_id.id,
            quantity=vals.get('product_uom_qty') or self.product_uom_qty,
            date=self.order_id.date_order,
            pricelist=self.order_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        result = {'domain': domain}

        title = False
        message = False
        warning = {}
        if product.sale_line_warn != 'no-message':
            title = _("Warning for %s") % product.name
            message = product.sale_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            result = {'warning': warning}
            if product.sale_line_warn == 'block':
                self.product_id = False
                return result

        name = product.name_get()[0][1]
        if product.description_sale:
            name += '\n' + product.description_sale
        vals['name'] = name
        
        self._compute_tax_id()
        price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product),
                                                                                     product.taxes_id, self.tax_id,
                                                                                     self.company_id)
        if self.order_id.sale_manual_currency_rate_active:
            sale_manual_currency_rate = price_unit * self.order_id.sale_manual_currency_rate
            vals['price_unit'] = sale_manual_currency_rate
            vals['name'] = self.product_id.name

        self.update(vals)

        return result


    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.order_id.pricelist_id:
            raise Warning(_("Please Select Pricelist First."))
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.order_id.pricelist_id and self.order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.order_id.partner_id.lang,
                partner=self.order_id.partner_id.id,
                quantity=self.product_uom_qty,
                date=self.order_id.date_order,
                pricelist=self.order_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
        price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product),
                                                                                  product.taxes_id, self.tax_id,
                                                                                  self.company_id)
        if self.order_id.sale_manual_currency_rate_active:
            self.price_unit = price_unit * self.order_id.sale_manual_currency_rate
            self.name = self.product_id.name


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def _create_invoice(self, order, so_line, amount):
        res = super(SaleAdvancePaymentInv,self)._create_invoice(order, so_line, amount)
        if order.sale_manual_currency_rate_active:
            res.write({'manual_currency_rate_active':order.sale_manual_currency_rate_active,'manual_currency_rate':order.sale_manual_currency_rate})
        return res

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _create_invoices(self, grouped=False, final=False):
        res = super(SaleOrder,self)._create_invoices(grouped=False, final=False)
        invoice_obj = self.env['account.move'].browse(res.id)
        if self.sale_manual_currency_rate_active:
            invoice_obj.write({'manual_currency_rate_active':self.sale_manual_currency_rate_active,'manual_currency_rate':self.sale_manual_currency_rate})
        return invoice_obj
