# -*- coding: utf-8 -*-
"""
Stock Location Extension for Chemical OS

Extends stock.location to support tank-specific fields:
- Tank capacity and specifications
- Current product and fill level
- Safety and compliance information
"""

from odoo import models, fields, api, _


class StockLocation(models.Model):
    """
    Extended Stock Location for Chemical OS tank management.
    
    Adds tank-specific fields for capacity tracking, safety compliance,
    and integration with tank content tracking.
    """
    _inherit = 'stock.location'
    
    # Tank Classification
    is_tank = fields.Boolean(
        string='Is Storage Tank',
        compute='_compute_is_tank',
        store=True,
        help='Automatically set based on location barcode containing "Tank".',
    )
    
    tank_type = fields.Selection([
        ('bulk', 'Bulk Storage Tank'),
        ('day', 'Day Tank'),
        ('mixing', 'Mixing Tank'),
        ('holding', 'Holding Tank'),
    ], string='Tank Type', default='bulk')
    
    # Capacity Information
    tank_capacity = fields.Float(
        string='Tank Capacity',
        digits='Product Unit of Measure',
        help='Maximum capacity of the tank in liters.',
    )
    
    tank_capacity_uom = fields.Selection([
        ('L', 'Liters'),
        ('KG', 'Kilograms'),
        ('GAL', 'Gallons'),
        ('M3', 'Cubic Meters'),
    ], string='Capacity UoM', default='L')
    
    # Current Content (computed from tank.content)
    tank_content_id = fields.Many2one(
        'chemical.tank.content',
        string='Tank Content',
        compute='_compute_tank_content',
        help='Current tank content record.',
    )
    
    current_product_id = fields.Many2one(
        'product.product',
        string='Current Product',
        compute='_compute_tank_content',
        help='Product currently in the tank.',
    )
    
    current_quantity = fields.Float(
        string='Current Quantity',
        compute='_compute_tank_content',
        help='Current quantity in the tank.',
    )
    
    current_fill_pct = fields.Float(
        string='Fill %',
        compute='_compute_tank_content',
        help='Current fill level percentage.',
    )
    
    # Tank Status
    tank_state = fields.Selection([
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('cleaning', 'Cleaning'),
        ('maintenance', 'Maintenance'),
        ('offline', 'Offline'),
    ], string='Tank Status', default='available')
    
    # Safety and Compliance
    last_inspection_date = fields.Date(
        string='Last Inspection',
        help='Date of last safety inspection.',
    )
    
    next_inspection_date = fields.Date(
        string='Next Inspection Due',
        help='Date when next inspection is due.',
    )
    
    requires_inerting = fields.Boolean(
        string='Requires Inerting',
        default=False,
        help='Tank requires nitrogen blanket or inerting.',
    )
    
    max_temperature = fields.Float(
        string='Max Temperature (°C)',
        help='Maximum allowable storage temperature.',
    )
    
    # Equipment Links
    pump_ids = fields.Many2many(
        'maintenance.equipment',
        'equipment_location_rel',
        'location_id',
        'equipment_id',
        string='Connected Pumps',
        domain="[('equipment_type', '=', 'pump')]",
        help='Pumps that can draw from this tank.',
    )
    
    pump_count = fields.Integer(
        string='Connected Pumps',
        compute='_compute_pump_count',
    )
    
    @api.depends('barcode')
    def _compute_is_tank(self):
        for record in self:
            record.is_tank = bool(record.barcode and 'Tank' in record.barcode)
    
    def _compute_tank_content(self):
        TankContent = self.env['chemical.tank.content']
        for record in self:
            if record.is_tank:
                content = TankContent.search([
                    ('location_id', '=', record.id)
                ], limit=1)
                record.tank_content_id = content
                record.current_product_id = content.product_id if content else False
                record.current_quantity = content.quantity if content else 0.0
                record.current_fill_pct = content.fill_percentage if content else 0.0
            else:
                record.tank_content_id = False
                record.current_product_id = False
                record.current_quantity = 0.0
                record.current_fill_pct = 0.0
    
    def _compute_pump_count(self):
        for record in self:
            record.pump_count = len(record.pump_ids)
    
    def action_view_tank_content(self):
        """Open tank content form view."""
        self.ensure_one()
        if not self.is_tank:
            return
        
        TankContent = self.env['chemical.tank.content']
        content = TankContent.search([('location_id', '=', self.id)], limit=1)
        
        if content:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Tank Content: %s') % self.name,
                'res_model': 'chemical.tank.content',
                'res_id': content.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Create Tank Content: %s') % self.name,
                'res_model': 'chemical.tank.content',
                'view_mode': 'form',
                'target': 'current',
                'context': {
                    'default_location_id': self.id,
                    'default_tank_capacity': self.tank_capacity,
                },
            }
    
    def action_view_tank_history(self):
        """Open tank history view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tank History: %s') % self.name,
            'res_model': 'chemical.tank.history',
            'view_mode': 'tree,form',
            'domain': [('location_id', '=', self.id)],
            'context': {'search_default_location_id': self.id},
        }
    
    def action_view_connected_pumps(self):
        """Open view of connected pumps."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Connected Pumps: %s') % self.name,
            'res_model': 'maintenance.equipment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.pump_ids.ids)],
        }
