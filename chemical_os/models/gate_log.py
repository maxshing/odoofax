# -*- coding: utf-8 -*-
"""
Vehicle Access Control - LPR Integration for Chemical OS

Implements automated gate control using License Plate Recognition (LPR) cameras.
Cameras are installed at:
- P1 (Main Plaza) - Main entry/exit gate
- P3 (Loading Road) - Tanker loading area gate

Features:
- Automatic plate matching against expected shipments
- Auto-gate opening for scheduled vehicles
- Security alerts for unscheduled vehicles
- Complete audit trail of all gate events
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ChemicalGateLog(models.Model):
    """
    Gate Log for tracking vehicle entry/exit events.
    
    Each record represents a single gate event captured by LPR camera.
    Links to stock.picking for automated shipment tracking.
    """
    _name = 'chemical.gate.log'
    _description = 'Gate Access Log (LPR)'
    _order = 'timestamp desc'
    _rec_name = 'display_name'
    
    plate_number = fields.Char(
        string='License Plate',
        required=True,
        index=True,
        help='Vehicle license plate number captured by LPR camera.',
    )
    
    gate_location_id = fields.Many2one(
        'stock.location',
        string='Gate Location',
        required=True,
        domain="[('usage', '=', 'transit')]",
        help='Physical gate location (P1 Main Plaza, P3 Loading Road).',
    )
    
    gate_code = fields.Char(
        string='Gate Code',
        related='gate_location_id.barcode',
        store=True,
    )
    
    timestamp = fields.Datetime(
        string='Event Time',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    
    action = fields.Selection([
        ('entry', 'Entry'),
        ('exit', 'Exit'),
    ], string='Action', required=True, default='entry')
    
    linked_picking_id = fields.Many2one(
        'stock.picking',
        string='Linked Shipment',
        help='Stock picking (delivery/receipt) associated with this vehicle.',
    )
    
    linked_partner_id = fields.Many2one(
        'res.partner',
        string='Carrier/Customer',
        related='linked_picking_id.partner_id',
        store=True,
    )
    
    status = fields.Selection([
        ('matched', 'Matched - Gate Opened'),
        ('unmatched', 'No Match - Security Alert'),
        ('manual', 'Manual Override'),
        ('denied', 'Access Denied'),
    ], string='Status', default='unmatched')
    
    alert_sent = fields.Boolean(
        string='Alert Sent',
        default=False,
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes or security officer comments.',
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    
    @api.depends('plate_number', 'action', 'timestamp')
    def _compute_display_name(self):
        for record in self:
            action_str = dict(self._fields['action'].selection).get(record.action, '')
            time_str = record.timestamp.strftime('%Y-%m-%d %H:%M') if record.timestamp else ''
            record.display_name = f"{record.plate_number} - {action_str} @ {time_str}"
    
    @api.model
    def process_lpr_event(self, plate_number, gate_code, action='entry'):
        """
        Process an LPR camera event.
        
        Called by the LPR camera API when a license plate is detected.
        
        Args:
            plate_number: str - Detected license plate number
            gate_code: str - Gate location code (e.g., 'P1', 'P3')
            action: str - 'entry' or 'exit'
        
        Returns:
            dict: Processing result with gate control signal
        
        Workflow:
        1. Search for pending stock.picking with matching plate
        2. If match found: Open gate, log entry, notify warehouse
        3. If no match: Create security alert
        """
        plate_number = plate_number.upper().replace(' ', '').replace('-', '')
        
        Location = self.env['stock.location']
        gate_location = Location.search([
            '|',
            ('barcode', '=', gate_code),
            ('barcode', 'ilike', gate_code),
        ], limit=1)
        
        if not gate_location:
            _logger.error('Gate location not found: %s', gate_code)
            return {
                'status': 'error',
                'signal': 'DENY',
                'message': f'Unknown gate location: {gate_code}',
            }
        
        Picking = self.env['stock.picking']
        today = fields.Date.today()
        date_range_start = today - timedelta(days=1)
        date_range_end = today + timedelta(days=1)
        
        pending_pickings = Picking.search([
            ('state', 'in', ['assigned', 'waiting', 'confirmed']),
            ('scheduled_date', '>=', date_range_start),
            ('scheduled_date', '<=', date_range_end),
        ])
        
        matched_picking = None
        for picking in pending_pickings:
            carrier_plate = self._extract_plate_from_picking(picking)
            if carrier_plate and self._normalize_plate(carrier_plate) == plate_number:
                matched_picking = picking
                break
        
        log_vals = {
            'plate_number': plate_number,
            'gate_location_id': gate_location.id,
            'timestamp': fields.Datetime.now(),
            'action': action,
        }
        
        if matched_picking:
            log_vals.update({
                'linked_picking_id': matched_picking.id,
                'status': 'matched',
            })
            gate_log = self.create(log_vals)
            
            picking_type = 'Delivery' if matched_picking.picking_type_code == 'outgoing' else 'Receipt'
            notification_msg = _(
                'Truck [%s] Arrived for %s #%s\n'
                'Partner: %s\n'
                'Gate: %s\n'
                'Time: %s'
            ) % (
                plate_number,
                picking_type,
                matched_picking.name,
                matched_picking.partner_id.name if matched_picking.partner_id else 'N/A',
                gate_location.name,
                fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            )
            
            matched_picking.message_post(
                body=notification_msg,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            
            _logger.info(
                'LPR Match: Plate %s matched to picking %s at gate %s',
                plate_number, matched_picking.name, gate_code
            )
            
            return {
                'status': 'success',
                'signal': 'OPEN_GATE',
                'gate_log_id': gate_log.id,
                'picking_id': matched_picking.id,
                'picking_name': matched_picking.name,
                'partner': matched_picking.partner_id.name if matched_picking.partner_id else None,
                'message': f'Gate opened for {picking_type} {matched_picking.name}',
            }
        
        else:
            log_vals.update({
                'status': 'unmatched',
                'alert_sent': True,
            })
            gate_log = self.create(log_vals)
            
            self._send_security_alert(plate_number, gate_location, gate_log)
            
            _logger.warning(
                'LPR Alert: Unscheduled vehicle %s at gate %s',
                plate_number, gate_code
            )
            
            return {
                'status': 'alert',
                'signal': 'DENY',
                'gate_log_id': gate_log.id,
                'message': f'Security Alert: Unscheduled Vehicle {plate_number}',
                'requires_manual_approval': True,
            }
    
    def _extract_plate_from_picking(self, picking):
        """
        Extract license plate from stock.picking.
        
        Looks for plate number in:
        1. picking.carrier_tracking_ref (if contains plate pattern)
        2. picking.note (search for plate pattern)
        3. picking.partner_id.x_vehicle_plate (custom field if exists)
        """
        if picking.carrier_tracking_ref:
            plate = picking.carrier_tracking_ref.strip()
            if len(plate) >= 5 and len(plate) <= 10:
                return plate
        
        if hasattr(picking, 'x_vehicle_plate') and picking.x_vehicle_plate:
            return picking.x_vehicle_plate
        
        if picking.partner_id and hasattr(picking.partner_id, 'x_vehicle_plate'):
            return picking.partner_id.x_vehicle_plate
        
        return None
    
    def _normalize_plate(self, plate):
        """Normalize license plate for comparison."""
        if not plate:
            return ''
        return plate.upper().replace(' ', '').replace('-', '').replace('.', '')
    
    def _send_security_alert(self, plate_number, gate_location, gate_log):
        """
        Send security alert for unscheduled vehicle.
        
        Notifies security officers via Odoo messaging system.
        """
        security_group = self.env.ref('stock.group_stock_manager', raise_if_not_found=False)
        if not security_group:
            return
        
        alert_msg = _(
            '<strong>SECURITY ALERT: Unscheduled Vehicle</strong><br/>'
            '<b>License Plate:</b> %s<br/>'
            '<b>Gate:</b> %s<br/>'
            '<b>Time:</b> %s<br/>'
            '<b>Action Required:</b> Manual verification needed'
        ) % (
            plate_number,
            gate_location.name,
            fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )
        
        gate_log.message_post(
            body=alert_msg,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[(4, user.partner_id.id) for user in security_group.users[:5]],
        )
    
    def action_manual_approve(self):
        """Manually approve gate access (security officer override)."""
        self.ensure_one()
        self.write({
            'status': 'manual',
            'notes': (self.notes or '') + f'\nManually approved by {self.env.user.name} at {fields.Datetime.now()}',
        })
        
        return {
            'status': 'success',
            'signal': 'OPEN_GATE',
            'message': 'Gate manually opened',
        }
    
    def action_deny_access(self):
        """Deny gate access."""
        self.ensure_one()
        self.write({
            'status': 'denied',
            'notes': (self.notes or '') + f'\nAccess denied by {self.env.user.name} at {fields.Datetime.now()}',
        })
        
        return {
            'status': 'denied',
            'signal': 'DENY',
            'message': 'Access denied',
        }
