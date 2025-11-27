from odoo import models, fields, api


class EduProject(models.Model):
    _name = 'edu.project'
    _description = 'Student Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Project Name', required=True, tracking=True)
    school_id = fields.Many2one('edu.school', string='School', required=True, tracking=True)
    students = fields.Text(string='Student List')
    teacher = fields.Char(string='Advisor')
    topic = fields.Selection([
        ('rfid', 'RFID'),
        ('scada', 'SCADA'),
        ('oil_analysis', 'Oil Analysis (油品分析)'),
        ('automation', 'Automation (自動化)'),
        ('ai', 'Artificial Intelligence (AI)'),
        ('iot', 'IoT'),
        ('other', 'Other'),
    ], string='Topic', tracking=True)
    related_product = fields.Many2one('product.template', string='Related Product')
    dataset_id = fields.Many2one('edu.dataset', string='Dataset Used')
    status = fields.Selection([
        ('draft', 'Draft (草稿)'),
        ('ongoing', 'Ongoing (進行中)'),
        ('finished', 'Finished (已完成)'),
    ], string='Status', default='draft', tracking=True)
    result_url = fields.Char(string='Result URL')
    
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    description = fields.Text(string='Description')
    
    @api.model
    def _get_default_company(self):
        return self.env.company

    company_id = fields.Many2one('res.company', string='Company', default=_get_default_company)
