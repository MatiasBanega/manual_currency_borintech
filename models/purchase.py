# -*- coding: utf-8 -*-

from odoo import fields, models,api
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

class PurchaseOrder(models.Model):
	_inherit ='purchase.order'
	
	purchase_manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
	purchase_manual_currency_rate = fields.Float('Rate', digits=(12, 6))

	def action_create_invoice(self):
		res = super(PurchaseOrder, self).action_create_invoice()
		move_ids = self.env['account.move'].search([('id', '=', res.get('res_id'))])
		if move_ids:
			move_ids.update({
				'manual_currency_rate_active': self.purchase_manual_currency_rate_active,
				'manual_currency_rate': self.purchase_manual_currency_rate,

			})
		return res

class PurchaseOrderLine(models.Model):
	_inherit ='purchase.order.line'


	def _prepare_stock_moves(self, picking):
		""" Prepare the stock moves data for one order line. This function returns a list of
		dictionary ready to be used in stock.move's create()
		"""
		rec  = super(PurchaseOrderLine, self)._prepare_stock_moves(picking)
		seller = self.product_id._select_seller(
			partner_id=self.partner_id,
			quantity=self.product_qty,
			date=self.order_id.date_order,
			uom_id=self.product_uom)
		
		price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price, self.product_id.supplier_taxes_id, self.taxes_id, self.company_id) if seller else 0.0
		if price_unit and seller and self.order_id.currency_id and seller.currency_id != self.order_id.currency_id:
			price_unit = seller.currency_id.compute(price_unit, self.order_id.currency_id)

		if seller and self.product_uom and seller.product_uom != self.product_uom:
			price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)
		
		if self.order_id.purchase_manual_currency_rate_active:
			price_unit = self.order_id.currency_id.round((self.price_unit)/self.order_id.purchase_manual_currency_rate)
		
		

		for line in rec :

			line.update({'price_unit' : price_unit})

		
		return rec
	
	@api.onchange('product_qty', 'product_uom')
	def _onchange_quantity(self):
		if not self.product_id:
			return

		seller = self.product_id._select_seller(
			partner_id=self.partner_id,
			quantity=self.product_qty,
			date=self.order_id.date_order,
			uom_id=self.product_uom)

		if seller or not self.date_planned:
			self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

		if not seller:
			return

		price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price, self.product_id.supplier_taxes_id, self.taxes_id, self.company_id) if seller else 0.0
		pu = price_unit
		if price_unit and seller and self.order_id.currency_id and seller.currency_id != self.order_id.currency_id:
			price_unit = seller.currency_id.compute(price_unit, self.order_id.currency_id)

		if seller and self.product_uom and seller.product_uom != self.product_uom:
			price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)

		if self.order_id.purchase_manual_currency_rate_active:
			price_unit = price_unit * self.order_id.purchase_manual_currency_rate

		self.price_unit = price_unit


class AccountInvoice(models.Model):
	_inherit = 'account.move'



	@api.onchange('purchase_vendor_bill_id', 'purchase_id')
	def _onchange_purchase_auto_complete(self):
		''' Load from either an old purchase order, either an old vendor bill.

		When setting a 'purchase.bill.union' in 'purchase_vendor_bill_id':
		* If it's a vendor bill, 'invoice_vendor_bill_id' is set and the loading is done by '_onchange_invoice_vendor_bill'.
		* If it's a purchase order, 'purchase_id' is set and this method will load lines.

		/!\ All this not-stored fields must be empty at the end of this function.
		'''
		if self.purchase_vendor_bill_id.vendor_bill_id:
			self.invoice_vendor_bill_id = self.purchase_vendor_bill_id.vendor_bill_id
			self._onchange_invoice_vendor_bill()
		elif self.purchase_vendor_bill_id.purchase_order_id:
			self.purchase_id = self.purchase_vendor_bill_id.purchase_order_id
		self.purchase_vendor_bill_id = False

		if not self.purchase_id:
			return

		# Copy partner.
		self.partner_id = self.purchase_id.partner_id
		self.fiscal_position_id = self.purchase_id.fiscal_position_id
		self.invoice_payment_term_id = self.purchase_id.payment_term_id
		self.currency_id = self.purchase_id.currency_id

		if self.purchase_id.purchase_manual_currency_rate_active:
			self.manual_currency_rate_active = self.purchase_id.purchase_manual_currency_rate_active
			self.manual_currency_rate = self.purchase_id.purchase_manual_currency_rate

		# Copy purchase lines.
		po_lines = self.purchase_id.order_line - self.line_ids.mapped('purchase_line_id')
		new_lines = self.env['account.move.line']
		for line in po_lines.filtered(lambda l: not l.display_type):
			new_line = new_lines.new(line._prepare_account_move_line(self))
			new_line.account_id = new_line._get_computed_account()
			new_line._onchange_price_subtotal()
			new_lines += new_line
		new_lines._onchange_mark_recompute_taxes()

		# Compute invoice_origin.
		origins = set(self.line_ids.mapped('purchase_line_id.order_id.name'))
		self.invoice_origin = ','.join(list(origins))

		# Compute ref.
		refs = set(self.line_ids.mapped('purchase_line_id.order_id.partner_ref'))
		refs = [ref for ref in refs if ref]
		self.ref = ','.join(refs)

		# Compute _invoice_payment_ref.
		if len(refs) == 1:
			self._invoice_payment_ref = refs[0]

		self.purchase_id = False
		self._onchange_currency()        
