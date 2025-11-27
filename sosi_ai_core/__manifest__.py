{
    'name': 'SOSI AI Core',
    'version': '18.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Enterprise AI knowledge management and second brain',
    'description': """
SOSI AI Core - 第二大腦
======================

企業知識管理與 AI 輔助系統：
- 知識來源管理
- AI 問答記錄
- 模型註冊中心

功能特色：
- 整合內部文件與資料庫
- 追蹤 AI 互動歷史
- 管理機器學習模型版本
    """,
    'author': 'CROWDFORMOSA INDUSTRIAL CO., LTD.',
    'website': 'https://www.crosa.com.tw',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_knowledge_source_views.xml',
        'views/ai_question_log_views.xml',
        'views/ai_model_registry_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
