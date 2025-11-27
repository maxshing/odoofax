# -*- coding: utf-8 -*-
"""
IoT Point Model for Chemical OS

Defines IoT sensor points for the plant's instrumentation system:
- Mass Flow Meters (MFM) on pumps and filling machines
- Differential Pressure (DP) sensors on tanks
- Temperature sensors for heated tanks

Handles the "Pump-As-Meter" scenarios for semi-automatic filling lines.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class IotPoint(models.Model):
    """
    IoT Point - Represents a physical sensor or measurement point.
    
    Each point is linked to a specific location (tank) or equipment (pump/filler)
    and receives real-time data from the plant's instrumentation system.
    """
    _name = 'chemical.iot.point'
    _description = 'IoT Measurement Point'
    _order = 'point_type, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string='Point ID',
        required=True,
        index=True,
        help='Unique identifier for this measurement point (e.g., FIT-P1, FIT-F1, LIT-A01).',
    )
    
    description = fields.Char(
        string='Description',
        help='Human-readable description of this measurement point.',
    )
    
    point_type = fields.Selection([
        ('flow', 'Flow Meter (FIT)'),
        ('level', 'Level Transmitter (LIT)'),
        ('pressure', 'Pressure Transmitter (PIT)'),
        ('temperature', 'Temperature Transmitter (TIT)'),
        ('density', 'Density Meter (DIT)'),
        ('viscosity', 'Viscosity Meter (VIT)'),
        ('particle', 'Particle Counter (PCS)'),
        ('moisture', 'Moisture Analyzer (MIT)'),
        ('valve', 'Valve Controller (VLV)'),
    ], string='Sensor Type', required=True, default='flow')
    
    location_type = fields.Selection([
        ('pump', 'Pump'),
        ('filler', 'Filling Machine'),
        ('mixer', 'Mixing Tank'),
        ('tank_inlet', 'Tank Inlet'),
        ('tank_outlet', 'Tank Outlet'),
        ('tank_level', 'Tank Level'),
        ('pipeline', 'Pipeline'),
        ('lab', 'Laboratory Instrument'),
    ], string='Location Type', required=True, default='pump')
    
    pump_id = fields.Many2one(
        'maintenance.equipment',
        string='Pump',
        domain="[('equipment_type', '=', 'pump')]",
        help='Pump equipment this sensor is attached to.',
    )
    
    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Work Center',
        help='Filling machine or work center this sensor monitors.',
    )
    
    tank_location_id = fields.Many2one(
        'stock.location',
        string='Tank Location',
        domain="[('is_tank', '=', True)]",
        help='Tank location this sensor monitors (for inlet/outlet/level sensors).',
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        default=lambda self: self.env.ref('uom.product_uom_litre', raise_if_not_found=False),
        help='Unit of measure for sensor readings.',
    )
    
    state = fields.Selection([
        ('active', 'Active'),
        ('maintenance', 'Maintenance'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    ], string='Status', default='active', tracking=True)
    
    last_reading = fields.Float(
        string='Last Reading',
        digits='Product Unit of Measure',
        help='Most recent sensor reading.',
    )
    
    last_reading_time = fields.Datetime(
        string='Last Reading Time',
        help='Timestamp of the most recent reading.',
    )
    
    reading_ids = fields.One2many(
        'chemical.iot.reading',
        'point_id',
        string='Readings',
    )
    
    reading_count = fields.Integer(
        string='Reading Count',
        compute='_compute_reading_count',
    )
    
    variance_threshold = fields.Float(
        string='Variance Threshold (%)',
        default=2.0,
        help='Maximum allowed variance between cross-checked sensors (for redundancy alerts).',
    )
    
    cross_check_point_id = fields.Many2one(
        'chemical.iot.point',
        string='Cross-Check Point',
        help='Another sensor to cross-validate readings against (for leak detection).',
    )
    
    active = fields.Boolean(default=True)
    
    def _compute_reading_count(self):
        for record in self:
            record.reading_count = len(record.reading_ids)
    
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'IoT Point ID must be unique!'),
    ]
    
    def action_view_readings(self):
        """Open reading history for this point."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Readings: %s') % self.name,
            'res_model': 'chemical.iot.reading',
            'view_mode': 'tree,form,graph',
            'domain': [('point_id', '=', self.id)],
            'context': {'default_point_id': self.id},
        }


