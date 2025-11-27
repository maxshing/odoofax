from odoo import models, fields, api


class AIModelRegistry(models.Model):
    _name = 'ai.model_registry'
    _description = 'AI Model Registry'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Model Name', required=True, tracking=True)
    version = fields.Char(string='Version', required=True)
    
    description = fields.Text(string='Description')
    
    model_type = fields.Selection([
        ('embedding', 'Embedding Model'),
        ('llm', 'Large Language Model'),
        ('classification', 'Classification'),
        ('regression', 'Regression'),
        ('custom', 'Custom Model'),
    ], string='Model Type', tracking=True)
    
    dataset_id = fields.Many2one('edu.dataset', string='Training Dataset')
    
    metrics = fields.Text(string='Performance Metrics (JSON)')
    
    file = fields.Binary(string='Model File')
    file_name = fields.Char(string='File Name')
    file_size = fields.Float(string='File Size (MB)')
    
    usage = fields.Text(string='Usage Notes')
    
    status = fields.Selection([
        ('development', 'Development'),
        ('testing', 'Testing'),
        ('production', 'Production'),
        ('deprecated', 'Deprecated'),
    ], string='Status', default='development', tracking=True)
    
    api_endpoint = fields.Char(string='API Endpoint')
    
    created_date = fields.Date(string='Created Date', default=fields.Date.today)
    last_used = fields.Datetime(string='Last Used')
    usage_count = fields.Integer(string='Usage Count', default=0)
    
    active = fields.Boolean(default=True)

    def action_deploy(self):
        self.write({'status': 'production'})
        
    def action_deprecate(self):
        self.write({'status': 'deprecated', 'active': False})
