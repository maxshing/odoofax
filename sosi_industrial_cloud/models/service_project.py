from odoo import models, fields, api


class ServiceProject(models.Model):
    _name = 'service.project'
    _description = 'Service Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Project Name', compute='_compute_name', store=True)
    package_id = fields.Many2one('service.package', string='Service Package', required=True, tracking=True)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    
    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date')
    
    status = fields.Selection([
        ('draft', 'Draft (草稿)'),
        ('active', 'Active (進行中)'),
        ('complete', 'Complete (已完成)'),
        ('cancelled', 'Cancelled (已取消)'),
    ], string='Status', default='draft', tracking=True)
    
    notes = fields.Text(string='Notes')
    
    integration_ids = fields.One2many('service.integration', 'project_id', string='Integrations')
    integration_count = fields.Integer(compute='_compute_integration_count', string='Integrations')
    
    monthly_fee = fields.Float(related='package_id.price_monthly', string='Monthly Fee', readonly=True)
    
    responsible_id = fields.Many2one('res.users', string='Project Manager', 
                                      default=lambda self: self.env.user)

    @api.depends('package_id', 'customer_id')
    def _compute_name(self):
        for record in self:
            if record.package_id and record.customer_id:
                record.name = f"{record.customer_id.name} - {record.package_id.name}"
            else:
                record.name = "New Project"

    @api.depends('integration_ids')
    def _compute_integration_count(self):
        for record in self:
            record.integration_count = len(record.integration_ids)

    def action_view_integrations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Integrations',
            'res_model': 'service.integration',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