class IotReading(models.Model):
    """
    IoT Reading - Individual sensor reading record.
    
    Stores timestamped readings from IoT sensors for historical analysis
    and process traceability.
    """
    _name = 'chemical.iot.reading'
    _description = 'IoT Sensor Reading'
    _order = 'reading_time desc'
    
    point_id = fields.Many2one(
        'chemical.iot.point',
        string='IoT Point',
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    reading_time = fields.Datetime(
        string='Reading Time',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    
    value = fields.Float(
        string='Value',
        digits='Product Unit of Measure',
        required=True,
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit',
        related='point_id.uom_id',
        readonly=True,
    )
    
    batch_reference = fields.Char(
        string='Batch Reference',
        help='Manufacturing order or transfer reference.',
    )
    
    source_tank_id = fields.Many2one(
        'stock.location',
        string='Source Tank',
        domain="[('is_tank', '=', True)]",
        help='Tank being drawn from during this reading.',
    )
    
    dest_tank_id = fields.Many2one(
        'stock.location',
        string='Destination',
        help='Destination location or work center.',
    )
    
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Stock Move',
        help='Stock move created from this reading.',
    )
    
    cross_check_status = fields.Selection([
        ('pending', 'Pending Validation'),
        ('matched', 'Matched'),
        ('variance', 'Variance Detected'),
        ('alert', 'Alert Raised'),
    ], string='Cross-Check Status', default='pending')
    
    variance_pct = fields.Float(
        string='Variance %',
        help='Percentage variance from cross-check point.',
    )
    
    notes = fields.Text(string='Notes')


class FlowToStockEngine(models.Model):
    """
    Flow-to-Stock Engine - Automates inventory transactions based on IoT data.
    
    This is the "Cyber-Physical" integration layer that converts sensor readings
    into stock movements for precise costing and inventory tracking.
    """
    _name = 'chemical.flow.engine'
    _description = 'Flow-to-Stock Automation Engine'
    
    name = fields.Char(
        string='Engine Name',
        default='Flow-to-Stock Engine',
        readonly=True,
    )
    
    state = fields.Selection([
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('error', 'Error'),
    ], string='Status', default='running')
    
    last_run = fields.Datetime(string='Last Run')
    
    processed_count = fields.Integer(
        string='Readings Processed',
        default=0,
    )
    
    alert_count = fields.Integer(
        string='Alerts Raised',
        default=0,
    )
    
    def process_pump_flow_data(self, pump_id, flow_qty, source_tank_id=None, mo_id=None):
        """
        Process flow data from a Pump Mass Flow Meter.
        
        This is the core "Pump-As-Meter" logic that handles scenarios where
        the pump is the source of truth for consumption tracking.
        
        Algorithm:
        1. Identify the Active Source Tank for this pump
        2. Find the Active Manufacturing Order (MO) or Internal Transfer
        3. Create a stock move: Decrease Stock from Source Tank by flow_qty
        
        Args:
            pump_id: ID of the pump equipment
            flow_qty: Flow quantity in liters
            source_tank_id: Optional - manually specified source tank
            mo_id: Optional - manufacturing order reference
        
        Returns:
            dict: Result containing created stock move and any alerts
        """
        Pump = self.env['maintenance.equipment']
        Location = self.env['stock.location']
        TankContent = self.env['chemical.tank.content']
        TankHistory = self.env['chemical.tank.history']
        IotReading = self.env['chemical.iot.reading']
        
        pump = Pump.browse(pump_id)
        if not pump.exists():
            raise UserError(_('Pump not found: %s') % pump_id)
        
        if not pump.is_metered:
            _logger.warning('Attempted to process flow data for non-metered pump: %s', pump.name)
            return {'error': 'Pump is not metered'}
        
        result = {
            'pump': pump.name,
            'flow_qty': flow_qty,
            'stock_move_id': False,
            'tank_history_id': False,
            'alerts': [],
        }
        
        if source_tank_id:
            source_tank = Location.browse(source_tank_id)
        else:
            source_tank = self._identify_active_source_tank(pump)
        
        if not source_tank:
            result['alerts'].append({
                'type': 'warning',
                'message': _('Could not identify active source tank for pump %s') % pump.name,
            })
            return result
        
        tank_content = TankContent.search([
            ('location_id', '=', source_tank.id)
        ], limit=1)
        
        if not tank_content:
            result['alerts'].append({
                'type': 'error',
                'message': _('No tank content record found for %s') % source_tank.name,
            })
            return result
        
        if tank_content.quantity < flow_qty:
            result['alerts'].append({
                'type': 'warning',
                'message': _('Insufficient quantity in %s. Available: %.2f, Requested: %.2f') % (
                    source_tank.name, tank_content.quantity, flow_qty
                ),
            })
        
        try:
            stock_move = self._create_stock_move_for_draw(
                source_tank=source_tank,
                product=tank_content.product_id,
                quantity=flow_qty,
                pump=pump,
                mo_reference=mo_id,
            )
            
            if stock_move:
                result['stock_move_id'] = stock_move.id
            
            tank_content.action_record_draw(
                quantity=flow_qty,
                notes=_('Automated draw from pump %s flow meter. MO: %s. Stock Move: %s') % (
                    pump.name, mo_id or 'N/A', stock_move.name if stock_move else 'N/A'
                )
            )
            
            history = TankHistory.search([
                ('tank_content_id', '=', tank_content.id)
            ], order='id desc', limit=1)
            
            result['tank_history_id'] = history.id if history else False
            
            iot_point = self.env['chemical.iot.point'].search([
                ('pump_id', '=', pump.id),
                ('point_type', '=', 'flow')
            ], limit=1)
            
            if iot_point:
                reading = IotReading.create({
                    'point_id': iot_point.id,
                    'value': flow_qty,
                    'source_tank_id': source_tank.id,
                    'batch_reference': mo_id or '',
                    'stock_move_id': stock_move.id if stock_move else False,
                    'notes': _('Pump flow processed and stock updated.'),
                })
                
                iot_point.write({
                    'last_reading': flow_qty,
                    'last_reading_time': fields.Datetime.now(),
                })
                
                if iot_point.cross_check_point_id:
                    self._perform_cross_check(iot_point, reading, result)
            
            self.write({
                'last_run': fields.Datetime.now(),
                'processed_count': self.processed_count + 1,
            })
            
            _logger.info(
                'Pump flow processed: Pump=%s, Tank=%s, Qty=%.2f, Move=%s',
                pump.name, source_tank.name, flow_qty, 
                stock_move.name if stock_move else 'N/A'
            )
            
        except Exception as e:
            result['alerts'].append({
                'type': 'error',
                'message': str(e),
            })
            _logger.error('Error processing pump flow: %s', str(e))
        
        return result
    
    def _create_stock_move_for_draw(self, source_tank, product, quantity, pump, mo_reference=None):
        """
        Create a stock move to record inventory draw from tank.
        
        This creates a proper stock.move record for accurate inventory tracking
        and costing, moving product from the tank to a consumption location.
        
        Args:
            source_tank: stock.location - The tank being drawn from
            product: product.product - The product being drawn
            quantity: float - Quantity in liters
            pump: maintenance.equipment - The pump performing the draw
            mo_reference: str - Optional manufacturing order reference
        
        Returns:
            stock.move record or False
        """
        StockMove = self.env.get('stock.move')
        if not StockMove:
            _logger.warning('stock.move model not available')
            return False
        
        if not product:
            _logger.warning('No product specified for stock move')
            return False
        
        dest_location = self.env['stock.location'].search([
            ('usage', '=', 'production'),
        ], limit=1)
        
        if not dest_location:
            dest_location = self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('name', 'ilike', 'production'),
            ], limit=1)
        
        if not dest_location:
            _logger.warning('No production destination location found')
            return False
        
        uom = product.uom_id
        
        move_vals = {
            'name': _('IoT Flow Draw: %s via %s') % (product.name, pump.name),
            'product_id': product.id,
            'product_uom_qty': quantity,
            'product_uom': uom.id,
            'location_id': source_tank.id,
            'location_dest_id': dest_location.id,
            'origin': mo_reference or _('IoT Flow Engine - %s') % pump.name,
        }
        
        try:
            with self.env.cr.savepoint():
                move = StockMove.create(move_vals)
                
                move._action_confirm()
                move._action_assign()
                
                StockMoveLine = self.env.get('stock.move.line')
                if StockMoveLine and move.state != 'done':
                    if not move.move_line_ids:
                        StockMoveLine.create({
                            'move_id': move.id,
                            'product_id': product.id,
                            'product_uom_id': uom.id,
                            'location_id': source_tank.id,
                            'location_dest_id': dest_location.id,
                            'quantity': quantity,
                        })
                    else:
                        move.move_line_ids.write({'quantity': quantity})
                    
                    move.with_context(bypass_immediate_transfer=True)._action_done()
                
                _logger.info(
                    'Stock move created and validated: %s, Qty: %.2f %s, From: %s, State: %s',
                    move.name, quantity, uom.name, source_tank.name, move.state
                )
                
                return move
            
        except Exception as e:
            _logger.error('Failed to create stock move: %s', str(e))
            return False
    
    def _identify_active_source_tank(self, pump):
        """
        Identify which source tank is currently active for a pump.
        
        Logic:
        - Check pump's linked tank locations
        - For now, return the first tank with product
        - Future: Integrate with PLC valve signals
        
        Args:
            pump: maintenance.equipment record
        
        Returns:
            stock.location record or False
        """
        if not pump.location_ids:
            return False
        
        TankContent = self.env['chemical.tank.content']
        
        for location in pump.location_ids:
            content = TankContent.search([
                ('location_id', '=', location.id),
                ('quantity', '>', 0),
                ('state', 'not in', ['cleaning', 'maintenance']),
            ], limit=1)
            
            if content:
                return location
        
        return pump.location_ids[0] if pump.location_ids else False
    
    def _perform_cross_check(self, iot_point, reading, result):
        """
        Perform cross-check validation between two sensors.
        
        Compares pump flow meter reading with machine flow meter reading
        to detect potential leaks or calibration issues.
        
        Args:
            iot_point: The primary IoT point
            reading: The reading record to validate
            result: Result dict to append alerts to
        """
        cross_point = iot_point.cross_check_point_id
        if not cross_point:
            return
        
        time_window = timedelta(minutes=5)
        reading_time = reading.reading_time or fields.Datetime.now()
        
        cross_readings = self.env['chemical.iot.reading'].search([
            ('point_id', '=', cross_point.id),
            ('reading_time', '>=', reading_time - time_window),
            ('reading_time', '<=', reading_time + time_window),
        ])
        
        if not cross_readings:
            reading.write({'cross_check_status': 'pending'})
            return
        
        cross_total = sum(cross_readings.mapped('value'))
        pump_value = reading.value
        
        if pump_value == 0:
            variance_pct = 100.0 if cross_total > 0 else 0.0
        else:
            variance_pct = abs(pump_value - cross_total) / pump_value * 100
        
        reading.write({'variance_pct': variance_pct})
        
        threshold = iot_point.variance_threshold or 2.0
        
        if variance_pct <= threshold:
            reading.write({'cross_check_status': 'matched'})
        elif variance_pct <= threshold * 2:
            reading.write({'cross_check_status': 'variance'})
            result['alerts'].append({
                'type': 'warning',
                'message': _('Variance detected between %s and %s: %.2f%% (Threshold: %.2f%%)') % (
                    iot_point.name, cross_point.name, variance_pct, threshold
                ),
            })
        else:
            reading.write({'cross_check_status': 'alert'})
            self.alert_count += 1
            result['alerts'].append({
                'type': 'critical',
                'message': _('LEAKAGE/CALIBRATION ALERT: %s vs %s variance %.2f%% exceeds threshold!') % (
                    iot_point.name, cross_point.name, variance_pct
                ),
            })
            
            self._create_maintenance_request(iot_point, cross_point, variance_pct)
    
    def _create_maintenance_request(self, point1, point2, variance_pct):
        """Create a maintenance request for calibration check."""
        MaintenanceRequest = self.env.get('maintenance.request')
        if not MaintenanceRequest:
            return
        
        equipment = point1.pump_id or point2.pump_id
        if not equipment:
            return
        
        MaintenanceRequest.create({
            'name': _('Calibration Check: %s / %s') % (point1.name, point2.name),
            'equipment_id': equipment.id,
            'description': _(
                'Flow meter variance of %.2f%% detected between sensors.\n'
                'Possible causes:\n'
                '- Pipeline leak between pump and machine\n'
                '- Sensor calibration drift\n'
                '- Air in lines\n\n'
                'Please inspect and recalibrate as needed.'
            ) % variance_pct,
            'priority': '2',
            'request_date': fields.Date.today(),
        })
