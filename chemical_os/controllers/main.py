# -*- coding: utf-8 -*-
"""
Shop Floor Authorization API Controller for Chemical OS

Provides REST API endpoints for HMI/PLC integration:
- GET /chemical/get_pending_job - Retrieve pending work order for a machine
- POST /chemical/authorize_start - Authorize and unlock machine via RFID

Security: Uses Odoo's standard authentication. For machine-to-machine
communication, API keys or token-based auth should be configured.
"""

from odoo import http, fields, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class ShopFloorAuthController(http.Controller):
    """
    Shop Floor Authorization API Controller.
    
    Provides the bridge between Odoo and the HMI/PLC systems
    for RFID-based operator authorization.
    
    Security: Uses 'user' authentication requiring valid session or API key.
    For machine-to-machine communication, create a dedicated API user and
    use token-based authentication via X-API-Key header or session cookies.
    """
    
    def _validate_api_key(self, api_key):
        """
        Validate API key for machine-to-machine authentication.
        
        The API key should be configured as an environment variable
        or stored in ir.config_parameter as 'chemical_os.api_key'.
        """
        if not api_key:
            return False
        
        config_key = request.env['ir.config_parameter'].sudo().get_param(
            'chemical_os.shop_floor_api_key', default=''
        )
        
        if config_key and api_key == config_key:
            return True
        
        return False
    
    def _check_authorization(self):
        """Check if the request is properly authorized."""
        api_key = request.httprequest.headers.get('X-API-Key')
        if api_key and self._validate_api_key(api_key):
            return True
        
        if request.env.user and request.env.user.id != request.env.ref('base.public_user').id:
            return True
        
        return False
    
    @http.route(
        '/chemical/get_pending_job',
        type='json',
        auth='user',
        methods=['GET', 'POST'],
        csrf=False,
    )
    def get_pending_job(self, machine_code=None, **kwargs):
        """
        Get the highest priority pending work order for a machine.
        
        Called by HMI to display job details on the operator screen.
        
        Args:
            machine_code: str - Machine code (e.g., 'f1', 'f2', 'f3')
        
        Returns:
            dict: Job details or error message
            
        Example Request:
            POST /chemical/get_pending_job
            {"jsonrpc": "2.0", "method": "call", "params": {"machine_code": "f1"}}
            Headers: X-API-Key: your-api-key
        
        Example Response:
            {
                "mo_name": "MO-001",
                "product": "Lubricant A",
                "target_qty": 500,
                "uom": "kg",
                "workorder_id": 123
            }
        """
        if not self._check_authorization():
            return {
                'status': 'error',
                'message': 'Unauthorized: Valid API key or user session required',
            }
        
        if not machine_code:
            return {
                'status': 'error',
                'message': 'Machine code is required',
            }
        
        try:
            Workcenter = request.env['mrp.workcenter'].sudo()
            workcenter = Workcenter.search([
                ('code', '=', machine_code.upper()),
            ], limit=1)
            
            if not workcenter:
                workcenter = Workcenter.search([
                    ('code', 'ilike', machine_code),
                ], limit=1)
            
            if not workcenter:
                return {
                    'status': 'error',
                    'message': f'Machine not found: {machine_code}',
                }
            
            Workorder = request.env['mrp.workorder'].sudo()
            pending_order = Workorder.search([
                ('workcenter_id', '=', workcenter.id),
                ('state', 'in', ['ready', 'waiting']),
            ], order='production_id.priority desc, production_id.date_start asc', limit=1)
            
            if not pending_order:
                return {
                    'status': 'no_job',
                    'message': f'No pending jobs for machine {machine_code}',
                    'machine_code': machine_code,
                    'machine_name': workcenter.name,
                }
            
            job_data = pending_order.get_pending_job_data()
            job_data['status'] = 'success'
            job_data['machine_code'] = machine_code
            job_data['machine_name'] = workcenter.name
            job_data['require_rfid'] = workcenter.require_rfid_auth
            
            _logger.info(
                'Pending job retrieved for machine %s: %s',
                machine_code, job_data.get('mo_name')
            )
            
            return job_data
            
        except Exception as e:
            _logger.error('Error getting pending job: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
    
    @http.route(
        '/chemical/authorize_start',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def authorize_start(self, machine_code=None, mo_name=None, rfid_tag=None, **kwargs):
        """
        Authorize and start a work order via RFID badge scan.
        
        Called by HMI after operator scans their RFID badge.
        
        Args:
            machine_code: str - Machine code (e.g., 'f1')
            mo_name: str - Manufacturing order name (e.g., 'MO-001')
            rfid_tag: str - RFID badge ID (maps to hr.employee.barcode)
        
        Returns:
            dict: Authorization result with UNLOCK signal or denial
            
        Example Request:
            POST /chemical/authorize_start
            Headers: X-API-Key: your-api-key
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "machine_code": "f1",
                    "mo_name": "MO-001",
                    "rfid_tag": "12345678"
                }
            }
        
        Example Success Response:
            {
                "status": "success",
                "signal": "UNLOCK",
                "authorized_by": "John Smith",
                "timestamp": "2024-01-15T10:30:00"
            }
        
        Example Denial Response:
            {
                "status": "denied",
                "message": "Unauthorized User"
            }
        """
        if not self._check_authorization():
            return {
                'status': 'error',
                'message': 'Unauthorized: Valid API key or user session required',
            }
        
        if not all([machine_code, mo_name, rfid_tag]):
            missing = []
            if not machine_code:
                missing.append('machine_code')
            if not mo_name:
                missing.append('mo_name')
            if not rfid_tag:
                missing.append('rfid_tag')
            return {
                'status': 'error',
                'message': f'Missing required parameters: {", ".join(missing)}',
            }
        
        try:
            Employee = request.env['hr.employee'].sudo()
            employee = Employee.search([
                ('barcode', '=', rfid_tag),
            ], limit=1)
            
            if not employee:
                employee = Employee.search([
                    ('barcode', 'ilike', rfid_tag),
                ], limit=1)
            
            if not employee:
                _logger.warning(
                    'RFID authorization failed: Unknown badge %s on machine %s',
                    rfid_tag, machine_code
                )
                return {
                    'status': 'denied',
                    'message': 'Unknown RFID badge. Please contact supervisor.',
                    'rfid_tag': rfid_tag,
                }
            
            Workcenter = request.env['mrp.workcenter'].sudo()
            workcenter = Workcenter.search([
                '|',
                ('code', '=', machine_code.upper()),
                ('code', 'ilike', machine_code),
            ], limit=1)
            
            if not workcenter:
                return {
                    'status': 'error',
                    'message': f'Machine not found: {machine_code}',
                }
            
            if workcenter.require_rfid_auth:
                if not workcenter.check_employee_authorization(employee):
                    _logger.warning(
                        'RFID authorization denied: Employee %s not authorized for machine %s',
                        employee.name, machine_code
                    )
                    return {
                        'status': 'denied',
                        'message': f'Unauthorized User: {employee.name} is not authorized to operate {workcenter.name}',
                        'employee': employee.name,
                        'machine': workcenter.name,
                    }
            
            Production = request.env['mrp.production'].sudo()
            production = Production.search([
                ('name', '=', mo_name),
            ], limit=1)
            
            if not production:
                production = Production.search([
                    ('name', 'ilike', mo_name),
                ], limit=1)
            
            if not production:
                return {
                    'status': 'error',
                    'message': f'Manufacturing order not found: {mo_name}',
                }
            
            Workorder = request.env['mrp.workorder'].sudo()
            workorder = Workorder.search([
                ('production_id', '=', production.id),
                ('workcenter_id', '=', workcenter.id),
                ('state', 'in', ['ready', 'waiting', 'progress']),
            ], limit=1)
            
            if not workorder:
                return {
                    'status': 'error',
                    'message': f'No active work order found for {mo_name} on {machine_code}',
                }
            
            result = workorder.action_authorize_start(employee)
            
            if result.get('status') == 'success':
                result['mo_name'] = mo_name
                result['machine_code'] = machine_code
                result['product'] = production.product_id.name
                result['target_qty'] = production.product_qty
                result['uom'] = production.product_uom_id.name
            
            return result
            
        except Exception as e:
            _logger.error('Error in authorize_start: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
    
    @http.route(
        '/chemical/machine_status',
        type='json',
        auth='user',
        methods=['GET', 'POST'],
        csrf=False,
    )
    def get_machine_status(self, machine_code=None, **kwargs):
        """
        Get current status of a machine.
        
        Args:
            machine_code: str - Machine code
        
        Returns:
            dict: Machine status information
        """
        if not self._check_authorization():
            return {
                'status': 'error',
                'message': 'Unauthorized: Valid API key or user session required',
            }
        
        if not machine_code:
            return {
                'status': 'error',
                'message': 'Machine code is required',
            }
        
        try:
            Workcenter = request.env['mrp.workcenter'].sudo()
            workcenter = Workcenter.search([
                '|',
                ('code', '=', machine_code.upper()),
                ('code', 'ilike', machine_code),
            ], limit=1)
            
            if not workcenter:
                return {
                    'status': 'error',
                    'message': f'Machine not found: {machine_code}',
                }
            
            return {
                'status': 'success',
                'machine_code': workcenter.code,
                'machine_name': workcenter.name,
                'machine_state': workcenter.machine_state,
                'require_rfid': workcenter.require_rfid_auth,
                'last_auth_by': workcenter.last_auth_employee_id.name if workcenter.last_auth_employee_id else None,
                'last_auth_time': workcenter.last_auth_time.isoformat() if workcenter.last_auth_time else None,
                'authorized_operator_count': workcenter.authorized_count,
            }
            
        except Exception as e:
            _logger.error('Error getting machine status: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
    
    @http.route(
        '/chemical/complete_job',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def complete_job(self, machine_code=None, mo_name=None, actual_qty=None, **kwargs):
        """
        Mark a job as complete and lock the machine.
        
        This endpoint:
        1. Finds the active work order for the machine/MO combination
        2. Records the actual quantity produced
        3. Completes the work order
        4. Locks the machine
        5. Optionally marks the MO as done if all work orders are complete
        
        Args:
            machine_code: str - Machine code
            mo_name: str - Manufacturing order name
            actual_qty: float - Actual quantity produced
        
        Returns:
            dict: Completion result with LOCK signal
        """
        if not self._check_authorization():
            return {
                'status': 'error',
                'message': 'Unauthorized: Valid API key or user session required',
            }
        
        if not all([machine_code, mo_name]):
            return {
                'status': 'error',
                'message': 'machine_code and mo_name are required',
            }
        
        try:
            Workcenter = request.env['mrp.workcenter'].sudo()
            workcenter = Workcenter.search([
                '|',
                ('code', '=', machine_code.upper()),
                ('code', 'ilike', machine_code),
            ], limit=1)
            
            if not workcenter:
                return {
                    'status': 'error',
                    'message': f'Machine not found: {machine_code}',
                }
            
            Production = request.env['mrp.production'].sudo()
            production = Production.search([
                '|',
                ('name', '=', mo_name),
                ('name', 'ilike', mo_name),
            ], limit=1)
            
            if not production:
                return {
                    'status': 'error',
                    'message': f'Manufacturing order not found: {mo_name}',
                }
            
            Workorder = request.env['mrp.workorder'].sudo()
            workorder = Workorder.search([
                ('production_id', '=', production.id),
                ('workcenter_id', '=', workcenter.id),
                ('state', '=', 'progress'),
            ], limit=1)
            
            if not workorder:
                workorder = Workorder.search([
                    ('production_id', '=', production.id),
                    ('workcenter_id', '=', workcenter.id),
                    ('state', 'in', ['ready', 'waiting']),
                ], limit=1)
            
            result = {
                'status': 'success',
                'signal': 'LOCK',
                'mo_name': mo_name,
                'machine_code': machine_code,
                'message': 'Job completed, machine locked',
            }
            
            if workorder:
                if actual_qty is not None:
                    workorder.qty_produced = actual_qty
                    result['actual_qty'] = actual_qty
                
                if workorder.state == 'progress':
                    try:
                        workorder.button_finish()
                        result['workorder_finished'] = True
                        
                        workorder.message_post(
                            body=_(
                                'Work order completed via Shop Floor API.\n'
                                'Machine: %s\n'
                                'Actual Qty: %s\n'
                                'Time: %s'
                            ) % (
                                machine_code,
                                actual_qty or 'N/A',
                                fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            ),
                            message_type='notification',
                        )
                    except Exception as wo_error:
                        _logger.warning('Could not finish work order: %s', str(wo_error))
                        result['workorder_finish_error'] = str(wo_error)
                
                pending_workorders = Workorder.search([
                    ('production_id', '=', production.id),
                    ('state', 'not in', ['done', 'cancel']),
                ])
                
                if not pending_workorders:
                    result['all_workorders_complete'] = True
                    _logger.info('All work orders complete for MO %s', mo_name)
            else:
                result['workorder_warning'] = 'No active work order found for this machine/MO'
            
            workcenter.action_lock_machine()
            
            _logger.info(
                'Job completed on machine %s for MO %s, qty: %s',
                machine_code, mo_name, actual_qty
            )
            
            return result
            
        except Exception as e:
            _logger.error('Error completing job: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
    
    @http.route(
        '/chemical/lpr_event',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def lpr_event(self, plate_number=None, gate_code=None, action='entry', **kwargs):
        """
        Process LPR camera event for vehicle access control.
        
        Called by LPR camera system when a license plate is detected.
        
        Args:
            plate_number: str - Detected license plate number
            gate_code: str - Gate location code (P1, P3)
            action: str - 'entry' or 'exit'
        
        Returns:
            dict: Gate control signal (OPEN_GATE or DENY)
        """
        if not self._check_authorization():
            return {
                'status': 'error',
                'message': 'Unauthorized: Valid API key or user session required',
            }
        
        if not plate_number or not gate_code:
            return {
                'status': 'error',
                'message': 'plate_number and gate_code are required',
            }
        
        try:
            GateLog = request.env['chemical.gate.log'].sudo()
            result = GateLog.process_lpr_event(plate_number, gate_code, action)
            return result
            
        except Exception as e:
            _logger.error('LPR event error: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
    
    @http.route(
        '/chemical/rfid_access',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def rfid_access(self, card_id=None, zone_code=None, reader_location=None, **kwargs):
        """
        Check RFID badge access permission for a zone.
        
        Called by RFID reader when an employee scans their badge.
        
        Args:
            card_id: str - RFID card ID
            zone_code: str - Zone code (S2, BLDG_X, etc.)
            reader_location: str - Physical reader location identifier
        
        Returns:
            dict: Access decision (OPEN_DOOR or DENY)
        """
        if not self._check_authorization():
            return {
                'status': 'error',
                'message': 'Unauthorized: Valid API key or user session required',
            }
        
        if not card_id or not zone_code:
            return {
                'status': 'error',
                'message': 'card_id and zone_code are required',
            }
        
        try:
            AccessLog = request.env['chemical.access.log'].sudo()
            result = AccessLog.check_access_permission(card_id, zone_code, reader_location)
            return result
            
        except Exception as e:
            _logger.error('RFID access error: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
    
    @http.route(
        '/chemical/encode_drum_tag',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def encode_drum_tag(self, production_id=None, workcenter_code=None, 
                        quantity=None, container_spec_id=None, **kwargs):
        """
        Encode RFID tag for a newly filled drum.
        
        Called by filling machine (f1, f2, f3) when drum filling is complete.
        
        Args:
            production_id: int - Manufacturing order ID
            workcenter_code: str - Filling machine code
            quantity: float - Filled quantity
            container_spec_id: int - Container specification ID
        
        Returns:
            dict: Tag data for RFID writer (WRITE_TAG signal)
        """
        if not self._check_authorization():
            return {
                'status': 'error',
                'message': 'Unauthorized: Valid API key or user session required',
            }
        
        if not production_id:
            return {
                'status': 'error',
                'message': 'production_id is required',
            }
        
        try:
            RfidTag = request.env['chemical.rfid.tag'].sudo()
            result = RfidTag.encode_drum_tag(
                production_id=production_id,
                workcenter_code=workcenter_code,
                quantity=quantity,
                container_spec_id=container_spec_id,
            )
            return result
            
        except Exception as e:
            _logger.error('RFID encode error: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
    
    @http.route(
        '/chemical/rfid_scan',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def rfid_scan(self, tag_id=None, reader_location=None, reader_type='portal', **kwargs):
        """
        Process RFID tag scan for inventory movement.
        
        Called by RFID portal/reader when a drum tag is scanned.
        
        Args:
            tag_id: str - RFID tag ID
            reader_location: str - Reader location code (P3, X-DOCK, etc.)
            reader_type: str - Type of reader (portal, handheld, fixed)
        
        Returns:
            dict: Scan result with automatic transfer details
        """
        if not self._check_authorization():
            return {
                'status': 'error',
                'message': 'Unauthorized: Valid API key or user session required',
            }
        
        if not tag_id or not reader_location:
            return {
                'status': 'error',
                'message': 'tag_id and reader_location are required',
            }
        
        try:
            RfidScan = request.env['chemical.rfid.scan'].sudo()
            result = RfidScan.process_rfid_scan(tag_id, reader_location, reader_type)
            return result
            
        except Exception as e:
            _logger.error('RFID scan error: %s', str(e))
            return {
                'status': 'error',
                'message': str(e),
            }
