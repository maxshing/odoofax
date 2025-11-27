from odoo import models, fields, api


class EduVisit(models.Model):
    _name = 'edu.visit'
    _description = 'Factory Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Visit Reference', compute='_compute_name', store=True)
    school_id = fields.Many2one('edu.school', string='School', required=True, tracking=True)
    date = fields.Date(string='Visit Date', required=True, tracking=True)
    student_count = fields.Integer(string='Number of Students')
    activities = fields.Text(string='Activities')
    photos = fields.Many2many('ir.attachment', string='Photos')
    remark = fields.Text(string='Remarks')
    
    responsible_id = fields.Many2one('res.users', string='Responsible Person', 
                                      default=lambda self: self.env.user)
    state = fields.Selection([
        ('planned', 'Planned (計劃中)'),
        ('confirmed', 'Confirmed (已確認)'),
        ('done', 'Done (已完成)'),
        ('cancelled', 'Cancelled (已取消)'),
    ], string='Status', default='planned', tracking=True)

    @api.depends('school_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.school_id and record.date:
                record.name = f"{record.school_id.name} - {record.date}"
            else:
                record.name = "New Visit"

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
