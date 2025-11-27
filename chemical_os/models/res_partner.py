# -*- coding: utf-8 -*-
"""
Partner Extension for Container Ledger
======================================

Extends res.partner to display container ledger information
directly on the customer form.
"""

from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    container_ledger_ids = fields.One2many(
        'chemical.container.ledger',
        'partner_id',
        string='Container Ledger',
        help='Container passbook entries for this customer.',
    )
    
    container_ledger_count = fields.Integer(
        string='Ledger Entries',
        compute='_compute_container_ledger_count',
    )
    
    total_containers_loaned = fields.Integer(
        string='Total Containers Loaned',
        compute='_compute_container_totals',
        help='Total drums currently lent to this customer.',
    )
    
    total_containers_customer_owned = fields.Integer(
        string='Total Customer Containers',
        compute='_compute_container_totals',
        help="Total customer's own drums in our facility.",
    )
    
    total_container_deposit = fields.Float(
        string='Total Container Deposit',
        compute='_compute_container_totals',
        help='Total deposit amount held for all loaned containers.',
    )
    
    @api.depends('container_ledger_ids')
    def _compute_container_ledger_count(self):
        for partner in self:
            partner.container_ledger_count = len(partner.container_ledger_ids)
    
    @api.depends('container_ledger_ids.balance_loaned', 
                 'container_ledger_ids.balance_customer_owned',
                 'container_ledger_ids.total_deposit')
    def _compute_container_totals(self):
        for partner in self:
            partner.total_containers_loaned = sum(
                partner.container_ledger_ids.mapped('balance_loaned')
            )
            partner.total_containers_customer_owned = sum(
                partner.container_ledger_ids.mapped('balance_customer_owned')
            )
            partner.total_container_deposit = sum(
                partner.container_ledger_ids.mapped('total_deposit')
            )
    
    def action_view_container_ledger(self):
        """Open container ledger for this customer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Container Ledger'),
            'res_model': 'chemical.container.ledger',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
    
    def action_return_drums(self):
        """Open drum return wizard for this customer."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Process Drum Return'),
            'res_model': 'chemical.drum.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_id': self.id},
        }
