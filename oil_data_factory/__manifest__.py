{
    'name': 'Oil Data Factory',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Oil production batch logging and IoT data management',
    'description': """
Oil Data Factory - 油品數據工廠
==============================

油品生產數據收集與品質管理：
- 批次生產記錄
- SCADA 數據整合
- 品質檢測追蹤
- IoT 設備數據記錄

功能特色：
- 連接 SCADA 系統記錄生產參數
- 自動收集黏度、密度、水分等檢測數據
- 批次 QC 結果追蹤
- IoT 設備標籤管理
    """,
    'author': 'CROWDFORMOSA INDUSTRIAL CO., LTD.',
    'website': 'https://www.crosa.com.tw',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'product', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/oil_batch_log_views.xml',
        'views/iot_data_log_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
