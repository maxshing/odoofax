from odoo import models, fields, api


class EduDataset(models.Model):
    _name = 'edu.dataset'
    _description = 'Educational Dataset'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Dataset Name', required=True, tracking=True)
    type = fields.Selection([
        ('scada', 'SCADA Data'),
        ('rfid', 'RFID Data'),
        ('lube_qc', 'Lubricant QC (油品品質)'),
        ('mrp_batch', 'MRP Batch Data'),
        ('iot', 'IoT Sensor Data'),
        ('other', 'Other'),
    ], string='Data Type', required=True, tracking=True)
    description = fields.Text(string='Description')
    source_model = fields.Char(string='Source Model', 
                               help='Odoo model name, e.g., stock.move, mrp.production')
    file = fields.Binary(string='Data File')
    file_name = fields.Char(string='File Name')
    tags = fields.Char(string='Tags')
    
    record_count = fields.Integer(string='Record Count')
    date_from = fields.Date(string='Data From')
    date_to = fields.Date(string='Data To')
    
    project_ids = fields.One2many('edu.project', 'dataset_id', string='Used by Projects')
    
    active = fields.Boolean(default=True)
