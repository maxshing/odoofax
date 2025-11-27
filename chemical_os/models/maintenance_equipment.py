# -*- coding: utf-8 -*-
"""
Maintenance Equipment Extension for Chemical OS

Extends the maintenance.equipment model to support:
- Many2many relationship to stock.location (source tanks)
- Pump-to-tank linkage for flow equipment tracking
"""

from odoo import models, fields, api


class MaintenanceEquipment(models.Model):
    """
    Extended Maintenance Equipment for Chemical OS.
    
    Adds location_ids field to link pumps to their source tanks,
    enabling precise tracking of which tanks each pump can serve.
    """
    _inherit = 'maintenance.equipment'
    
    # Many2many field linking equipment to source tank locations
    location_ids = fields.Many2many(
        'stock.location',
        'equipment_location_rel',
        'equipment_id',
        'location_id',
        string='Source Tanks',
        help='Tank locations that this equipment (pump) can draw from.',
        domain="[('usage', '=', 'internal'), ('barcode', 'like', 'Tank')]",
    )
    
    # Equipment type classification
    equipment_type = fields.Selection([
        ('pump', 'Pump'),
        ('filler', 'Filling Machine'),
        ('mixer', 'Mixing Tank'),
        ('other', 'Other'),
    ], string='Equipment Type', default='other',
       help='Classification of equipment for Chemical OS operations.')
    
    # Cross-building asset flag
    is_cross_building = fields.Boolean(
        string='Cross-Building Asset',
        default=False,
        help='Indicates this equipment serves multiple buildings (critical asset).',
    )
    
    # Metered equipment flag (has Mass Flow Meter)
    is_metered = fields.Boolean(
        string='Is Metered',
        default=False,
        help='Indicates this equipment has a Mass Flow Meter (MFM) installed for precise flow measurement.',
    )
    
    # IoT Point link
    iot_point_ids = fields.One2many(
        'chemical.iot.point',
        'pump_id',
        string='IoT Points',
        help='IoT measurement points attached to this equipment.',
    )
    
    iot_point_count = fields.Integer(
        string='IoT Points',
        compute='_compute_iot_point_count',
    )
    
    # Tank count (computed)
    tank_count = fields.Integer(
        string='Linked Tanks',
        compute='_compute_tank_count',
        store=True,
    )
    
    @api.depends('location_ids')
    def _compute_tank_count(self):
        """Compute the number of linked tank locations."""
        for record in self:
            record.tank_count = len(record.location_ids)
    
    def _compute_iot_point_count(self):
        """Compute the number of IoT points."""
        for record in self:
            record.iot_point_count = len(record.iot_point_ids)
    
    def action_view_iot_points(self):
        """Open a view showing all IoT points for this equipment."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'IoT Points',
            'res_model': 'chemical.iot.point',
            'view_mode': 'tree,form',
            'domain': [('pump_id', '=', self.id)],
            'context': {'default_pump_id': self.id},
        }
    
    def action_view_linked_tanks(self):
        """Open a view showing all linked tank locations."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Linked Tanks',
            'res_model': 'stock.location',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.location_ids.ids)],
            'context': {'create': False},
        }
