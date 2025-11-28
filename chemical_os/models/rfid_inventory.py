# -*- coding: utf-8 -*-
"""
Inventory & Production Tracking - RFID Tag System for Chemical OS

Implements RFID-based inventory tracking for drums and containers.

Hardware Integration:
- RFID Writers at Filling Machines (f1, f2, f3): Encode new drum tags
- RFID Portals at Loading Road (P3): Automatic inventory movement
- RFID Handhelds: Manual scanning for verification

Features:
- Automatic lot creation with RFID encoding
- Portal-based automatic stock transfers
- Full traceability from production to delivery
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import hashlib
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ChemicalRfidTag(models.Model):
    """
    RFID Tag registry for drums and containers.
    
    Each tag is uniquely encoded with product, lot, and expiry information.
    """
    _name = 'chemical.rfid.tag'
    _description = 'RFID Tag Registry'
    _order = 'create_date desc'
    _rec_name = 'tag_id'
    
    tag_id = fields.Char(
        string='Tag ID',
        required=True,
        index=True,
        readonly=True,
        help='Unique RFID tag identifier burned into the drum.',
    )
    
    tag_data = fields.Char(
        string='Encoded Data',
        readonly=True,
        help='Full data encoded on the tag (Product_Lot_Expiry).',
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        index=True,
    )
    
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot/Serial Number',
        required=True,
        index=True,
    )
    
    production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        help='MO that produced this drum.',
    )
    
    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Filling Machine',
        help='Machine that filled this drum (f1, f2, f3).',
    )
    
    container_spec_id = fields.Many2one(
        'chemical.container.spec',
        string='Container Type',
        help='Container specification (200L drum, IBC, etc.).',
    )
    
    fill_date = fields.Datetime(
        string='Fill Date',
        default=fields.Datetime.now,
    )
    
    expiry_date = fields.Date(
        string='Expiry Date',
    )
    
    quantity = fields.Float(
        string='Quantity',
        help='Amount filled in this container.',
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        related='product_id.uom_id',
    )
    
    current_location_id = fields.Many2one(
        'stock.location',
        string='Current Location',
        help='Last known location of this drum.',
    )
    
    state = fields.Selection([
        ('encoded', 'Newly Encoded'),
        ('in_stock', 'In Stock'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('returned', 'Returned'),
        ('scrapped', 'Scrapped'),
    ], string='Status', default='encoded', index=True)
    
    scan_history_ids = fields.One2many(
        'chemical.rfid.scan',
        'tag_id',
        string='Scan History',
    )
    
    scan_count = fields.Integer(
        string='Scan Count',
        compute='_compute_scan_count',
    )
    
    def _compute_scan_count(self):
        for record in self:
            record.scan_count = len(record.scan_history_ids)
    
    @api.model
    def encode_drum_tag(self, production_id, workcenter_code=None, quantity=None, container_spec_id=None):
        """
        Encode a new RFID tag for a filled drum.
        
        Called by filling machine (f1/f2/f3) when drum filling is complete.
        
        Args:
            production_id: int - Manufacturing order ID
            workcenter_code: str - Filling machine code (f1, f2, f3)
            quantity: float - Filled quantity
            container_spec_id: int - Container specification ID
        
        Returns:
            dict: Encoding result with tag data for RFID writer
        
        Workflow:
        1. Get production order details
        2. Generate unique tag ID
        3. Create stock.lot record
        4. Encode tag data string
        5. Register tag in system
        6. Return data for RFID writer
        """
        Production = self.env['mrp.production']
        production = Production.browse(production_id)
        
        if not production.exists():
            return {
                'status': 'error',
                'message': f'Manufacturing order not found: {production_id}',
            }
        
        product = production.product_id
        
        expiry_date = None
        if product.use_expiration_date:
            shelf_life_days = product.expiration_time or 365
            expiry_date = fields.Date.today() + timedelta(days=shelf_life_days)
        
        Lot = self.env['stock.lot']
        lot_name = self._generate_lot_name(production)
        
        existing_lot = Lot.search([
            ('name', '=', lot_name),
            ('product_id', '=', product.id),
        ], limit=1)
        
        if existing_lot:
            lot = existing_lot
        else:
            lot_vals = {
                'name': lot_name,
                'product_id': product.id,
                'company_id': production.company_id.id,
            }
            if expiry_date:
                lot_vals['expiration_date'] = expiry_date
            lot = Lot.create(lot_vals)
        
        tag_id = self._generate_tag_id(product.id, lot.id)
        
        tag_data = self._encode_tag_data(product, lot, expiry_date)
        
        Workcenter = self.env['mrp.workcenter']
        workcenter = None
        if workcenter_code:
            workcenter = Workcenter.search([
                '|',
                ('code', '=', workcenter_code.upper()),
                ('code', 'ilike', workcenter_code),
            ], limit=1)
        
        tag_vals = {
            'tag_id': tag_id,
            'tag_data': tag_data,
            'product_id': product.id,
            'lot_id': lot.id,
            'production_id': production.id,
            'workcenter_id': workcenter.id if workcenter else False,
            'container_spec_id': container_spec_id,
            'fill_date': fields.Datetime.now(),
            'expiry_date': expiry_date,
            'quantity': quantity or production.product_qty,
            'current_location_id': workcenter.location_id.id if workcenter and hasattr(workcenter, 'location_id') else False,
            'state': 'encoded',
        }
        
        rfid_tag = self.create(tag_vals)
        
        _logger.info(
            'RFID Tag Encoded: %s for product %s, lot %s, MO %s',
            tag_id, product.name, lot.name, production.name
        )
        
        return {
            'status': 'success',
            'signal': 'WRITE_TAG',
            'tag_id': tag_id,
            'tag_data': tag_data,
            'rfid_record_id': rfid_tag.id,
            'lot_id': lot.id,
            'lot_name': lot.name,
            'product': product.name,
            'product_code': product.default_code or '',
            'expiry_date': expiry_date.isoformat() if expiry_date else None,
            'quantity': quantity or production.product_qty,
        }
    
    def _generate_lot_name(self, production):
        """Generate lot name from production order."""
        date_str = fields.Date.today().strftime('%y%m%d')
        seq = self.env['ir.sequence'].next_by_code('chemical.lot.sequence') or '001'
        return f"{production.product_id.default_code or 'PRD'}-{date_str}-{seq}"
    
    def _generate_tag_id(self, product_id, lot_id):
        """Generate unique RFID tag ID."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        raw_id = f"{product_id}-{lot_id}-{timestamp}"
        hash_suffix = hashlib.md5(raw_id.encode()).hexdigest()[:8].upper()
        return f"RFID-{hash_suffix}"
    
    def _encode_tag_data(self, product, lot, expiry_date):
        """
        Encode data string for RFID tag.
        
        Format: PRODUCT_ID|LOT_NO|EXPIRY_DATE
        """
        product_code = product.default_code or str(product.id)
        lot_no = lot.name
        exp_str = expiry_date.strftime('%Y%m%d') if expiry_date else '99991231'
        
        return f"{product_code}|{lot_no}|{exp_str}"


