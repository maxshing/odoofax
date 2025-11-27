from odoo import models, fields, api


class OilBatchLog(models.Model):
    _name = 'oil.batch_log'
    _description = 'Oil Production Batch Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc'

    name = fields.Char(string='Batch Reference', compute='_compute_name', store=True)
    batch_no = fields.Char(string='Batch Number', required=True, tracking=True)
    
    product_id = fields.Many2one('product.product', string='Product', required=True, tracking=True)
    tank_id = fields.Many2one('stock.location', string='Tank/Location', 
                               domain="[('usage','=','internal')]")
    
    start_time = fields.Datetime(string='Start Time', required=True, tracking=True)
    end_time = fields.Datetime(string='End Time')
    duration_hours = fields.Float(compute='_compute_duration', string='Duration (hours)', store=True)
    
    operator = fields.Char(string='Operator')
    operator_id = fields.Many2one('res.users', string='Operator User')
    
    scada_log = fields.Text(string='SCADA Log Data')
    
    viscosity = fields.Float(string='Viscosity (cSt)', tracking=True)
    viscosity_temp = fields.Float(string='Viscosity Temp (°C)', default=40.0)
    density = fields.Float(string='Density (g/mL)', tracking=True)
    moisture = fields.Float(string='Moisture (ppm)', tracking=True)
    acid_number = fields.Float(string='Acid Number (mgKOH/g)')
    flash_point = fields.Float(string='Flash Point (°C)')
    
    qc_result = fields.Selection([
        ('pending', 'Pending (待檢)'),
        ('pass', 'Pass (合格)'),
        ('fail', 'Fail (不合格)'),
        ('conditional', 'Conditional (有條件通過)'),
    ], string='QC Result', default='pending', tracking=True)
    
    qc_notes = fields.Text(string='QC Notes')
    notes = fields.Text(string='Production Notes')
    
    quantity_produced = fields.Float(string='Quantity Produced')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    
    iot_log_ids = fields.One2many('iot.data.log', 'related_batch_id', string='IoT Logs')
    iot_log_count = fields.Integer(compute='_compute_iot_log_count', string='IoT Records')

    @api.depends('batch_no', 'product_id')
    def _compute_name(self):
        for record in self:
            if record.batch_no and record.product_id:
                record.name = f"{record.batch_no} - {record.product_id.name}"
            else:
                record.name = record.batch_no or "New Batch"

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration_hours = delta.total_seconds() / 3600
            else:
                record.duration_hours = 0

    @api.depends('iot_log_ids')
    def _compute_iot_log_count(self):
        for record in self:
            record.iot_log_count = len(record.iot_log_ids)

    def action_mark_pass(self):
        self.write({'qc_result': 'pass'})

    def action_mark_fail(self):
        self.write({'qc_result': 'fail'})

    def action_view_iot_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'IoT Logs',
            'res_model': 'iot.data.log',
            'view_mode': 'list,form',
            'domain': [('related_batch_id', '=', self.id)],
            'context': {'default_related_batch_id': self.id},
        }
