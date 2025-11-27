from odoo import models, fields, api


class ServicePackage(models.Model):
    _name = 'service.package'
    _description = 'Service Package'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Package Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    
    module_auto_quote = fields.Boolean(string='Auto Quotation (自動化報價)')
    module_auto_purchase = fields.Boolean(string='Auto Purchase (自動採購)')
    module_rfid = fields.Boolean(string='RFID Logistics (RFID物流)')
    module_scada = fields.Boolean(string='SCADA Monitoring (SCADA監控)')
    module_iot_api = fields.Boolean(string='IoT API')
    
    price_monthly = fields.Float(string='Monthly Price (TWD)', tracking=True)
    implementation_days = fields.Integer(string='Implementation Days')
    
    target_customer = fields.Selection([
        ('small_factory', 'Small/Medium Factory (中小工廠)'),
        ('chemical', 'Chemical Plant (化工廠)'),
        ('warehouse', 'Warehouse/Logistics (倉儲業)'),
        ('manufacturing', 'Manufacturing (製造業)'),
    ], string='Target Customer')
    
    project_ids = fields.One2many('service.project', 'package_id', string='Projects')
    project_count = fields.Integer(compute='_compute_project_count', string='Projects')
    
    active = fields.Boolean(default=True)

    @api.depends('project_ids')
    def _compute_project_count(self):
        for record in self:
            record.project_count = len(record.project_ids)
    
    def get_included_modules(self):
        modules = []
        if self.module_auto_quote:
            modules.append('Auto Quotation')
        if self.module_auto_purchase:
            modules.append('Auto Purchase')
        if self.module_rfid:
            modules.append('RFID Logistics')
        if self.module_scada:
            modules.append('SCADA Monitoring')
        if self.module_iot_api:
            modules.append('IoT API')
        return ', '.join(modules)

    def action_view_projects(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Projects',
            'res_model': 'service.project',
            'view_mode': 'list,form',
            'domain': [('package_id', '=', self.id)],
            'context': {'default_package_id': self.id},
        }
