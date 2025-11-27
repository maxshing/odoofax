# -*- coding: utf-8 -*-
"""
MRP BOM Extension for Chemical OS Automated Blending Module

Extends the Bill of Materials to support:
- Tank source selection for each ingredient line
- Dosing tolerance for PLC accuracy control
- PLC recipe synchronization for automated dispensing
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging

_logger = logging.getLogger(__name__)


class MrpBomLineExtension(models.Model):
    """
    Extended BOM Line for Chemical Blending.
    
    Adds tank source and dosing tolerance for PLC-controlled dispensing.
    """
    _inherit = 'mrp.bom.line'
    
    tank_source_id = fields.Many2one(
        'stock.location',
        string='Source Tank',
        domain="[('is_tank', '=', True)]",
        help='Specific tank location to draw this ingredient from (e.g., D1 for Base Oil A).',
    )
    
    dosing_tolerance = fields.Float(
        string='Dosing Tolerance (%)',
        default=0.5,
        help='Acceptable variance percentage for PLC dosing (e.g., 0.5% means ±0.5% of target quantity).',
    )
    
    tank_product_id = fields.Many2one(
        'product.product',
        string='Tank Product',
        related='tank_source_id.current_product_id',
        readonly=True,
        help='Current product stored in the selected tank.',
    )
    
    tank_available_qty = fields.Float(
        string='Tank Available',
        related='tank_source_id.current_quantity',
        readonly=True,
        help='Current quantity available in the selected tank.',
    )
    
    @api.constrains('dosing_tolerance')
    def _check_dosing_tolerance(self):
        """Ensure dosing tolerance is within reasonable bounds."""
        for line in self:
            if line.dosing_tolerance < 0 or line.dosing_tolerance > 10:
                raise ValidationError(_(
                    'Dosing tolerance must be between 0%% and 10%%. '
                    'Current value: %.2f%%'
                ) % line.dosing_tolerance)
    
    @api.onchange('tank_source_id')
    def _onchange_tank_source(self):
        """Warn if tank product doesn't match BOM line product."""
        if self.tank_source_id and self.product_id:
            tank_product = self.tank_source_id.current_product_id
            if tank_product and tank_product != self.product_id:
                return {
                    'warning': {
                        'title': _('Product Mismatch'),
                        'message': _(
                            'Tank %s contains %s, but this BOM line requires %s. '
                            'Please verify the tank selection.'
                        ) % (
                            self.tank_source_id.name,
                            tank_product.name,
                            self.product_id.name
                        )
                    }
                }


class MrpBomExtension(models.Model):
    """
    Extended BOM for Chemical Blending with PLC Integration.
    """
    _inherit = 'mrp.bom'
    
    is_blending_recipe = fields.Boolean(
        string='Is Blending Recipe',
        default=False,
        help='Indicates this BOM is for automated blending with PLC control.',
    )
    
    mixing_workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Mixing Work Center',
        domain="[('code', 'like', 'm')]",
        help='Default mixing tank work center for this recipe (m1-m5).',
    )
    
    nitrogen_purge_required = fields.Boolean(
        string='Nitrogen Purge Required',
        default=True,
        help='Enable nitrogen purging (通氮除水) during mixing process.',
    )
    
    nitrogen_purge_duration = fields.Integer(
        string='Purge Duration (min)',
        default=30,
        help='Default nitrogen purge duration in minutes.',
    )
    
    stirring_speed = fields.Integer(
        string='Stirring Speed (RPM)',
        default=60,
        help='Default stirring speed for mixing tanks.',
    )
    
    stirring_duration = fields.Integer(
        string='Stirring Duration (min)',
        default=45,
        help='Default stirring duration in minutes.',
    )
    
    moisture_spec_max = fields.Float(
        string='Max Moisture (ppm)',
        default=200.0,
        help='Maximum allowable moisture content in ppm for QC Check A.',
    )
    
    viscosity_spec_min = fields.Float(
        string='Min Viscosity (cSt)',
        default=0.0,
        help='Minimum viscosity specification at 40°C.',
    )
    
    viscosity_spec_max = fields.Float(
        string='Max Viscosity (cSt)',
        default=999.0,
        help='Maximum viscosity specification at 40°C.',
    )
    
    particle_spec_max = fields.Float(
        string='Max Particle Size (NAS)',
        default=8.0,
        help='Maximum NAS class for particle contamination (QC Check B).',
    )


