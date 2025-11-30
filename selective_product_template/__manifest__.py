# __manifest__.py
{
    'name': 'Selective Product Variants',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Control which product variants are created',
    'description': """
        Allows selective creation of product variants instead of 
        creating all possible combinations automatically.
    """,
    'author': 'Mo. Sarmout',
    'depends': ['product'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],

}