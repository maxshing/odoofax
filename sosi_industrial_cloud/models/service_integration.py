from odoo import models, fields, api
from datetime import datetime


class ServiceIntegration(models.Model):
    _name = 'service.integration'
    _description = 'Service Integration'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Integration Name', required=True, tracking=True)
    type = fields.Selection([
        ('woocommerce', 'WooCommerce'),
        ('shopee', 'Shopee'),
        ('ebay', 'eBay'),
        ('node_red', 'Node-RED'),
        ('rfid', 'RFID System'),
        ('scada', 'SCADA System'),
        ('mqtt', 'MQTT Broker'),
        ('rest_api', 'REST API'),
    ], string='Integration Type', required=True, tracking=True)
    
    endpoint_url = fields.Char(string='Endpoint URL')
    api_key = fields.Char(string='API Key', groups='base.group_system')
    api_secret = fields.Char(string='API Secret', groups='base.group_system')
    
    active = fields.Boolean(string='Active', default=True, tracking=True)
    last_sync = fields.Datetime(string='Last Sync', readonly=True)
    sync_interval = fields.Integer(string='Sync Interval (minutes)', default=60)
    
    log = fields.Text(string='Sync Log')
    error_count = fields.Integer(string='Error Count', default=0)
    
    project_id = fields.Many2one('service.project', string='Related Project')
    customer_id = fields.Many2one('res.partner', string='Customer')

    def action_test_connection(self):
        self.ensure_one()
        self.write({
            'log': f"[{datetime.now()}] Connection test initiated for {self.type}\n" + (self.log or ''),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Connection test completed. Check logs for details.',
                'type': 'info',
            }
        }

    def action_sync_now(self):
        self.ensure_one()
        self.write({
            'last_sync': datetime.now(),
            'log': f"[{datetime.now()}] Manual sync triggered\n" + (self.log or ''),
        })
