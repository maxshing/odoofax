# -*- coding: utf-8 -*-
"""
Tank History Tracking for Chemical OS

Records all operations on storage tanks:
- Fill operations (incoming product)
- Draw operations (outgoing product)
- Transfers between tanks
- Cleaning and maintenance events
"""

from odoo import models, fields, api, _


class TankHistory(models.Model):
    """
    Tank History - Audit trail for all tank operations.
    
    Records every fill, draw, transfer, and maintenance operation
    with before/after quantities for complete traceability.
    """
    _name = 'chemical.tank.history'
    _description = 'Tank Operation History'
    _order = 'operation_date desc, id desc'
    _rec_name = 'display_name'
    
    # Tank Content Reference
    tank_content_id = fields.Many2one(
        'chemical.tank.content',
        string='Tank Content',
        required=True,
        ondelete='cascade',
    )
    
    # Denormalized for easier reporting
    location_id = fields.Many2one(
        'stock.location',
        string='Tank Location',
        related='tank_content_id.location_id',
        store=True,
        readonly=True,
    )
    
    # Operation Details
    operation_type = fields.Selection([
        ('fill', 'Fill (入料)'),
        ('draw', 'Draw (出料)'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('adjustment', 'Inventory Adjustment'),
        ('sample', 'Sample Taken'),
        ('cleaning', 'Cleaning'),
        ('maintenance', 'Maintenance'),
    ], string='Operation Type', required=True)
    
    operation_date = fields.Datetime(
        string='Operation Date',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    
    # Quantity Tracking
    quantity = fields.Float(
        string='Quantity',
        digits='Product Unit of Measure',
        help='Amount involved in the operation.',
    )
    
    quantity_before = fields.Float(
        string='Quantity Before',
        digits='Product Unit of Measure',
        help='Tank quantity before the operation.',
    )
    
    quantity_after = fields.Float(
        string='Quantity After',
        digits='Product Unit of Measure',
        help='Tank quantity after the operation.',
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='tank_content_id.uom_id',
        readonly=True,
    )
    
    # Product and Lot
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='tank_content_id.product_id',
        store=True,
        readonly=True,
    )
    
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot/Batch',
        help='Lot/batch number involved in this operation.',
    )
    
    # Source/Destination for transfers
    source_location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        help='Source location for transfer operations.',
    )
    
    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        help='Destination location for transfer operations.',
    )
    
    # Stock Move Reference
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        help='Related Odoo stock move (if any).',
    )
    
    # User and Notes
    user_id = fields.Many2one(
        'res.users',
        string='Operator',
        default=lambda self: self.env.user,
        required=True,
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about the operation.',
    )
    
    # Computed Display Name
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    
    # Reference number for the operation
    reference = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
    )
    
    @api.depends('location_id', 'operation_type', 'operation_date', 'quantity')
    def _compute_display_name(self):
        operation_labels = {
            'fill': '入料',
            'draw': '出料',
            'transfer_in': '轉入',
            'transfer_out': '轉出',
            'adjustment': '調整',
            'sample': '取樣',
            'cleaning': '清槽',
            'maintenance': '維護',
        }
        for record in self:
            op_label = operation_labels.get(record.operation_type, record.operation_type)
            date_str = record.operation_date.strftime('%Y-%m-%d %H:%M') if record.operation_date else ''
            record.display_name = f"{record.location_id.name} - {op_label} {record.quantity:.0f} @ {date_str}"
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate reference number on creation."""
        for vals in vals_list:
            if not vals.get('reference'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('chemical.tank.history') or 'TH/'
        return super().create(vals_list)
    
    def get_operation_summary(self):
        """Get a human-readable summary of the operation."""
        self.ensure_one()
        
        summaries = {
            'fill': _('Filled %s with %.2f %s') % (
                self.location_id.name, 
                self.quantity, 
                self.uom_id.name or 'units'
            ),
            'draw': _('Drew %.2f %s from %s') % (
                self.quantity,
                self.uom_id.name or 'units',
                self.location_id.name
            ),
            'transfer_in': _('Transferred %.2f %s into %s from %s') % (
                self.quantity,
                self.uom_id.name or 'units',
                self.location_id.name,
                self.source_location_id.name if self.source_location_id else 'unknown'
            ),
            'transfer_out': _('Transferred %.2f %s from %s to %s') % (
                self.quantity,
                self.uom_id.name or 'units',
                self.location_id.name,
                self.dest_location_id.name if self.dest_location_id else 'unknown'
            ),
            'adjustment': _('Adjusted %s quantity by %.2f %s') % (
                self.location_id.name,
                self.quantity,
                self.uom_id.name or 'units'
            ),
            'sample': _('Sample taken from %s (%.2f %s)') % (
                self.location_id.name,
                self.quantity,
                self.uom_id.name or 'units'
            ),
            'cleaning': _('Cleaning operation on %s') % self.location_id.name,
            'maintenance': _('Maintenance operation on %s') % self.location_id.name,
        }
        
        return summaries.get(self.operation_type, _('Unknown operation'))
