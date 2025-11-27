# -*- coding: utf-8 -*-
"""
Personnel Safety & Access Control - RFID Badge System for Chemical OS

Implements zone-based access control using RFID badges.
Fixed readers are installed at:
- Building entrances (H, X, Y, Z)
- Tank Farm gates
- Hazardous zones (S2 Inside Bund)

Features:
- Zone-based access permissions
- Certification requirements for hazardous areas
- Real-time access logging
- Safety officer alerts for unauthorized attempts
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ChemicalAccessZone(models.Model):
    """
    Access Zone definition for RFID-based access control.
    
    Defines restricted areas within the plant and their access requirements.
    """
    _name = 'chemical.access.zone'
    _description = 'Access Control Zone'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Zone Name',
        required=True,
        help='Human-readable zone name (e.g., "Hazardous Material Storage S2").',
    )
    
    code = fields.Char(
        string='Zone Code',
        required=True,
        index=True,
        help='Technical code for API calls (e.g., "S2", "TANK_A", "BLDG_X").',
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    
    location_id = fields.Many2one(
        'stock.location',
        string='Stock Location',
        help='Linked warehouse location for this zone.',
    )
    
    building = fields.Selection([
        ('H', 'Building H - Office/Admin'),
        ('X', 'Factory X - Heavy Drum Filling'),
        ('Y', 'Factory Y - Mixing/Blending'),
        ('Z', 'Factory Z - Small Packaging'),
        ('P', 'Outdoor Areas (P1-P5)'),
    ], string='Building', required=True)
    
    zone_type = fields.Selection([
        ('general', 'General Access'),
        ('restricted', 'Restricted Area'),
        ('hazardous', 'Hazardous Zone'),
        ('tank_farm', 'Tank Farm'),
        ('production', 'Production Area'),
    ], string='Zone Type', default='general', required=True)
    
    is_hazardous = fields.Boolean(
        string='Hazardous Zone',
        compute='_compute_is_hazardous',
        store=True,
    )
    
    required_certification_ids = fields.Many2many(
        'hr.skill',
        'zone_skill_rel',
        'zone_id',
        'skill_id',
        string='Required Certifications',
        help='Skills/certifications required to access this zone.',
    )
    
    required_ppe = fields.Text(
        string='Required PPE',
        help='Personal Protective Equipment required for this zone.',
    )
    
    max_occupancy = fields.Integer(
        string='Max Occupancy',
        help='Maximum number of people allowed in zone simultaneously.',
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    
    employee_ids = fields.Many2many(
        'hr.employee',
        'employee_zone_access_rel',
        'zone_id',
        'employee_id',
        string='Authorized Employees',
        help='Employees with direct access to this zone.',
    )
    
    access_log_ids = fields.One2many(
        'chemical.access.log',
        'zone_id',
        string='Access Logs',
    )
    
    access_log_count = fields.Integer(
        string='Access Log Count',
        compute='_compute_access_log_count',
    )
    
    @api.depends('zone_type')
    def _compute_is_hazardous(self):
        for record in self:
            record.is_hazardous = record.zone_type == 'hazardous'
    
    def _compute_access_log_count(self):
        for record in self:
            record.access_log_count = self.env['chemical.access.log'].search_count([
                ('zone_id', '=', record.id)
            ])
    
    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            existing = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id),
            ])
            if existing:
                raise ValidationError(_('Zone code must be unique: %s') % record.code)
    
    def action_view_access_logs(self):
        """View access logs for this zone."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Access Logs: %s') % self.name,
            'res_model': 'chemical.access.log',
            'view_mode': 'tree,form',
            'domain': [('zone_id', '=', self.id)],
            'context': {'default_zone_id': self.id},
        }


