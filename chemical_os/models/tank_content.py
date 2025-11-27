# -*- coding: utf-8 -*-
"""
Tank Content Tracking for Chemical OS

Tracks the current contents of each storage tank location:
- Current product and lot/batch
- Quantity and capacity utilization
- Quality status and sampling dates
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TankContent(models.Model):
    """
    Tank Content - Tracks what is currently stored in each tank.
    
    Links storage tank locations to products and lot/batch numbers,
    enabling precise inventory tracking at the tank level.
    """
    _name = 'chemical.tank.content'
    _description = 'Tank Content Tracking'
    _rec_name = 'display_name'
    _order = 'location_id, product_id'
    
    # Tank Location Reference
    location_id = fields.Many2one(
        'stock.location',
        string='Tank Location',
        required=True,
        ondelete='cascade',
        domain="[('usage', '=', 'internal'), ('barcode', 'like', 'Tank')]",
        help='The storage tank location.',
    )
    
    # Product Information
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain="[('type', '=', 'product')]",
        help='The product currently stored in this tank.',
    )
    
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot/Batch',
        domain="[('product_id', '=', product_id)]",
        help='The lot or batch number of the product.',
    )
    
    # Quantity Tracking
    quantity = fields.Float(
        string='Current Quantity',
        digits='Product Unit of Measure',
        default=0.0,
        help='Current quantity in the tank (in product UoM).',
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        readonly=True,
    )
    
    # Capacity Information
    tank_capacity = fields.Float(
        string='Tank Capacity',
        digits='Product Unit of Measure',
        help='Maximum capacity of the tank (in liters or kg).',
    )
    
    fill_percentage = fields.Float(
        string='Fill %',
        compute='_compute_fill_percentage',
        store=True,
        help='Current fill level as percentage of capacity.',
    )
    
    # Status and Quality
    state = fields.Selection([
        ('empty', 'Empty'),
        ('partial', 'Partial'),
        ('full', 'Full'),
        ('cleaning', 'Cleaning'),
        ('maintenance', 'Maintenance'),
    ], string='Status', default='empty', required=True)
    
    quality_status = fields.Selection([
        ('pending', 'Pending QC'),
        ('approved', 'Approved'),
        ('quarantine', 'Quarantine'),
        ('rejected', 'Rejected'),
    ], string='Quality Status', default='pending')
    
    # Dates
    last_fill_date = fields.Datetime(
        string='Last Fill Date',
        help='Date when the tank was last filled.',
    )
    
    last_sample_date = fields.Date(
        string='Last Sample Date',
        help='Date when the last quality sample was taken.',
    )
    
    next_sample_date = fields.Date(
        string='Next Sample Due',
        help='Date when the next quality sample is due.',
    )
    
    # Computed Display Name
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional notes about tank contents.',
    )
    
    # History Relationship
    history_ids = fields.One2many(
        'chemical.tank.history',
        'tank_content_id',
        string='History',
    )
    
    history_count = fields.Integer(
        string='History Count',
        compute='_compute_history_count',
    )
    
    @api.depends('location_id', 'product_id', 'quantity')
    def _compute_display_name(self):
        for record in self:
            if record.location_id and record.product_id:
                record.display_name = f"{record.location_id.name}: {record.product_id.name} ({record.quantity:.0f})"
            elif record.location_id:
                record.display_name = f"{record.location_id.name}: Empty"
            else:
                record.display_name = "New Tank Content"
    
    @api.depends('quantity', 'tank_capacity')
    def _compute_fill_percentage(self):
        for record in self:
            if record.tank_capacity > 0:
                record.fill_percentage = (record.quantity / record.tank_capacity) * 100
            else:
                record.fill_percentage = 0.0
    
    def _compute_history_count(self):
        for record in self:
            record.history_count = len(record.history_ids)
    
    @api.constrains('quantity', 'tank_capacity')
    def _check_quantity(self):
        for record in self:
            if record.quantity < 0:
                raise ValidationError(_('Quantity cannot be negative.'))
            if record.tank_capacity > 0 and record.quantity > record.tank_capacity:
                raise ValidationError(_('Quantity cannot exceed tank capacity.'))
    
    @api.onchange('quantity', 'tank_capacity')
    def _onchange_quantity(self):
        """Auto-update state based on fill level."""
        if self.quantity <= 0:
            self.state = 'empty'
        elif self.tank_capacity > 0 and self.quantity >= self.tank_capacity * 0.95:
            self.state = 'full'
        else:
            self.state = 'partial'
    
    def action_record_fill(self, quantity, lot_id=False, notes=False):
        """
        Record a fill operation - adding product to the tank.
        
        Args:
            quantity: Amount being added
            lot_id: Optional lot/batch ID
            notes: Optional operation notes
        """
        self.ensure_one()
        
        old_quantity = self.quantity
        new_quantity = old_quantity + quantity
        
        # Create history record
        self.env['chemical.tank.history'].create({
            'tank_content_id': self.id,
            'operation_type': 'fill',
            'quantity': quantity,
            'quantity_before': old_quantity,
            'quantity_after': new_quantity,
            'lot_id': lot_id or self.lot_id.id,
            'notes': notes,
        })
        
        # Update tank content
        vals = {
            'quantity': new_quantity,
            'last_fill_date': fields.Datetime.now(),
        }
        if lot_id:
            vals['lot_id'] = lot_id
        
        self.write(vals)
        self._onchange_quantity()
        
        return True
    
    def action_record_draw(self, quantity, notes=False):
        """
        Record a draw operation - removing product from the tank.
        
        Args:
            quantity: Amount being removed
            notes: Optional operation notes
        """
        self.ensure_one()
        
        if quantity > self.quantity:
            raise ValidationError(_('Cannot draw more than current quantity.'))
        
        old_quantity = self.quantity
        new_quantity = old_quantity - quantity
        
        # Create history record
        self.env['chemical.tank.history'].create({
            'tank_content_id': self.id,
            'operation_type': 'draw',
            'quantity': quantity,
            'quantity_before': old_quantity,
            'quantity_after': new_quantity,
            'lot_id': self.lot_id.id,
            'notes': notes,
        })
        
        # Update tank content
        self.write({'quantity': new_quantity})
        self._onchange_quantity()
        
        return True
    
    def action_record_transfer(self, target_tank_id, quantity, notes=False):
        """
        Record a transfer operation between tanks.
        
        Args:
            target_tank_id: Destination tank content ID
            quantity: Amount being transferred
            notes: Optional operation notes
        """
        self.ensure_one()
        target = self.browse(target_tank_id)
        
        if quantity > self.quantity:
            raise ValidationError(_('Cannot transfer more than current quantity.'))
        
        # Record draw from source
        self.action_record_draw(quantity, notes=f"Transfer to {target.location_id.name}: {notes or ''}")
        
        # Record fill to target
        target.action_record_fill(
            quantity, 
            lot_id=self.lot_id.id,
            notes=f"Transfer from {self.location_id.name}: {notes or ''}"
        )
        
        return True
    
    def action_view_history(self):
        """Open history view for this tank."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tank History: %s') % self.location_id.name,
            'res_model': 'chemical.tank.history',
            'view_mode': 'tree,form',
            'domain': [('tank_content_id', '=', self.id)],
            'context': {'default_tank_content_id': self.id},
        }
    
    def action_start_cleaning(self):
        """Mark tank as under cleaning."""
        self.ensure_one()
        if self.quantity > 0:
            raise ValidationError(_('Tank must be empty before cleaning.'))
        self.write({'state': 'cleaning'})
        
        # Record in history
        self.env['chemical.tank.history'].create({
            'tank_content_id': self.id,
            'operation_type': 'cleaning',
            'quantity': 0,
            'quantity_before': 0,
            'quantity_after': 0,
            'notes': 'Tank cleaning started.',
        })
    
    def action_complete_cleaning(self):
        """Mark cleaning as complete, tank ready for use."""
        self.ensure_one()
        self.write({
            'state': 'empty',
            'product_id': False,
            'lot_id': False,
        })
        
        # Record in history
        self.env['chemical.tank.history'].create({
            'tank_content_id': self.id,
            'operation_type': 'cleaning',
            'quantity': 0,
            'quantity_before': 0,
            'quantity_after': 0,
            'notes': 'Tank cleaning completed. Ready for new product.',
        })
