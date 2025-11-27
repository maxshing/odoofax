from odoo import models, fields, api


class AIKnowledgeSource(models.Model):
    _name = 'ai.knowledge_source'
    _description = 'AI Knowledge Source'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Source Name', required=True, tracking=True)
    type = fields.Selection([
        ('document', 'Document'),
        ('database', 'Database Table'),
        ('api', 'External API'),
        ('manual', 'Manual Entry'),
        ('web', 'Web Scraping'),
    ], string='Source Type', required=True, tracking=True)
    category = fields.Selection([
        ('product', 'Product Knowledge'),
        ('process', 'Process/SOP'),
        ('customer', 'Customer Info'),
        ('technical', 'Technical Docs'),
        ('regulatory', 'Regulatory/Compliance'),
        ('other', 'Other'),
    ], string='Category')
    
    file = fields.Binary(string='File')
    file_name = fields.Char(string='File Name')
    
    metadata = fields.Text(string='Metadata (JSON)')
    tags = fields.Char(string='Tags')
    
    description = fields.Text(string='Description')
    source_url = fields.Char(string='Source URL')
    
    last_indexed = fields.Datetime(string='Last Indexed')
    index_status = fields.Selection([
        ('pending', 'Pending'),
        ('indexing', 'Indexing'),
        ('indexed', 'Indexed'),
        ('error', 'Error'),
    ], string='Index Status', default='pending')
    
    chunk_count = fields.Integer(string='Chunk Count', readonly=True)
    active = fields.Boolean(default=True)

    def action_start_indexing(self):
        self.ensure_one()
        self.write({
            'index_status': 'indexing',
        })
        return True
