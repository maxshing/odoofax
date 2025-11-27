# -*- coding: utf-8 -*-
"""
MRP Work Center Extension for Chemical OS Shop Floor Authorization

Extends mrp.workcenter and mrp.workorder to support:
- RFID-based operator authorization
- Machine interlock control
- Authorized employee tracking
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MrpWorkcenterExtension(models.Model):
    """
    Extended Work Center for Shop Floor Authorization.
    
    Adds RFID authorization requirements and employee access control
    for filling machines f1, f2, f3.
    """
    _inherit = 'mrp.workcenter'
    
    require_rfid_auth = fields.Boolean(
        string='Require RFID Authorization',
        default=False,
        help='If enabled, operators must scan their RFID badge to unlock this machine.',
    )
    
    authorized_employee_ids = fields.Many2many(
        'hr.employee',
        'workcenter_employee_auth_rel',
        'workcenter_id',
        'employee_id',
        string='Authorized Operators',
        help='Employees who are authorized to operate this work center. '
             'Only these employees can unlock the machine via RFID.',
    )
    
    authorized_count = fields.Integer(
        string='Authorized Operators',
        compute='_compute_authorized_count',
    )
    
    machine_state = fields.Selection([
        ('locked', 'Locked (Interlocked)'),
        ('unlocked', 'Unlocked'),
        ('running', 'Running'),
        ('error', 'Error'),
    ], string='Machine State', default='locked', readonly=True,
       help='Current interlock state of the machine.')
    
    last_auth_employee_id = fields.Many2one(
        'hr.employee',
        string='Last Authorized By',
        readonly=True,
    )
    
    last_auth_time = fields.Datetime(
        string='Last Authorization Time',
        readonly=True,
    )
    
    def _compute_authorized_count(self):
        for record in self:
            record.authorized_count = len(record.authorized_employee_ids)
    
    def action_view_authorized_employees(self):
        """Open a view showing all authorized employees."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Authorized Operators: %s') % self.name,
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.authorized_employee_ids.ids)],
            'context': {'create': False},
        }
    
    def check_employee_authorization(self, employee):
        """
        Check if an employee is authorized to operate this work center.
        
        Args:
            employee: hr.employee record
        
        Returns:
            bool: True if authorized, False otherwise
        """
        self.ensure_one()
        
        if not self.require_rfid_auth:
            return True
        
        if not self.authorized_employee_ids:
            _logger.warning(
                'Work center %s requires RFID auth but has no authorized employees',
                self.name
            )
            return False
        
        return employee.id in self.authorized_employee_ids.ids
    
    def action_unlock_machine(self, employee):
        """
        Unlock the machine after successful authorization.
        
        Args:
            employee: hr.employee record who authorized
        
        Returns:
            dict: Result with unlock signal
        """
        self.ensure_one()
        
        self.write({
            'machine_state': 'unlocked',
            'last_auth_employee_id': employee.id,
            'last_auth_time': fields.Datetime.now(),
        })
        
        _logger.info(
            'Machine %s unlocked by employee %s (ID: %s)',
            self.code, employee.name, employee.id
        )
        
        return {
            'status': 'success',
            'signal': 'UNLOCK',
            'machine_code': self.code,
            'authorized_by': employee.name,
            'timestamp': fields.Datetime.now().isoformat(),
        }
    
    def action_lock_machine(self):
        """Lock the machine (return to interlock state)."""
        self.ensure_one()
        self.machine_state = 'locked'
        _logger.info('Machine %s locked', self.code)


class MrpWorkorderExtension(models.Model):
    """
    Extended Work Order for Shop Floor Authorization.
    
    Tracks authorization details for each work order execution.
    """
    _inherit = 'mrp.workorder'
    
    authorized_by = fields.Many2one(
        'hr.employee',
        string='Authorized By',
        readonly=True,
        help='Employee who authorized the start of this work order via RFID.',
    )
    
    auth_timestamp = fields.Datetime(
        string='Authorization Time',
        readonly=True,
        help='Timestamp when the work order was authorized to start.',
    )
    
    rfid_required = fields.Boolean(
        string='RFID Required',
        related='workcenter_id.require_rfid_auth',
        store=True,
    )
    
    is_authorized = fields.Boolean(
        string='Is Authorized',
        compute='_compute_is_authorized',
        store=True,
    )
    
    @api.depends('authorized_by', 'rfid_required')
    def _compute_is_authorized(self):
        for record in self:
            if not record.rfid_required:
                record.is_authorized = True
            else:
                record.is_authorized = bool(record.authorized_by)
    
    def action_authorize_start(self, employee):
        """
        Authorize and start this work order.
        
        Called after successful RFID verification.
        
        Args:
            employee: hr.employee record
        
        Returns:
            dict: Authorization result
        """
        self.ensure_one()
        
        workcenter = self.workcenter_id
        if not workcenter:
            raise UserError(_('Work order has no assigned work center.'))
        
        if workcenter.require_rfid_auth:
            if not workcenter.check_employee_authorization(employee):
                return {
                    'status': 'denied',
                    'message': _('Unauthorized User: %s is not authorized to operate %s') % (
                        employee.name, workcenter.name
                    ),
                }
        
        self.write({
            'authorized_by': employee.id,
            'auth_timestamp': fields.Datetime.now(),
        })
        
        if self.state == 'ready':
            self.button_start()
        
        unlock_result = workcenter.action_unlock_machine(employee)
        
        self.message_post(
            body=_(
                'Work order authorized and started.\n'
                'Operator: %s\n'
                'Badge ID: %s\n'
                'Time: %s'
            ) % (
                employee.name,
                employee.barcode or 'N/A',
                fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ),
            message_type='notification',
        )
        
        _logger.info(
            'Work order %s authorized by %s on machine %s',
            self.display_name, employee.name, workcenter.code
        )
        
        return {
            'status': 'success',
            'signal': 'UNLOCK',
            'workorder_id': self.id,
            'workorder_name': self.display_name,
            'authorized_by': employee.name,
            'authorized_by_id': employee.id,
            'timestamp': fields.Datetime.now().isoformat(),
        }
    
    def get_pending_job_data(self):
        """
        Get job data for HMI display.
        
        Returns:
            dict: Job details for the HMI
        """
        self.ensure_one()
        
        production = self.production_id
        if not production:
            return {}
        
        return {
            'workorder_id': self.id,
            'workorder_name': self.display_name,
            'mo_name': production.name,
            'product': production.product_id.name,
            'product_code': production.product_id.default_code or '',
            'target_qty': production.product_qty,
            'uom': production.product_uom_id.name,
            'priority': production.priority or '0',
            'state': self.state,
            'workcenter': self.workcenter_id.name if self.workcenter_id else '',
            'workcenter_code': self.workcenter_id.code if self.workcenter_id else '',
        }
