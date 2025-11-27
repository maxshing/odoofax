{
    'name': 'SOSI Academy',
    'version': '18.0.1.0.0',
    'category': 'Education',
    'summary': 'Educational partnership and student project management',
    'description': """
SOSI Academy - 教育系統
========================

管理產學合作關係：
- 學校資料管理
- 學生專題追蹤
- 工廠參訪安排
- 教育資料集管理

功能特色：
- 整合 RFID、SCADA、油品分析等專題領域
- 連結產品與教育專案
- 參訪活動記錄與照片管理
    """,
    'author': 'CROWDFORMOSA INDUSTRIAL CO., LTD.',
    'website': 'https://www.crosa.com.tw',
    'license': 'LGPL-3',
    'depends': ['base', 'product', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/edu_school_views.xml',
        'views/edu_project_views.xml',
        'views/edu_visit_views.xml',
        'views/edu_dataset_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
