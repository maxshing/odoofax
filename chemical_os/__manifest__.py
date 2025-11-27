# -*- coding: utf-8 -*-
{
    'name': 'Chemical OS',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Chemicals',
    'summary': 'Chemical Product and Container Management System',
    'description': """
Chemical OS - Advanced Chemical Product Management
===================================================

This module replaces the legacy petrochemical ERP coding system with structured data management.

Key Features:
- Advanced Packaging Management (Container Specifications)
- Container Ledger (Customer Container Accounts)
- Reverse Logistics Workflow (Buyback, Return Loan, Customer Inbound)
- Legacy Code Parsing and Migration

Legacy Code References:
- 9172/9175: Container specifications
- 1002 series: Product codes with simplified packaging

Technical Notes:
- Handles complex container lifecycle management
- Supports three transaction modes: Buyback, Loan Return, Customer Inbound
- Automatic credit note generation for buyback operations
- Dirty drum inventory tracking
    """,
    'author': 'CROWDFORMOSA INDUSTRIAL CO., LTD.',
    'website': 'https://crosa.com.tw',
    'depends': [
        'base',
        'stock',
        'account',
        'contacts',
        'mail',
        'mrp',
        'maintenance',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/stock_location_data.xml',
        'data/equipment_data.xml',
        'data/iot_sensor_data.xml',
        'data/blending_location_data.xml',
        'views/container_spec_views.xml',
        'views/container_ledger_views.xml',
        'views/container_transaction_views.xml',
        'views/tank_content_views.xml',
        'views/tank_history_views.xml',
        'views/iot_point_views.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/gate_log_views.xml',
        'views/rfid_inventory_views.xml',
        'views/partner_views.xml',
        'wizard/drum_return_wizard_views.xml',
        'views/menu.xml',
    ],
    'demo': [
        'data/tank_demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
