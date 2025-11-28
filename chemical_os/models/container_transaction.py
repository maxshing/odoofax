# -*- coding: utf-8 -*-
"""
Container Transaction Model
===========================

The "Passbook Entries" for container movements.

This model records every container movement transaction, providing
a complete audit trail for the container ledger. Each transaction
updates the ledger balances and creates an immutable history record.

Transaction Types:
    - buyback: Customer sells drums back to us (Mode A)
    - return_loan: Customer returns loaned drums (Mode B)
    - customer_inbound: Customer's own drums arrive (Mode C)
    - loan_out: We lend drums to customer
    - customer_outbound: Customer's drums leave our facility

This replaces manual passbook entries with structured, auditable data.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ChemicalContainerTransaction(models.Model):
    _name = 'chemical.container.transaction'
    _description = 'Container Transaction'
    _order = 'create_date desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )
    
    ledger_id = fields.Many2one(
        'chemical.container.ledger',
        string='Container Ledger',
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='restrict',
        index=True,
    )
    
    container_spec_id = fields.Many2one(
        'chemical.container.spec',
        string='Container Specification',
        required=True,
        ondelete='restrict',
    )
    
    transaction_type = fields.Selection(
        selection=[
            ('buyback', 'Buyback (原裝桶購回)'),
            ('return_loan', 'Return Loan (歸還借桶)'),
            ('customer_inbound', 'Customer Inbound (自備桶進廠)'),
            ('loan_out', 'Loan Out (借桶出貨)'),
            ('customer_outbound', 'Customer Outbound (自備桶出貨)'),
        ],
        string='Transaction Type',
        required=True,
        index=True,
    )
    
    direction = fields.Selection(
        selection=[
            ('inbound', 'Inbound (進)'),
            ('outbound', 'Outbound (出)'),
        ],
        string='Direction',
        required=True,
    )
    
    quantity = fields.Integer(
        string='Quantity',
        required=True,
    )
    
    # Financial fields for buyback transactions
    unit_price = fields.Float(
        string='Unit Price',
        digits='Product Price',
    )
    
    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
        digits='Account',
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    
    # References to related documents
    credit_note_id = fields.Many2one(
        'account.move',
        string='Credit Note',
        readonly=True,
        help='Credit note generated for buyback transactions.',
    )
    
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        readonly=True,
        help='Stock movement for physical drum transfer.',
    )
    
    # Balance snapshots (for passbook display)
    balance_loaned_before = fields.Integer(
        string='Loaned Balance Before',
        readonly=True,
    )
    
    balance_loaned_after = fields.Integer(
        string='Loaned Balance After',
        readonly=True,
    )
    
    balance_customer_before = fields.Integer(
        string='Customer Balance Before',
        readonly=True,
    )
    
    balance_customer_after = fields.Integer(
        string='Customer Balance After',
        readonly=True,
    )
    
    notes = fields.Text(string='Notes')
    
    processed_by = fields.Many2one(
        'res.users',
        string='Processed By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    
    @api.depends('partner_id', 'container_spec_id', 'transaction_type', 'quantity')
    def _compute_display_name(self):
        type_labels = {
            'buyback': '購回',
            'return_loan': '還桶',
            'customer_inbound': '進廠',
            'loan_out': '借出',
            'customer_outbound': '出貨',
        }
        for rec in self:
            partner = rec.partner_id.name or ''
            spec = rec.container_spec_id.name or ''
            type_label = type_labels.get(rec.transaction_type, '')
            rec.display_name = f"{partner} - {type_label} {rec.quantity}個 {spec}"
    
    @api.depends('quantity', 'unit_price')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = rec.quantity * (rec.unit_price or 0.0)
    
    @api.model
    def create_transaction(self, ledger, transaction_type, quantity, direction, **kwargs):
        """
        Create a transaction record and update ledger balances.
        
        This is the primary method for recording container movements.
        It captures balance snapshots before/after for audit trail.
        
        Args:
            ledger: Container ledger record
            transaction_type: Type of transaction
            quantity: Number of containers
            direction: 'inbound' or 'outbound'
            **kwargs: Additional fields (unit_price, notes, etc.)
            
        Returns:
            Created transaction record
        """
        # Capture balances before
        balance_loaned_before = ledger.balance_loaned
        balance_customer_before = ledger.balance_customer_owned
        
        # Create transaction
        vals = {
            'ledger_id': ledger.id,
            'partner_id': ledger.partner_id.id,
            'container_spec_id': ledger.container_spec_id.id,
            'transaction_type': transaction_type,
            'quantity': quantity,
            'direction': direction,
            'balance_loaned_before': balance_loaned_before,
            'balance_customer_before': balance_customer_before,
            **kwargs,
        }
        
        transaction = self.create(vals)
        
        # Update ledger balances based on transaction type
        if transaction_type in ('return_loan', 'buyback'):
            # Customer returning loaned drums
            ledger.action_update_balance('loaned', quantity, 'inbound')
        elif transaction_type == 'customer_inbound':
            # Customer's drums arriving
            ledger.action_update_balance('customer_owned', quantity, 'inbound')
        elif transaction_type == 'loan_out':
            # We lending drums to customer
            ledger.action_update_balance('loaned', quantity, 'outbound')
        elif transaction_type == 'customer_outbound':
            # Customer's drums leaving
            ledger.action_update_balance('customer_owned', quantity, 'outbound')
        
        # Capture balances after
        transaction.write({
            'balance_loaned_after': ledger.balance_loaned,
            'balance_customer_after': ledger.balance_customer_owned,
        })
        
        return transaction
