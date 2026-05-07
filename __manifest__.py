{
    "name": "MR WhatsApp Connector",
    "version": "19.0.1.0.0",
    "summary": "Send WhatsApp messages from Odoo via a self-hosted whatsapp-web.js sidecar",
    "description": """
Connects Odoo to a self-hosted Node.js sidecar running whatsapp-web.js so users can
send WhatsApp messages from partner, sales order, invoice, purchase order, and CRM
lead records. Pair the session by scanning a QR code in Settings -> WhatsApp.

Note: this relies on automating WhatsApp Web, which is against WhatsApp's Terms of
Service. Numbers can be banned. Use at your own risk.
    """,
    "author": "Mohamed Reda",
    "website": "https://github.com/",
    "category": "Discuss",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "contacts",
        "sale",
        "account",
        "purchase",
        "crm",
        "stock",
        "portal",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/whatsapp_send_wizard_views.xml",
        "views/whatsapp_message_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/purchase_order_views.xml",
        "views/crm_lead_views.xml",
        "views/menu_views.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mr_whatsapp_connector/static/src/js/qr_widget.js",
            "mr_whatsapp_connector/static/src/xml/qr_widget.xml",
            "mr_whatsapp_connector/static/src/scss/qr_widget.scss",
        ],
    },
    "external_dependencies": {
        "python": ["requests"],
    },
    "application": True,
    "installable": True,
}
