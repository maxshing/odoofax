{
    'name': 'SOSI Industrial Cloud',
    'version': '18.0.1.0.0',
    'category': 'Services',
    'summary': 'Factory-level information services and integrations',
    'description': """
SOSI Industrial Cloud - 工廠級資訊服務
======================================

提供中小工廠的雲端資訊服務：
- 服務方案管理
- 系統整合連接（WooCommerce, Shopee, RFID, SCADA, Node-RED）
- 客戶專案追蹤
- API 管理與監控

功能模組：
- 自動化報價
- 自動採購
- RFID 物流
- SCADA 監控
- IoT API
    """,
    'author': 'CROWDFORMOSA INDUSTRIAL CO., LTD.',
    'website': 'https://www.crosa.com.tw',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/service_package_views.xml',
        'views/service_integration_views.xml',
        'views/service_project_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