class ChemicalRfidScan(models.Model):
    """
    RFID Scan history for tracking drum movements.
    """
    _name = 'chemical.rfid.scan'
    _description = 'RFID Scan Event'
    _order = 'timestamp desc'
    
    tag_id = fields.Many2one(
        'chemical.rfid.tag',
        string='RFID Tag',
        required=True,
        index=True,
        ondelete='cascade',
    )
    
    reader_location = fields.Char(
        string='Reader Location',
        required=True,
        help='Physical location of RFID reader.',
    )
    
    reader_type = fields.Selection([
        ('portal', 'Portal Reader'),
        ('handheld', 'Handheld Scanner'),
        ('fixed', 'Fixed Reader'),
    ], string='Reader Type', default='portal')
    
    timestamp = fields.Datetime(
        string='Scan Time',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    
    from_location_id = fields.Many2one(
        'stock.location',
        string='From Location',
    )
    
    to_location_id = fields.Many2one(
        'stock.location',
        string='To Location',
    )
    
    picking_id = fields.Many2one(
        'stock.picking',
        string='Generated Transfer',
        help='Stock picking automatically created from this scan.',
    )
    
    result = fields.Selection([
        ('success', 'Transfer Created'),
        ('matched', 'Matched to Existing Transfer'),
        ('error', 'Error'),
        ('info', 'Information Only'),
    ], string='Result', default='info')
    
    notes = fields.Text(
        string='Notes',
    )
    
    @api.model
    def process_rfid_scan(self, tag_id, reader_location, reader_type='portal'):
        """
        Process an RFID scan event.
        
        Called by RFID portal/reader when a tag is scanned.
        
        Args:
            tag_id: str - RFID tag ID
            reader_location: str - Reader location code (e.g., 'P3', 'X-DOCK')
            reader_type: str - Type of reader ('portal', 'handheld', 'fixed')
        
        Returns:
            dict: Processing result
        
        Workflow:
        1. Find the RFID tag record
        2. Determine source and destination locations
        3. Check for pending delivery orders
        4. Create/validate internal transfer
        5. Update tag location
        """
        RfidTag = self.env['chemical.rfid.tag']
        tag = RfidTag.search([
            ('tag_id', '=', tag_id),
        ], limit=1)
        
        if not tag:
            _logger.warning('RFID Scan: Unknown tag %s at %s', tag_id, reader_location)
            return {
                'status': 'error',
                'message': f'Unknown RFID tag: {tag_id}',
            }
        
        Location = self.env['stock.location']
        to_location = Location.search([
            '|',
            ('barcode', '=', reader_location),
            ('barcode', 'ilike', reader_location),
        ], limit=1)
        
        if not to_location:
            to_location = Location.search([
                ('name', 'ilike', reader_location),
            ], limit=1)
        
        if not to_location:
            _logger.error('RFID Scan: Unknown location %s', reader_location)
            return {
                'status': 'error',
                'message': f'Unknown reader location: {reader_location}',
            }
        
        from_location = tag.current_location_id
        
        scan_vals = {
            'tag_id': tag.id,
            'reader_location': reader_location,
            'reader_type': reader_type,
            'timestamp': fields.Datetime.now(),
            'from_location_id': from_location.id if from_location else False,
            'to_location_id': to_location.id,
        }
        
        Picking = self.env['stock.picking']
        pending_delivery = Picking.search([
            ('state', 'in', ['assigned', 'waiting', 'confirmed']),
            ('picking_type_code', '=', 'outgoing'),
            ('move_ids.product_id', '=', tag.product_id.id),
        ], limit=1)
        
        if pending_delivery:
            matched_move = pending_delivery.move_ids.filtered(
                lambda m: m.product_id.id == tag.product_id.id and m.state not in ('done', 'cancel')
            )
            
            if matched_move:
                scan_vals['picking_id'] = pending_delivery.id
                scan_vals['result'] = 'matched'
                scan_vals['notes'] = f'Matched to delivery {pending_delivery.name}'
                
                tag.write({
                    'current_location_id': to_location.id,
                    'state': 'in_transit',
                })
                
                scan = self.create(scan_vals)
                
                _logger.info(
                    'RFID Scan: Tag %s matched to delivery %s at %s',
                    tag_id, pending_delivery.name, reader_location
                )
                
                return {
                    'status': 'matched',
                    'tag_id': tag_id,
                    'product': tag.product_id.name,
                    'lot': tag.lot_id.name,
                    'delivery': pending_delivery.name,
                    'destination': pending_delivery.partner_id.name if pending_delivery.partner_id else 'N/A',
                    'scan_id': scan.id,
                }
        
        if from_location and from_location.id != to_location.id:
            transfer_result = self._create_internal_transfer(tag, from_location, to_location)
            
            if transfer_result.get('picking_id'):
                scan_vals['picking_id'] = transfer_result['picking_id']
                scan_vals['result'] = 'success'
                scan_vals['notes'] = f'Created transfer {transfer_result.get("picking_name")}'
            else:
                scan_vals['result'] = 'error'
                scan_vals['notes'] = transfer_result.get('message')
        else:
            scan_vals['result'] = 'info'
            scan_vals['notes'] = 'Location unchanged or first scan'
        
        tag.write({
            'current_location_id': to_location.id,
            'state': 'in_stock' if to_location.usage == 'internal' else 'in_transit',
        })
        
        scan = self.create(scan_vals)
        
        _logger.info(
            'RFID Scan: Tag %s at %s, result: %s',
            tag_id, reader_location, scan_vals['result']
        )
        
        return {
            'status': 'success',
            'tag_id': tag_id,
            'product': tag.product_id.name,
            'lot': tag.lot_id.name,
            'from_location': from_location.name if from_location else 'N/A',
            'to_location': to_location.name,
            'scan_id': scan.id,
            'result': scan_vals['result'],
            'transfer': scan_vals.get('notes'),
        }
    
    def _create_internal_transfer(self, tag, from_location, to_location):
        """
        Create an internal transfer for the scanned drum.
        """
        Picking = self.env['stock.picking']
        PickingType = self.env['stock.picking.type']
        
        picking_type = PickingType.search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.env.company.id),
        ], limit=1)
        
        if not picking_type:
            return {
                'status': 'error',
                'message': 'No internal transfer type found',
            }
        
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': from_location.id,
            'location_dest_id': to_location.id,
            'origin': f'RFID Scan: {tag.tag_id}',
            'move_ids': [(0, 0, {
                'name': f'RFID Transfer: {tag.product_id.name}',
                'product_id': tag.product_id.id,
                'product_uom_qty': tag.quantity,
                'product_uom': tag.uom_id.id,
                'location_id': from_location.id,
                'location_dest_id': to_location.id,
            })],
        }
        
        try:
            picking = Picking.create(picking_vals)
            picking.action_confirm()
            picking.action_assign()
            
            for move in picking.move_ids:
                for move_line in move.move_line_ids:
                    move_line.lot_id = tag.lot_id.id
                    move_line.quantity = tag.quantity
            
            picking.button_validate()
            
            return {
                'status': 'success',
                'picking_id': picking.id,
                'picking_name': picking.name,
            }
            
        except Exception as e:
            _logger.error('RFID Transfer creation failed: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
