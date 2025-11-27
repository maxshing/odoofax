from odoo import models, fields, api


class IotDataLog(models.Model):
    _name = 'iot.data.log'
    _description = 'IoT Data Log'
    _order = 'timestamp desc'

    name = fields.Char(string='Log Reference', compute='_compute_name', store=True)
    
    device_id = fields.Char(string='Device ID', required=True, index=True)
    device_name = fields.Char(string='Device Name')
    
    tag_type = fields.Selection([
        ('temperature', 'Temperature (溫度)'),
        ('pressure', 'Pressure (壓力)'),
        ('flow', 'Flow Rate (流量)'),
        ('level', 'Tank Level (液位)'),
        ('viscosity', 'Viscosity (黏度)'),
        ('density', 'Density (密度)'),
        ('humidity', 'Humidity (濕度)'),
        ('rfid', 'RFID Tag'),
        ('weight', 'Weight (重量)'),
        ('other', 'Other'),
    ], string='Tag Type', required=True)
    
    value = fields.Float(string='Value')
    value_string = fields.Char(string='Value (String)')
    unit = fields.Char(string='Unit')
    
    timestamp = fields.Datetime(string='Timestamp', required=True, 
                                 default=fields.Datetime.now, index=True)
    
    related_batch_id = fields.Many2one('oil.batch_log', string='Related Batch', index=True)
    
    location_id = fields.Many2one('stock.location', string='Location')
    
    quality = fields.Selection([
        ('good', 'Good'),
        ('uncertain', 'Uncertain'),
        ('bad', 'Bad'),
    ], string='Data Quality', default='good')
    
    raw_data = fields.Text(string='Raw Data (JSON)')
    
    processed = fields.Boolean(string='Processed', default=False)
    process_notes = fields.Text(string='Process Notes')

    @api.depends('device_id', 'tag_type', 'timestamp')
    def _compute_name(self):
        for record in self:
            ts = record.timestamp.strftime('%Y-%m-%d %H:%M') if record.timestamp else ''
            record.name = f"{record.device_id} / {record.tag_type} / {ts}"

    @api.model
    def create_from_mqtt(self, device_id, tag_type, value, timestamp=None):
        """Helper method to create IoT log from MQTT message"""
        vals = {
            'device_id': device_id,
            'tag_type': tag_type,
            'value': float(value) if isinstance(value, (int, float, str)) else 0,
            'timestamp': timestamp or fields.Datetime.now(),
        }
        return self.create(vals)
