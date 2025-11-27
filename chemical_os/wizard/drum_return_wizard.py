# -*- coding: utf-8 -*-
"""
Drum Return Wizard
==================

Handles the complex reverse logistics workflow when a customer returns drums.

Three Return Modes:
    Mode A - Buyback (原裝桶購回):
        - Inventory: Drums go to "Warehouse/Dirty_Drums" location
        - Accounting: Creates draft Customer Credit Note for buyback price
        
    Mode B - Return Loan (歸還借桶):
        - Inventory: Drums go to "Warehouse/Dirty_Drums" location
        - Ledger: Decreases balance_loaned in container ledger
        
    Mode C - Customer Inbound (自備桶進廠):
        - Inventory: No value change (customer-owned)
        - Ledger: Increases balance_customer_owned

Business Logic:
    - Returned drums are never immediately available for reuse
    - All returned drums must go through cleaning/inspection first
    - Financial transactions are created as drafts for review
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class DrumReturnWizard(models.TransientModel):
    _name = 'chemical.drum.return.wizard'
    _description = 'Process Drum Return'
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        domain="[('customer_rank', '>', 0)]",
    )
    
    container_spec_id = fields.Many2one(
        'chemical.container.spec',
        string='Container Specification',
        required=True,
        domain="[('is_returnable', '=', True)]",
    )
    
    quantity = fields.Integer(
        string='Quantity',
        required=True,
        default=1,
    )
    
    return_mode = fields.Selection(
        selection=[
            ('buyback', 'Mode A: Buyback (原裝桶購回)'),
            ('return_loan', 'Mode B: Return Loan (歸還借桶)'),
            ('customer_inbound', 'Mode C: Customer Inbound (自備桶進廠)'),
        ],
        string='Return Mode',
        required=True,
        default='return_loan',
        help="""
        Mode A - Buyback: We buy back the drums and issue credit note.
        Mode B - Return Loan: Customer returns drums we previously lent.
        Mode C - Customer Inbound: Customer's own drums arriving for refill.
        """,
    )
    
    # Computed fields for preview
    current_loaned = fields.Integer(
        string='Current Loaned Balance',
        compute='_compute_current_balances',
    )
    
    current_customer_owned = fields.Integer(
        string='Current Customer Owned',
        compute='_compute_current_balances',
    )
    
    buyback_unit_price = fields.Float(
        string='Buyback Price per Unit',
        related='container_spec_id.buyback_price',
    )
    
    total_buyback_amount = fields.Float(
        string='Total Buyback Amount',
        compute='_compute_total_buyback',
    )
    
    notes = fields.Text(string='Notes')
    
    @api.depends('partner_id', 'container_spec_id')
    def _compute_current_balances(self):
        Ledger = self.env['chemical.container.ledger']
        for wizard in self:
            if wizard.partner_id and wizard.container_spec_id:
                ledger = Ledger.search([
                    ('partner_id', '=', wizard.partner_id.id),
                    ('container_spec_id', '=', wizard.container_spec_id.id),
                ], limit=1)
                wizard.current_loaned = ledger.balance_loaned if ledger else 0
                wizard.current_customer_owned = ledger.balance_customer_owned if ledger else 0
            else:
                wizard.current_loaned = 0
                wizard.current_customer_owned = 0
    
    @api.depends('quantity', 'buyback_unit_price')
    def _compute_total_buyback(self):
        for wizard in self:
            wizard.total_buyback_amount = wizard.quantity * (wizard.buyback_unit_price or 0.0)
    
    @api.constrains('quantity')
    def _check_quantity(self):
        for wizard in self:
            if wizard.quantity <= 0:
                raise ValidationError(_('Quantity must be greater than zero.'))
    
    @api.constrains('return_mode', 'quantity', 'current_loaned')
    def _check_return_loan_balance(self):
        """Ensure we don't return more loaned drums than currently outstanding."""
        for wizard in self:
            if wizard.return_mode == 'return_loan':
                if wizard.quantity > wizard.current_loaned:
                    raise ValidationError(
                        _('Cannot return %d drums. Only %d drums are currently loaned to this customer.') 
                        % (wizard.quantity, wizard.current_loaned)
                    )
    
    def action_process_return(self):
        """
        Main processing method - routes to appropriate handler based on return mode.
        
        This is the entry point called when user clicks "Process Return" button.
        """
        self.ensure_one()
        
        # Validate inputs
        if not self.partner_id or not self.container_spec_id or not self.quantity:
            raise UserError(_('Please fill in all required fields.'))
        
        # Route to appropriate handler
        if self.return_mode == 'buyback':
            return self._process_buyback()
        elif self.return_mode == 'return_loan':
            return self._process_return_loan()
        elif self.return_mode == 'customer_inbound':
            return self._process_customer_inbound()
        else:
            raise UserError(_('Invalid return mode selected.'))
    
    def _process_buyback(self):
        """
        Mode A: Buyback (原裝桶購回)
        
        Actions:
            1. Create stock move to "Warehouse/Dirty_Drums" location
            2. Create draft Customer Credit Note (Invoice Allowance)
            3. Create transaction record in container ledger
        """
        self.ensure_one()
        
        # Get or create ledger
        Ledger = self.env['chemical.container.ledger']
        Transaction = self.env['chemical.container.transaction']
        ledger = Ledger.get_or_create_ledger(
            self.partner_id.id, 
            self.container_spec_id.id
        )
        
        # 1. Create inventory movement to dirty drums location
        move = self._create_dirty_drum_move()
        
        # 2. Create draft credit note for buyback
        credit_note = self._create_buyback_credit_note()
        
        # 3. Create transaction record with audit trail
        transaction = Transaction.create_transaction(
            ledger=ledger,
            transaction_type='buyback',
            quantity=self.quantity,
            direction='inbound',
            unit_price=self.buyback_unit_price,
            credit_note_id=credit_note.id if credit_note else False,
            stock_move_id=move.id if move else False,
            notes=self.notes,
        )
        
        # Log activity
        self.partner_id.message_post(
            body=_('Drum Buyback: %d x %s for %s TWD. Credit Note: %s') % (
                self.quantity,
                self.container_spec_id.name,
                self.total_buyback_amount,
                credit_note.name if credit_note else 'N/A',
            ),
            subject=_('Drum Buyback Processed'),
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Credit Note Created'),
            'res_model': 'account.move',
            'res_id': credit_note.id if credit_note else False,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _process_return_loan(self):
        """
        Mode B: Return Loan (歸還借桶)
        
        Actions:
            1. Create stock move to "Warehouse/Dirty_Drums" location
            2. Decrease balance_loaned in container ledger
            3. Create transaction record in container ledger
        """
        self.ensure_one()
        
        # Get or create ledger
        Ledger = self.env['chemical.container.ledger']
        Transaction = self.env['chemical.container.transaction']
        ledger = Ledger.get_or_create_ledger(
            self.partner_id.id, 
            self.container_spec_id.id
        )
        
        # 1. Create inventory movement
        move = self._create_dirty_drum_move()
        
        # 2. Create transaction record (this also updates ledger balances)
        transaction = Transaction.create_transaction(
            ledger=ledger,
            transaction_type='return_loan',
            quantity=self.quantity,
            direction='inbound',
            stock_move_id=move.id if move else False,
            notes=self.notes,
        )
        
        # Log activity
        self.partner_id.message_post(
            body=_('Loan Return: %d x %s. New loaned balance: %d') % (
                self.quantity,
                self.container_spec_id.name,
                ledger.balance_loaned,
            ),
            subject=_('Drum Loan Return Processed'),
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Return Processed'),
                'message': _('%d drums returned. Loaned balance updated.') % self.quantity,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    
    def _process_customer_inbound(self):
        """
        Mode C: Customer Inbound (自備桶進廠)
        
        Actions:
            1. No inventory value change (customer-owned property)
            2. Increase balance_customer_owned in ledger
            3. Create transaction record in container ledger
        """
        self.ensure_one()
        
        # Get or create ledger
        Ledger = self.env['chemical.container.ledger']
        Transaction = self.env['chemical.container.transaction']
        ledger = Ledger.get_or_create_ledger(
            self.partner_id.id, 
            self.container_spec_id.id
        )
        
        # Create transaction record (this also updates ledger balances)
        transaction = Transaction.create_transaction(
            ledger=ledger,
            transaction_type='customer_inbound',
            quantity=self.quantity,
            direction='inbound',
            notes=self.notes,
        )
        
        # Log activity
        self.partner_id.message_post(
            body=_('Customer Drums Inbound: %d x %s. Customer owned balance: %d') % (
                self.quantity,
                self.container_spec_id.name,
                ledger.balance_customer_owned,
            ),
            subject=_('Customer Drums Received'),
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Drums Received'),
                'message': _('%d customer drums received and logged.') % self.quantity,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    
    def _create_dirty_drum_move(self):
        """
        Create stock movement for returned drums to dirty drum location.
        
        Note: This creates a simplified stock move. In production, you may need
        to configure proper source/destination locations in Odoo inventory settings.
        """
        StockMove = self.env.get('stock.move')
        if not StockMove:
            # Stock module not installed, skip inventory move
            return False
        
        # Get or create dirty drums location
        dirty_location = self._get_dirty_drums_location()
        
        # Get source location (partner/customer location)
        partner_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        
        if not dirty_location or not partner_location:
            # Locations not configured, log warning and skip
            return False
        
        # Find or create a dummy product for container tracking
        container_product = self._get_container_product()
        
        move_vals = {
            'name': _('Drum Return: %s') % self.container_spec_id.name,
            'product_id': container_product.id if container_product else False,
            'product_uom_qty': self.quantity,
            'product_uom': container_product.uom_id.id if container_product else False,
            'location_id': partner_location.id,
            'location_dest_id': dirty_location.id,
            'partner_id': self.partner_id.id,
            'origin': _('Drum Return - %s') % self.partner_id.name,
        }
        
        try:
            move = StockMove.create(move_vals)
            move._action_confirm()
            move._action_assign()
            return move
        except Exception:
            # If stock move fails, continue without it
            return False
    
    def _get_dirty_drums_location(self):
        """
        Get the Dirty Drums inventory location from the predefined XML data.
        
        Location hierarchy (defined in data/stock_location_data.xml):
        - WH/DIRTY (Main collection point)
          - WH/DIRTY/X (Building X)
          - WH/DIRTY/Y (Building Y)
          - WH/DIRTY/Z (Building Z)
        """
        # Try to get the main dirty drums location from XML data
        dirty_location = self.env.ref(
            'chemical_os.location_dirty_drums', 
            raise_if_not_found=False
        )
        
        if dirty_location:
            return dirty_location
        
        # Fallback: Search by barcode
        Location = self.env.get('stock.location')
        if Location:
            dirty_location = Location.search([
                ('barcode', '=', 'WH/DIRTY'),
                ('usage', '=', 'internal'),
            ], limit=1)
            
            if dirty_location:
                return dirty_location
        
        # Last resort: Search by name
        if Location:
            dirty_location = Location.search([
                ('name', '=', 'Dirty Drums'),
                ('usage', '=', 'internal'),
            ], limit=1)
        
        return dirty_location if dirty_location else False
    
    def _get_container_product(self):
        """Get or create a product representing the container for inventory tracking."""
        Product = self.env.get('product.product')
        if not Product:
            return False
        
        product_code = f"CONTAINER-{self.container_spec_id.code}"
        product = Product.search([('default_code', '=', product_code)], limit=1)
        
        if not product:
            try:
                product = Product.create({
                    'name': self.container_spec_id.name,
                    'default_code': product_code,
                    'type': 'product',
                    'categ_id': self.env.ref('product.product_category_all').id,
                })
            except Exception:
                return False
        
        return product
    
    def _create_buyback_credit_note(self):
        """
        Create draft Customer Credit Note for buyback amount.
        
        Note: Creates a simplified credit note. Production implementation
        should use proper journal and account configurations.
        """
        AccountMove = self.env.get('account.move')
        if not AccountMove:
            return False
        
        if not self.total_buyback_amount:
            return False
        
        try:
            credit_note = AccountMove.create({
                'move_type': 'out_refund',  # Customer Credit Note
                'partner_id': self.partner_id.id,
                'invoice_date': fields.Date.today(),
                'ref': _('Drum Buyback - %s') % self.container_spec_id.name,
                'narration': _('Container buyback for %d x %s') % (
                    self.quantity, 
                    self.container_spec_id.name
                ),
                'invoice_line_ids': [(0, 0, {
                    'name': _('Drum Buyback: %s') % self.container_spec_id.name,
                    'quantity': self.quantity,
                    'price_unit': self.buyback_unit_price,
                })],
            })
            return credit_note
        except Exception as e:
            # If credit note creation fails, log and continue
            self.partner_id.message_post(
                body=_('Failed to create credit note: %s') % str(e),
                subject=_('Credit Note Error'),
            )
            return False