class MrpProductionExtension(models.Model):
    """
    Extended Manufacturing Order for Automated Blending.
    """
    _inherit = 'mrp.production'
    
    is_blending_order = fields.Boolean(
        string='Is Blending Order',
        related='bom_id.is_blending_recipe',
        store=True,
    )
    
    plc_recipe_sent = fields.Boolean(
        string='Recipe Sent to PLC',
        default=False,
        help='Indicates the recipe has been transmitted to the PLC.',
    )
    
    plc_recipe_payload = fields.Text(
        string='PLC Recipe Payload',
        readonly=True,
        help='JSON payload sent to the PLC system.',
    )
    
    plc_sent_time = fields.Datetime(
        string='PLC Sent Time',
        readonly=True,
    )
    
    nitrogen_purge_triggered = fields.Boolean(
        string='Nitrogen Purge Triggered',
        default=False,
    )
    
    nitrogen_purge_count = fields.Integer(
        string='Purge Cycles',
        default=0,
        help='Number of nitrogen purge cycles performed.',
    )
    
    qc_check_a_passed = fields.Boolean(
        string='QC Check A Passed',
        default=False,
        help='Post-mixing quality check (Moisture & Viscosity) passed.',
    )
    
    qc_check_b_passed = fields.Boolean(
        string='QC Check B Passed',
        default=False,
        help='Post-filtration quality check (Particle Size) passed.',
    )
    
    transfer_picking_id = fields.Many2one(
        'stock.picking',
        string='Transfer to Filling',
        readonly=True,
        help='Internal transfer from mixing to filling line.',
    )
    
    def action_send_recipe_to_plc(self):
        """
        Generate and send recipe data to PLC for automated blending.
        
        Creates a JSON payload containing:
        - Recipe identification
        - Ingredient list with source tanks and quantities
        - Dosing tolerances
        - Process parameters (stirring, nitrogen purge)
        - Quality specifications
        
        Returns:
            dict: Action to display the generated payload
        """
        self.ensure_one()
        
        if not self.bom_id:
            raise UserError(_('No Bill of Materials defined for this production order.'))
        
        if not self.bom_id.is_blending_recipe:
            raise UserError(_('This BOM is not configured as a blending recipe.'))
        
        ingredient_lines = []
        for line in self.bom_id.bom_line_ids:
            if not line.tank_source_id:
                raise UserError(_(
                    'BOM line for product "%s" is missing a source tank. '
                    'All ingredients must have a tank source for PLC dosing.'
                ) % line.product_id.name)
            
            target_qty = line.product_qty * (self.product_qty / self.bom_id.product_qty)
            
            ingredient_lines.append({
                'sequence': line.sequence,
                'product_code': line.product_id.default_code or line.product_id.name,
                'product_name': line.product_id.name,
                'source_tank': line.tank_source_id.barcode or line.tank_source_id.name,
                'source_tank_id': line.tank_source_id.id,
                'target_qty_liters': round(target_qty, 2),
                'tolerance_pct': line.dosing_tolerance,
                'tolerance_min': round(target_qty * (1 - line.dosing_tolerance / 100), 2),
                'tolerance_max': round(target_qty * (1 + line.dosing_tolerance / 100), 2),
                'uom': line.product_uom_id.name,
            })
        
        payload = {
            'header': {
                'recipe_id': self.id,
                'recipe_name': self.name,
                'bom_reference': self.bom_id.code or self.bom_id.display_name,
                'product_code': self.product_id.default_code or '',
                'product_name': self.product_id.name,
                'batch_qty': self.product_qty,
                'batch_uom': self.product_uom_id.name,
                'timestamp': fields.Datetime.now().isoformat(),
            },
            'workcenter': {
                'mixing_tank': self.bom_id.mixing_workcenter_id.code if self.bom_id.mixing_workcenter_id else 'm1',
                'workcenter_id': self.bom_id.mixing_workcenter_id.id if self.bom_id.mixing_workcenter_id else False,
            },
            'ingredients': ingredient_lines,
            'process_params': {
                'stirring_speed_rpm': self.bom_id.stirring_speed,
                'stirring_duration_min': self.bom_id.stirring_duration,
                'nitrogen_purge_required': self.bom_id.nitrogen_purge_required,
                'nitrogen_purge_duration_min': self.bom_id.nitrogen_purge_duration,
            },
            'quality_specs': {
                'moisture_max_ppm': self.bom_id.moisture_spec_max,
                'viscosity_min_cst': self.bom_id.viscosity_spec_min,
                'viscosity_max_cst': self.bom_id.viscosity_spec_max,
                'particle_max_nas': self.bom_id.particle_spec_max,
            },
            'commands': {
                'start_dosing': True,
                'auto_nitrogen_purge': self.bom_id.nitrogen_purge_required,
                'auto_stirring': True,
            }
        }
        
        payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
        
        self.write({
            'plc_recipe_sent': True,
            'plc_recipe_payload': payload_json,
            'plc_sent_time': fields.Datetime.now(),
        })
        
        _logger.info(
            'PLC Recipe sent for MO %s: %d ingredients, target qty: %.2f',
            self.name, len(ingredient_lines), self.product_qty
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('PLC Recipe Payload'),
            'res_model': 'mrp.production',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'show_plc_payload': True},
        }
    
    def action_trigger_nitrogen_purge(self):
        """
        Trigger additional nitrogen purge cycle.
        
        Called when moisture content exceeds specification during QC Check A.
        """
        self.ensure_one()
        
        self.write({
            'nitrogen_purge_triggered': True,
            'nitrogen_purge_count': self.nitrogen_purge_count + 1,
        })
        
        purge_command = {
            'command': 'NITROGEN_PURGE',
            'mo_id': self.id,
            'mo_name': self.name,
            'duration_min': self.bom_id.nitrogen_purge_duration if self.bom_id else 30,
            'cycle_number': self.nitrogen_purge_count,
            'reason': 'HIGH_MOISTURE_DETECTED',
            'timestamp': fields.Datetime.now().isoformat(),
        }
        
        _logger.info(
            'Nitrogen purge triggered for MO %s (Cycle #%d): %s',
            self.name, self.nitrogen_purge_count, json.dumps(purge_command)
        )
        
        self.message_post(
            body=_(
                'Nitrogen purge cycle #%d triggered due to high moisture content. '
                'Duration: %d minutes.'
            ) % (self.nitrogen_purge_count, purge_command['duration_min']),
            message_type='notification',
        )
        
        return purge_command
    
    def action_record_qc_check_a(self, moisture_ppm, viscosity_cst):
        """
        Record QC Check A results (Post-Mixing: Moisture & Viscosity).
        
        Args:
            moisture_ppm: Measured moisture content in ppm
            viscosity_cst: Measured viscosity in cSt at 40°C
        
        Returns:
            dict: Result containing pass/fail status and any triggered actions
        """
        self.ensure_one()
        
        result = {
            'mo_id': self.id,
            'mo_name': self.name,
            'check_type': 'QC_CHECK_A',
            'moisture_ppm': moisture_ppm,
            'viscosity_cst': viscosity_cst,
            'passed': False,
            'actions_triggered': [],
        }
        
        bom = self.bom_id
        if not bom:
            result['error'] = 'No BOM defined'
            return result
        
        moisture_ok = moisture_ppm <= bom.moisture_spec_max
        viscosity_ok = (bom.viscosity_spec_min <= viscosity_cst <= bom.viscosity_spec_max)
        
        result['moisture_ok'] = moisture_ok
        result['viscosity_ok'] = viscosity_ok
        result['moisture_spec'] = f'≤ {bom.moisture_spec_max} ppm'
        result['viscosity_spec'] = f'{bom.viscosity_spec_min} - {bom.viscosity_spec_max} cSt'
        
        if not moisture_ok:
            purge_result = self.action_trigger_nitrogen_purge()
            result['actions_triggered'].append({
                'action': 'NITROGEN_PURGE',
                'cycle': self.nitrogen_purge_count,
            })
        
        if moisture_ok and viscosity_ok:
            self.qc_check_a_passed = True
            result['passed'] = True
            
            self.message_post(
                body=_(
                    'QC Check A PASSED\n'
                    'Moisture: %.1f ppm (Spec: %s)\n'
                    'Viscosity: %.2f cSt (Spec: %s)'
                ) % (moisture_ppm, result['moisture_spec'], viscosity_cst, result['viscosity_spec']),
                message_type='notification',
            )
        else:
            self.message_post(
                body=_(
                    'QC Check A PENDING\n'
                    'Moisture: %.1f ppm %s (Spec: %s)\n'
                    'Viscosity: %.2f cSt %s (Spec: %s)'
                ) % (
                    moisture_ppm, '✓' if moisture_ok else '✗', result['moisture_spec'],
                    viscosity_cst, '✓' if viscosity_ok else '✗', result['viscosity_spec']
                ),
                message_type='notification',
            )
        
        return result
    
    def action_record_qc_check_b(self, particle_size_nas):
        """
        Record QC Check B results (Post-Filtration: Particle Size).
        
        If passed, automatically triggers transfer to filling line.
        
        Args:
            particle_size_nas: Measured NAS class
        
        Returns:
            dict: Result containing pass/fail status and transfer details
        """
        self.ensure_one()
        
        result = {
            'mo_id': self.id,
            'mo_name': self.name,
            'check_type': 'QC_CHECK_B',
            'particle_size_nas': particle_size_nas,
            'passed': False,
            'transfer_created': False,
        }
        
        bom = self.bom_id
        if not bom:
            result['error'] = 'No BOM defined'
            return result
        
        if not self.qc_check_a_passed:
            result['error'] = 'QC Check A must pass before Check B'
            self.message_post(
                body=_('QC Check B BLOCKED: QC Check A has not passed yet.'),
                message_type='notification',
            )
            return result
        
        particle_ok = particle_size_nas <= bom.particle_spec_max
        result['particle_ok'] = particle_ok
        result['particle_spec'] = f'≤ NAS {bom.particle_spec_max}'
        
        if particle_ok:
            self.qc_check_b_passed = True
            result['passed'] = True
            
            transfer_result = self.trigger_transfer_to_filling()
            if transfer_result.get('picking_id'):
                result['transfer_created'] = True
                result['transfer_picking_id'] = transfer_result.get('picking_id')
                result['transfer_name'] = transfer_result.get('picking_name')
            else:
                result['transfer_error'] = transfer_result.get('error', 'Unknown error')
            
            self.message_post(
                body=_(
                    'QC Check B PASSED\n'
                    'Particle Size: NAS %.1f (Spec: %s)\n'
                    'Transfer to filling line initiated: %s'
                ) % (particle_size_nas, result['particle_spec'], result.get('transfer_name', 'N/A')),
                message_type='notification',
            )
        else:
            self.message_post(
                body=_(
                    'QC Check B FAILED\n'
                    'Particle Size: NAS %.1f (Spec: %s)\n'
                    'Product requires additional filtration.'
                ) % (particle_size_nas, result['particle_spec']),
                message_type='notification',
            )
        
        return result
    
    def trigger_transfer_to_filling(self):
        """
        Create internal transfer from Factory Y mixing outlet to Factory X filling line.
        
        This is called automatically when QC Check B (Particle Size) passes.
        Creates a stock.picking to move bulk liquid from WH/Y/Mixing_Outlet 
        to WH/X/Line_F3_Input.
        
        Returns:
            dict: Transfer details including picking ID and name
        """
        self.ensure_one()
        
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
        Location = self.env['stock.location']
        
        source_location = Location.search([
            '|',
            ('barcode', '=', 'WH/Y/Mixing_Outlet'),
            ('name', 'ilike', 'Mixing Outlet'),
        ], limit=1)
        
        if not source_location:
            source_location = Location.search([
                ('barcode', 'like', 'WH/Y'),
                ('usage', '=', 'internal'),
            ], limit=1)
        
        dest_location = Location.search([
            '|',
            ('barcode', '=', 'WH/X/Line_F3_Input'),
            ('name', 'ilike', 'F3 Input'),
        ], limit=1)
        
        if not dest_location:
            dest_location = Location.search([
                ('barcode', 'like', 'WH/X'),
                ('usage', '=', 'internal'),
            ], limit=1)
        
        if not source_location or not dest_location:
            _logger.warning(
                'Transfer locations not found for MO %s. Source: %s, Dest: %s',
                self.name, source_location, dest_location
            )
            return {'error': 'Transfer locations not configured'}
        
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.code', 'in', ['WH', 'Y', 'WH/Y']),
        ], limit=1)
        
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
            ], limit=1)
        
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'origin': f'{self.name} - Transfer to Filling',
            'note': _(
                'Automated transfer from Blending Module.\n'
                'QC Check B passed - Product released for filling.\n'
                'Source: Factory Y Mixing\n'
                'Destination: Factory X Line F3'
            ),
            'move_type': 'direct',
        }
        
        picking = StockPicking.create(picking_vals)
        
        move_vals = {
            'name': f'{self.product_id.name} - {self.name}',
            'product_id': self.product_id.id,
            'product_uom_qty': self.product_qty,
            'product_uom': self.product_uom_id.id,
            'picking_id': picking.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'production_id': self.id,
        }
        
        move = StockMove.create(move_vals)
        
        picking.action_confirm()
        picking.action_assign()
        
        self.transfer_picking_id = picking.id
        
        _logger.info(
            'Transfer created for MO %s: Picking %s, Qty: %.2f %s',
            self.name, picking.name, self.product_qty, self.product_uom_id.name
        )
        
        return {
            'picking_id': picking.id,
            'picking_name': picking.name,
            'source': source_location.name,
            'destination': dest_location.name,
            'quantity': self.product_qty,
        }
