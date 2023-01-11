# -*- coding: utf-8 -*-
{
    "name" : "Modificacion manual del tipo de cambio en facturas, ventas y compras.",
    "version" : "13.0.0.10",
    "depends" : ['base','account','purchase','sale_management','stock'],
    "author": "DEVMAN",
    "summary": "Aplicar modificaicon manual del tipo de cambio en facturas, ventas y compras.",
    "description": """
    
    """,
    'category': 'Accounting',
    "website" : "https://www.devman.com.ar",
    "data" :[
             "views/customer_invoice.xml",
             "views/account_payment_view.xml",
             "views/purchase_view.xml",
             "views/sale_view.xml",
    ],
    'qweb':[
    ],
    "auto_install": False,
    "installable": True,
	#"images":['static/description/icono.png'],
}
