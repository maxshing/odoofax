# -*- coding: utf-8 -*-
"""
Container Specification Model
=============================

Replaces Legacy Codes 9172/9175 for container specifications.

Legacy Issue:
    The old system used single character codes (P=Plastic) which couldn't 
    distinguish between HDPE vs PP, or Open Top vs Closed Top drums.

Solution:
    This model provides structured container specifications with clear
    material types, lid configurations, and volume specifications.

Example Legacy Codes:
    9172 = Steel Drum
    9175 = Plastic Container
    P = Plastic (ambiguous - could be HDPE or PP)
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ChemicalContainerSpec(models.Model):
    _name = 'chemical.container.spec'
    _description = 'Container Specification'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'material, volume_type, lid_type'

    name = fields.Char(
        string='Specification Name',
        compute='_compute_name',
        store=True,
        readonly=False,
    )
    
    code = fields.Char(
        string='Specification Code',
        required=True,
        copy=False,
        help='Unique code for this container specification (e.g., HDPE-200L-C)',
    )
    
    # Material Type - Replaces ambiguous "P" code
    material = fields.Selection(
        selection=[
            ('steel', 'Steel (鋼製)'),
            ('hdpe', 'HDPE Plastic (HDPE塑膠)'),
            ('pp', 'PP Plastic (PP塑膠)'),
            ('sus', 'Stainless Steel (不鏽鋼)'),
            ('fiber', 'Fiberglass (玻璃纖維)'),
        ],
        string='Material',
        required=True,
        tracking=True,
        help='Container material type. Replaces legacy single-character codes.',
    )
    
    # Lid Type - Distinguishes Open vs Closed Top
    lid_type = fields.Selection(
        selection=[
            ('closed', 'Closed Top / Liquid (閉口桶/液體用)'),
            ('open', 'Open Top / Removable (開口桶/固體用)'),
        ],
        string='Lid Type',
        required=True,
        tracking=True,
        help='Closed top for liquids, Open top for pastes/solids.',
    )
    
    # Volume Type
    volume_type = fields.Selection(
        selection=[
            ('200l', '200L Drum (200公升桶)'),
            ('18l', '18L Pail / 5 Gallon (18公升/5加侖桶)'),
            ('1000l', '1000L IBC (1000公升IBC桶)'),
            ('25l', '25L Jerry Can (25公升油桶)'),
            ('bulk', 'Bulk / Tanker (散裝/槽車)'),
        ],
        string='Volume Type',
        required=True,
        tracking=True,
    )
    
    # Additional specifications
    volume_liters = fields.Float(
        string='Volume (Liters)',
        compute='_compute_volume_liters',
        store=True,
    )
    
    tare_weight = fields.Float(
        string='Tare Weight (kg)',
        help='Empty container weight in kilograms.',
    )
    
    is_returnable = fields.Boolean(
        string='Returnable',
        default=True,
        help='Whether this container type can be returned for credit.',
    )
    
    deposit_amount = fields.Float(
        string='Deposit Amount (TWD)',
        help='押桶金額 - Deposit required when lending this container.',
    )
    
    buyback_price = fields.Float(
        string='Buyback Price (TWD)',
        help='購回價格 - Price paid when buying back container from customer.',
    )
    
    # Legacy reference
    legacy_codes = fields.Char(
        string='Legacy Codes',
        help='Reference to original legacy codes (e.g., 9172, 9175, P, S).',
    )
    
    active = fields.Boolean(default=True)
    
    notes = fields.Text(string='Notes')
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Container specification code must be unique!'),
    ]
    
    @api.depends('material', 'volume_type', 'lid_type')
    def _compute_name(self):
        """Generate human-readable name from specifications."""
        material_names = {
            'steel': '鋼製',
            'hdpe': 'HDPE',
            'pp': 'PP',
            'sus': '不鏽鋼',
            'fiber': '玻璃纖維',
        }
        volume_names = {
            '200l': '200L',
            '18l': '18L',
            '1000l': '1000L IBC',
            '25l': '25L',
            'bulk': '散裝',
        }
        lid_names = {
            'closed': '閉口',
            'open': '開口',
        }
        for rec in self:
            if rec.material and rec.volume_type and rec.lid_type:
                rec.name = f"{material_names.get(rec.material, '')} {volume_names.get(rec.volume_type, '')} {lid_names.get(rec.lid_type, '')}桶"
            else:
                rec.name = rec.code or 'New Specification'
    
    @api.depends('volume_type')
    def _compute_volume_liters(self):
        """Convert volume type to numeric value."""
        volume_map = {
            '200l': 200.0,
            '18l': 18.0,
            '1000l': 1000.0,
            '25l': 25.0,
            'bulk': 0.0,
        }
        for rec in self:
            rec.volume_liters = volume_map.get(rec.volume_type, 0.0)
    
    @api.model
    def get_spec_for_legacy_code(self, legacy_code):
        """
        Find container specification matching a legacy code.
        
        Replaces manual lookup in legacy system.
        
        Args:
            legacy_code: Original system code (e.g., '9172', 'P')
            
        Returns:
            Container spec record or False
        """
        return self.search([
            ('legacy_codes', 'ilike', legacy_code)
        ], limit=1) or False
