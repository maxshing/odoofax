# -*- coding: utf-8 -*-
"""
Container Ledger Model
======================

The "Container Passbook" for tracking customer container accounts.

Business Problem:
    A single customer may have three types of drum interactions simultaneously:
    1. Loaned drums (借桶) - We lend drums to customer
    2. Customer-owned drums (自備桶) - Customer's drums in our facility
    3. Buyback transactions - Customer returns drums for credit
    
Solution:
    This ledger tracks all container movements and balances per customer,
    similar to a bank passbook (存摺) for containers.

Ledger Entry Types:
    - 前欠 (Previous Balance)
    - 本期借 (Current Period Loans)
    - 本期還 (Current Period Returns)
    - 結存 (Current Balance)
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ChemicalContainerLedger(models.Model):
    _name = 'chemical.container.ledger'
    _description = 'Customer Container Ledger'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'partner_id, container_spec_id'
    
    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='cascade',
        tracking=True,
        domain="[('customer_rank', '>', 0)]",
    )
    
    container_spec_id = fields.Many2one(
        'chemical.container.spec',
        string='Container Specification',
        required=True,
        tracking=True,
        help='The type of container being tracked.',
    )
    
    # Balance Fields - The "Passbook" entries
    balance_loaned = fields.Integer(
        string='Loaned Balance (借出餘額)',
        default=0,
        tracking=True,
        help='Quantity of drums currently lent to this customer. 目前借給客戶的桶數。',
    )
    
    balance_customer_owned = fields.Integer(
        string='Customer Owned Balance (自備桶餘額)',
        default=0,
        tracking=True,
        help="Quantity of customer's own drums currently in our plant. 客戶自備桶目前在廠內的數量。",
    )
    
    # Period tracking
    period_loaned = fields.Integer(
        string='Period Loans (本期借)',
        default=0,
        help='Drums loaned out this period.',
    )
    
    period_returned = fields.Integer(
        string='Period Returns (本期還)',
        default=0,
        help='Drums returned this period.',
    )
    
    # Monetary values
    total_deposit = fields.Float(
        string='Total Deposit (總押金)',
        compute='_compute_totals',
        store=True,
        help='Total deposit amount held for loaned containers.',
    )
    
    total_value = fields.Float(
        string='Total Container Value',
        compute='_compute_totals',
        store=True,
    )
    
    # Audit fields
    last_movement_date = fields.Datetime(
        string='Last Movement',
        tracking=True,
    )
    
    notes = fields.Text(string='Notes')
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    
    # Transaction history - The actual passbook entries
    transaction_ids = fields.One2many(
        'chemical.container.transaction',
        'ledger_id',
        string='Transactions',
        help='Container movement history (存摺明細)',
    )
    
    transaction_count = fields.Integer(
        string='Transaction Count',
        compute='_compute_transaction_count',
    )
    
    @api.depends('transaction_ids')
    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = len(rec.transaction_ids)
    
    _sql_constraints = [
        ('partner_container_unique', 
         'UNIQUE(partner_id, container_spec_id)', 
         'Each customer can only have one ledger entry per container type!'),
    ]
    
    @api.depends('partner_id', 'container_spec_id')
    def _compute_name(self):
        for rec in self:
            partner_name = rec.partner_id.name or 'Unknown'
            spec_name = rec.container_spec_id.name or 'Unknown Spec'
            rec.name = f"{partner_name} - {spec_name}"
    
    @api.depends('balance_loaned', 'container_spec_id.deposit_amount', 'container_spec_id.buyback_price')
    def _compute_totals(self):
        for rec in self:
            deposit = rec.container_spec_id.deposit_amount or 0.0
            buyback = rec.container_spec_id.buyback_price or 0.0
            rec.total_deposit = rec.balance_loaned * deposit
            rec.total_value = rec.balance_loaned * buyback
    
    def action_update_balance(self, movement_type, quantity, direction):
        """
        Update container balance based on movement.
        
        This is the core method for all container transactions.
        
        Args:
            movement_type: 'loaned' or 'customer_owned'
            quantity: Number of containers
            direction: 'inbound' (to us) or 'outbound' (to customer)
            
        Returns:
            Updated record
            
        Raises:
            ValidationError: If operation would result in negative balance
        """
        self.ensure_one()
        
        if quantity <= 0:
            raise ValidationError(_('Quantity must be positive.'))
        
        if movement_type == 'loaned':
            if direction == 'outbound':
                # We're lending drums to customer
                self.balance_loaned += quantity
                self.period_loaned += quantity
            elif direction == 'inbound':
                # Customer returning loaned drums
                if self.balance_loaned < quantity:
                    raise ValidationError(
                        _('Cannot return more drums than currently loaned. '
                          'Current loaned balance: %d') % self.balance_loaned
                    )
                self.balance_loaned -= quantity
                self.period_returned += quantity
                
        elif movement_type == 'customer_owned':
            if direction == 'inbound':
                # Customer's drums arriving at our plant
                self.balance_customer_owned += quantity
            elif direction == 'outbound':
                # Customer's drums leaving our plant
                if self.balance_customer_owned < quantity:
                    raise ValidationError(
                        _('Cannot send out more customer drums than in stock. '
                          'Current balance: %d') % self.balance_customer_owned
                    )
                self.balance_customer_owned -= quantity
        
        self.last_movement_date = fields.Datetime.now()
        
        return self
    
    def action_reset_period(self):
        """Reset period counters (typically at month end)."""
        for rec in self:
            rec.period_loaned = 0
            rec.period_returned = 0
        return True
    
    @api.model
    def get_or_create_ledger(self, partner_id, container_spec_id):
        """
        Get existing ledger or create new one for partner/container combination.
        
        Args:
            partner_id: res.partner record ID
            container_spec_id: chemical.container.spec record ID
            
        Returns:
            Ledger record
        """
        ledger = self.search([
            ('partner_id', '=', partner_id),
            ('container_spec_id', '=', container_spec_id),
        ], limit=1)
        
        if not ledger:
            ledger = self.create({
                'partner_id': partner_id,
                'container_spec_id': container_spec_id,
            })
        
        return ledger
    
    def action_view_movements(self):
        """Open related stock movements for this container type."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Container Movements'),
            'res_model': 'stock.move',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', '=', self.partner_id.id),
                # Additional domain based on container spec if needed
            ],
            'context': {'default_partner_id': self.partner_id.id},
        }