class ChemicalAccessLog(models.Model):
    """
    Access Log for RFID badge scans.
    
    Records every access attempt (successful or denied) for audit trail.
    """
    _name = 'chemical.access.log'
    _description = 'Zone Access Log'
    _order = 'timestamp desc'
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        index=True,
    )
    
    rfid_card_id = fields.Char(
        string='RFID Card ID',
        required=True,
        index=True,
    )
    
    zone_id = fields.Many2one(
        'chemical.access.zone',
        string='Zone',
        required=True,
        index=True,
    )
    
    reader_location = fields.Char(
        string='Reader Location',
        help='Physical location of RFID reader (e.g., "Z-ENTRANCE", "S2-GATE").',
    )
    
    timestamp = fields.Datetime(
        string='Scan Time',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    
    action = fields.Selection([
        ('entry', 'Entry'),
        ('exit', 'Exit'),
    ], string='Action', default='entry')
    
    result = fields.Selection([
        ('granted', 'Access Granted'),
        ('denied', 'Access Denied'),
        ('override', 'Manual Override'),
    ], string='Result', required=True)
    
    denial_reason = fields.Char(
        string='Denial Reason',
        help='Reason for access denial.',
    )
    
    alert_sent = fields.Boolean(
        string='Alert Sent',
        default=False,
    )
    
    @api.model
    def check_access_permission(self, card_id, zone_code, reader_location=None):
        """
        Check if an RFID card holder has permission to access a zone.
        
        Called by RFID reader API when a card is scanned.
        
        Args:
            card_id: str - RFID card ID
            zone_code: str - Zone code (e.g., 'S2', 'BLDG_X')
            reader_location: str - Optional reader location identifier
        
        Returns:
            dict: Access decision with door control signal
        
        Workflow:
        1. Find employee by RFID card ID
        2. Find zone by code
        3. Check if employee has required certifications (for hazardous zones)
        4. Check if employee is in zone's authorized list
        5. Log the access attempt
        6. Return access decision
        """
        Employee = self.env['hr.employee']
        employee = Employee.search([
            ('barcode', '=', card_id),
        ], limit=1)
        
        if not employee:
            _logger.warning('RFID Access: Unknown card %s at zone %s', card_id, zone_code)
            return {
                'status': 'denied',
                'signal': 'DENY',
                'message': 'Unknown RFID card',
                'card_id': card_id,
            }
        
        Zone = self.env['chemical.access.zone']
        zone = Zone.search([
            ('code', '=', zone_code),
            ('active', '=', True),
        ], limit=1)
        
        if not zone:
            _logger.error('RFID Access: Unknown zone %s', zone_code)
            return {
                'status': 'error',
                'signal': 'DENY',
                'message': f'Unknown zone: {zone_code}',
            }
        
        access_granted = True
        denial_reason = None
        
        if zone.is_hazardous and zone.required_certification_ids:
            employee_skills = set()
            if hasattr(employee, 'employee_skill_ids'):
                for skill_line in employee.employee_skill_ids:
                    employee_skills.add(skill_line.skill_id.id)
            
            required_skills = set(zone.required_certification_ids.ids)
            missing_skills = required_skills - employee_skills
            
            if missing_skills:
                access_granted = False
                missing_names = zone.required_certification_ids.filtered(
                    lambda s: s.id in missing_skills
                ).mapped('name')
                denial_reason = f'Missing certifications: {", ".join(missing_names)}'
        
        if access_granted and zone.employee_ids:
            if employee.id not in zone.employee_ids.ids:
                direct_access = self._check_employee_access_zones(employee, zone)
                if not direct_access:
                    access_granted = False
                    denial_reason = 'Not in authorized employee list'
        
        log_vals = {
            'employee_id': employee.id,
            'rfid_card_id': card_id,
            'zone_id': zone.id,
            'reader_location': reader_location or zone_code,
            'timestamp': fields.Datetime.now(),
            'action': 'entry',
            'result': 'granted' if access_granted else 'denied',
            'denial_reason': denial_reason,
        }
        
        access_log = self.create(log_vals)
        
        if access_granted:
            _logger.info(
                'RFID Access Granted: Employee %s (%s) at zone %s',
                employee.name, card_id, zone_code
            )
            
            return {
                'status': 'granted',
                'signal': 'OPEN_DOOR',
                'access_log_id': access_log.id,
                'employee_id': employee.id,
                'employee_name': employee.name,
                'zone': zone.name,
                'message': f'Access granted to {employee.name}',
            }
        else:
            access_log.alert_sent = True
            self._send_access_alert(employee, zone, denial_reason, access_log)
            
            _logger.warning(
                'RFID Access Denied: Employee %s (%s) at zone %s - %s',
                employee.name, card_id, zone_code, denial_reason
            )
            
            return {
                'status': 'denied',
                'signal': 'DENY',
                'access_log_id': access_log.id,
                'employee_id': employee.id,
                'employee_name': employee.name,
                'zone': zone.name,
                'reason': denial_reason,
                'message': f'Access denied: {denial_reason}',
            }
    
    def _check_employee_access_zones(self, employee, zone):
        """Check if employee has access via their assigned zones."""
        if hasattr(employee, 'access_zone_ids'):
            return zone.id in employee.access_zone_ids.ids
        return False
    
    def _send_access_alert(self, employee, zone, reason, access_log):
        """
        Send alert for unauthorized access attempt.
        
        Notifies safety officers for hazardous zone violations.
        """
        if not zone.is_hazardous:
            return
        
        alert_msg = _(
            '<strong>UNAUTHORIZED ACCESS ATTEMPT</strong><br/>'
            '<b>Employee:</b> %s<br/>'
            '<b>Badge ID:</b> %s<br/>'
            '<b>Zone:</b> %s<br/>'
            '<b>Reason:</b> %s<br/>'
            '<b>Time:</b> %s'
        ) % (
            employee.name,
            employee.barcode or 'N/A',
            zone.name,
            reason,
            fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )
        
        access_log.message_post(
            body=alert_msg,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )


class HrEmployeeExtension(models.Model):
    """
    Extended HR Employee for RFID access control.
    """
    _inherit = 'hr.employee'
    
    access_zone_ids = fields.Many2many(
        'chemical.access.zone',
        'employee_zone_access_rel',
        'employee_id',
        'zone_id',
        string='Authorized Zones',
        help='Zones this employee is authorized to access.',
    )
    
    access_zone_count = fields.Integer(
        string='Authorized Zones',
        compute='_compute_access_zone_count',
    )
    
    last_access_time = fields.Datetime(
        string='Last Access',
        compute='_compute_last_access',
    )
    
    last_access_zone = fields.Char(
        string='Last Zone',
        compute='_compute_last_access',
    )
    
    def _compute_access_zone_count(self):
        for record in self:
            record.access_zone_count = len(record.access_zone_ids)
    
    def _compute_last_access(self):
        AccessLog = self.env['chemical.access.log']
        for record in self:
            last_log = AccessLog.search([
                ('employee_id', '=', record.id),
            ], order='timestamp desc', limit=1)
            
            if last_log:
                record.last_access_time = last_log.timestamp
                record.last_access_zone = last_log.zone_id.name if last_log.zone_id else ''
            else:
                record.last_access_time = False
                record.last_access_zone = ''
    
    def action_view_access_logs(self):
        """View access logs for this employee."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Access Logs: %s') % self.name,
            'res_model': 'chemical.access.log',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
        }
