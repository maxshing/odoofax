# SOSI Industrial Modules for Odoo 18.0

This repository contains custom Odoo 18.0 modules developed by CROWDFORMOSA INDUSTRIAL CO., LTD.

## Modules

### Chemical OS
**Category:** Inventory/Chemicals  
**Description:** Chemical Product and Container Management System

Key Features:
- Advanced Packaging Management (Container Specifications)
- Container Ledger (Customer Container Accounts)
- Reverse Logistics Workflow (Buyback, Return Loan, Customer Inbound)
- Legacy Code Parsing and Migration

Dependencies: `base`, `stock`, `account`, `contacts`, `mail`, `mrp`, `maintenance`, `hr`

### Oil Data Factory
**Category:** Manufacturing  
**Description:** Oil production batch logging and IoT data management

Key Features:
- Batch production records
- SCADA data integration
- Quality inspection tracking
- IoT device data logging

Dependencies: `base`, `mail`, `product`, `stock`

### SOSI Academy
**Category:** Education  
**Description:** Educational partnership and student project management

Key Features:
- School data management
- Student project tracking
- Factory visit arrangements
- Educational dataset management

Dependencies: `base`, `product`, `mail`

### SOSI AI Core
**Category:** Productivity  
**Description:** Enterprise AI knowledge management and second brain

Key Features:
- Knowledge source management
- AI Q&A logging
- Model registry

Dependencies: `base`, `mail`

### SOSI Industrial Cloud
**Category:** Services  
**Description:** Factory-level information services and integrations

Key Features:
- Service package management
- System integrations (WooCommerce, Shopee, RFID, SCADA, Node-RED)
- Customer project tracking
- API management and monitoring

Dependencies: `base`, `mail`, `contacts`

## Deployment to Odoo.sh

### Prerequisites
- Odoo.sh account
- GitHub repository linked to Odoo.sh

### Steps

1. **Create a new Odoo.sh project:**
   - Go to [odoo.sh](https://www.odoo.sh)
   - Click "Create Project"
   - Select your GitHub repository (`odoofax`)

2. **Configure the branch:**
   - Odoo.sh will automatically detect the Odoo modules in the repository
   - Select the appropriate branch for your deployment (production, staging, development)

3. **Install modules:**
   - Once the build completes, go to Apps in your Odoo instance
   - Search for any of the modules listed above
   - Click Install

### Branch Types in Odoo.sh

- **Production:** Main branch for live usage
- **Staging:** For testing before production deployment
- **Development:** For development and experimentation

### Module Installation Order

Due to dependencies, install modules in this order:
1. `sosi_ai_core` (minimal dependencies)
2. `sosi_academy`
3. `sosi_industrial_cloud`
4. `oil_data_factory`
5. `chemical_os` (most dependencies)

## Technical Notes

- All modules are compatible with Odoo 18.0
- Modules use only Python standard library and Odoo built-in features
- No additional Python dependencies required

## License

LGPL-3

## Author

CROWDFORMOSA INDUSTRIAL CO., LTD.  
Website: https://www.crosa.com.tw
