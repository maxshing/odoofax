from odoo import models, fields, api


class AIQuestionLog(models.Model):
    _name = 'ai.question_log'
    _description = 'AI Question Log'
    _order = 'timestamp desc'

    question = fields.Text(string='Question', required=True)
    answer = fields.Text(string='Answer')
    
    category = fields.Selection([
        ('product', 'Product Inquiry'),
        ('process', 'Process Question'),
        ('customer', 'Customer Related'),
        ('technical', 'Technical Support'),
        ('general', 'General'),
    ], string='Category')
    
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    
    related_model = fields.Char(string='Related Model')
    related_record_id = fields.Integer(string='Related Record ID')
    
    tags = fields.Char(string='Tags')
    
    confidence_score = fields.Float(string='Confidence Score')
    tokens_used = fields.Integer(string='Tokens Used')
    response_time_ms = fields.Integer(string='Response Time (ms)')
    
    feedback = fields.Selection([
        ('helpful', 'Helpful'),
        ('not_helpful', 'Not Helpful'),
        ('incorrect', 'Incorrect'),
    ], string='User Feedback')
    feedback_note = fields.Text(string='Feedback Note')

    source_ids = fields.Many2many('ai.knowledge_source', string='Sources Used')
