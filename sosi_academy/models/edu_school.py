from odoo import models, fields, api


class EduSchool(models.Model):
    _name = 'edu.school'
    _description = 'Educational Institution'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='School Name', required=True, tracking=True)
    contact = fields.Char(string='Contact Person')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    region = fields.Selection([
        ('north', 'North (北部)'),
        ('central', 'Central (中部)'),
        ('south', 'South (南部)'),
        ('east', 'East (東部)'),
    ], string='Region', default='central')
    notes = fields.Text(string='Notes')
    
    project_ids = fields.One2many('edu.project', 'school_id', string='Projects')
    visit_ids = fields.One2many('edu.visit', 'school_id', string='Visits')
    
    project_count = fields.Integer(compute='_compute_project_count', string='Projects')
    visit_count = fields.Integer(compute='_compute_visit_count', string='Visits')

    @api.depends('project_ids')
    def _compute_project_count(self):
        for record in self:
            record.project_count = len(record.project_ids)

    @api.depends('visit_ids')
    def _compute_visit_count(self):
        for record in self:
            record.visit_count = len(record.visit_ids)

    def action_view_projects(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Projects',
            'res_model': 'edu.project',
            'view_mode': 'list,form',
            'domain': [('school_id', '=', self.id)],
            'context': {'default_school_id': self.id},
        }

    def action_view_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Visits',
            'res_model': 'edu.visit',
            'view_mode': 'list,form',
            'domain': [('school_id', '=', self.id)],
            'context': {'default_school_id': self.id},
        }
