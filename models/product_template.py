# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    auto_create_variants = fields.Boolean(
        string='Auto Create All Variants',
        default=True,
        help='If disabled, you need to manually specify which variant combinations to create'
    )
    
    allowed_variant_combination_ids = fields.One2many(
        'product.allowed.variant.combination',
        'product_tmpl_id',
        string='Allowed Variant Combinations'
    )
    
    def write(self, vals):
        """Override write to trigger variant creation when combinations change"""
        
        # Protection: Auto-load existing variants when switching to selective mode
        if 'auto_create_variants' in vals:
            for template in self:
                # If switching from True to False (enabling selective mode)
                if template.auto_create_variants and not vals['auto_create_variants']:
                    # And no combinations are defined yet
                    if not template.allowed_variant_combination_ids:
                        # Auto-load existing variants to prevent accidental deletion
                        template._auto_load_existing_combinations()
        
        res = super().write(vals)
        
        # If allowed combinations changed and auto create is disabled
        if 'allowed_variant_combination_ids' in vals:
            for template in self:
                if not template.auto_create_variants:
                    template._create_selective_variants()
                    # Invalidate cache to update smart button
                    template.invalidate_recordset(['product_variant_ids', 'product_variant_count'])
        
        return res
    
    def _create_variant_ids(self):
        """Override to control variant creation based on allowed combinations"""
        if self.auto_create_variants:
            return super()._create_variant_ids()
        else:
            result = self._create_selective_variants()
            # Invalidate cache to update smart button
            self.invalidate_recordset(['product_variant_ids', 'product_variant_count'])
            return result
    
    def action_update_variants(self):
        """Manual button to update variants"""
        self.ensure_one()
        self._create_selective_variants()
        self.invalidate_recordset(['product_variant_ids', 'product_variant_count'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Variants have been updated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
        
    
    def action_load_existing_variants(self):
        """Load all existing variants into allowed combinations"""
        self.ensure_one()
        
        # Check if product has attributes
        if not self.attribute_line_ids:
            raise ValidationError(_('This product has no attributes configured.'))
        
        # Check if product has existing variants
        if not self.product_variant_ids:
            raise ValidationError(_('This product has no existing variants to load.'))
        
        # Get number of attributes
        num_attributes = len(self.attribute_line_ids)
        
        # Clear existing allowed combinations
        self.allowed_variant_combination_ids.unlink()
        
        # Create allowed combinations from existing variants
        combinations_to_create = []
        for variant in self.product_variant_ids:
            # Only add variants that have complete attribute combinations
            if len(variant.product_template_attribute_value_ids) == num_attributes:
                combinations_to_create.append({
                    'product_tmpl_id': self.id,
                    'value_ids': [(6, 0, variant.product_template_attribute_value_ids.ids)],
                })
        
        # Create the combinations
        if combinations_to_create:
            self.env['product.allowed.variant.combination'].create(combinations_to_create)
        
        return {
            'type': 'ir.actions.client',
            # 'tag': 'display_notification',
            'tag': 'reload',
            # 'params': {
            #     'title': _('Success'),
            #     'message': _('%s variant combinations have been loaded. You can now remove the ones you don\'t need.') % len(combinations_to_create),
            #     'type': 'success',
            #     'sticky': False,
            # }
        }
    
    def _auto_load_existing_combinations(self):
        """Automatically load existing variants when enabling selective mode"""
        self.ensure_one()
        
        if not self.product_variant_ids:
            return
        
        num_attributes = len(self.attribute_line_ids)
        if num_attributes == 0:
            return
        
        combinations_to_create = []
        for variant in self.product_variant_ids:
            if len(variant.product_template_attribute_value_ids) == num_attributes:
                combinations_to_create.append({
                    'product_tmpl_id': self.id,
                    'value_ids': [(6, 0, variant.product_template_attribute_value_ids.ids)],
                })
        
        if combinations_to_create:
            self.env['product.allowed.variant.combination'].create(combinations_to_create)
    
    def _create_selective_variants(self):
        """Create only the variants specified in allowed combinations"""
        self.ensure_one()
        
        Product = self.env['product.product']
        
        # Get the number of attributes
        num_attributes = len(self.attribute_line_ids)
        
        if num_attributes == 0:
            return self.product_variant_ids
        
        # Get existing variants mapped by their attribute value combinations
        existing_variants = {}
        for variant in self.product_variant_ids:
            key = tuple(sorted(variant.product_template_attribute_value_ids.ids))
            existing_variants[key] = variant
        
        # Get allowed combinations
        allowed_keys = set()
        variants_created = False
        
        for allowed_combo in self.allowed_variant_combination_ids:
            if len(allowed_combo.value_ids) == num_attributes:
                key = tuple(sorted(allowed_combo.value_ids.ids))
                allowed_keys.add(key)
                
                # Create variant if it doesn't exist
                if key not in existing_variants:
                    variant = Product.create({
                        'product_tmpl_id': self.id,
                        'product_template_attribute_value_ids': [(6, 0, allowed_combo.value_ids.ids)],
                    })
                    variants_created = True
        
        # Delete variants that are not in allowed combinations
        variants_to_delete = self.env['product.product']
        for key, variant in existing_variants.items():
            if key not in allowed_keys:
                variants_to_delete |= variant
        
        if variants_to_delete:
            variants_to_delete.unlink()
        
        # Force refresh of the variants relationship
        if variants_created or variants_to_delete:
            self.env['product.product'].flush_model()
            self.env['product.template'].flush_model()
        
        return self.product_variant_ids


class ProductAllowedVariantCombination(models.Model):
    _name = 'product.allowed.variant.combination'
    _description = 'Allowed Product Variant Combinations'
    _order = 'name'
    
    product_tmpl_id = fields.Many2one(
        'product.template', 
        string='Product Template',
        required=True, 
        ondelete='cascade',
        index=True
    )
    value_ids = fields.Many2many(
        'product.template.attribute.value',
        relation='product_allowed_combination_value_rel',
        column1='combination_id',
        column2='value_id',
        string='Attribute Values',
        required=True
    )
    name = fields.Char(
        string='Combination Name',
        compute='_compute_name', 
        store=True
    )
    
    @api.depends('value_ids', 'value_ids.name')
    def _compute_name(self):
        """Compute display name from attribute values"""
        for record in self:
            if record.value_ids:
                # Sort by attribute sequence for consistent display
                sorted_values = record.value_ids.sorted(key=lambda v: (v.attribute_id.sequence, v.attribute_id.name))
                record.name = ', '.join(sorted_values.mapped('name'))
            else:
                record.name = ''
    
    @api.constrains('value_ids', 'product_tmpl_id')
    def _check_complete_combination(self):
        """Ensure each combination has values for ALL attributes"""
        for record in self:
            if not record.product_tmpl_id or not record.value_ids:
                continue
                
            # Get number of attributes
            num_attributes = len(record.product_tmpl_id.attribute_line_ids)
            num_values = len(record.value_ids)
            
            # Check if combination is complete
            if num_values != num_attributes:
                attribute_names = ', '.join(record.product_tmpl_id.attribute_line_ids.mapped('attribute_id.name'))
                raise ValidationError(
                    _('Each combination must have exactly one value for each attribute.\n\n'
                      'Product "%s" has %d attributes: %s\n'
                      'Your combination has only %d values.\n\n'
                      'Please select one value from each attribute.') % (
                        record.product_tmpl_id.name,
                        num_attributes,
                        attribute_names,
                        num_values
                    )
                )
            
            # Check that values are from different attributes
            attribute_ids = record.value_ids.mapped('attribute_id')
            unique_attribute_ids = set(attribute_ids.ids)
            
            if len(unique_attribute_ids) != num_values:
                # Find which attribute has multiple values
                from collections import Counter
                attr_counts = Counter(attribute_ids.ids)
                duplicate_attrs = [attr_id for attr_id, count in attr_counts.items() if count > 1]
                duplicate_names = self.env['product.attribute'].browse(duplicate_attrs).mapped('name')
                
                raise ValidationError(
                    _('You cannot select multiple values from the same attribute in one combination.\n\n'
                      'Duplicate attribute(s): %s\n\n'
                      'Please select only ONE value from each attribute.') % (', '.join(duplicate_names))
                )
            
            # Check that all values belong to this product's attributes
            product_attribute_ids = record.product_tmpl_id.attribute_line_ids.mapped('attribute_id').ids
            value_attribute_ids = attribute_ids.ids
            
            invalid_attrs = set(value_attribute_ids) - set(product_attribute_ids)
            if invalid_attrs:
                invalid_names = self.env['product.attribute'].browse(list(invalid_attrs)).mapped('name')
                raise ValidationError(
                    _('Some selected values do not belong to this product\'s attributes.\n\n'
                      'Invalid attribute(s): %s') % (', '.join(invalid_names))
                )
    
    @api.constrains('value_ids', 'product_tmpl_id')
    def _check_duplicate_combination(self):
        """Prevent duplicate combinations for the same product"""
        for record in self:
            if not record.value_ids:
                continue
            
            # Search for other combinations with same values
            value_ids_set = set(record.value_ids.ids)
            
            other_combinations = self.search([
                ('product_tmpl_id', '=', record.product_tmpl_id.id),
                ('id', '!=', record.id)
            ])
            
            for other in other_combinations:
                if set(other.value_ids.ids) == value_ids_set:
                    raise ValidationError(
                        _('This combination already exists for this product.\n\n'
                          'Duplicate: %s') % record.name
                    )
