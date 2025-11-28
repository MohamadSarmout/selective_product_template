# models/product_template_attribute_value.py
from odoo import models, api

class ProductTemplateAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to prevent automatic variant creation if disabled"""
        records = super().create(vals_list)
        
        # Check each product template
        for record in records:
            product_tmpl = record.product_tmpl_id
            if not product_tmpl.auto_create_variants:
                # Don't trigger automatic variant creation
                # User must manually add allowed combinations
                continue
        
        return records