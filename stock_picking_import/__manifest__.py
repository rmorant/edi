# Copyright <YEAR(S)> <AUTHOR(S)>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Import Returns",
    "summary": "",
    "version": "14.0.1.0.0",
    # see https://odoo-community.org/page/development-status
    "development_status": "Alpha",
    "category": "Sales Management",
    "website": "https://github.com/OCA/edi/tree/14.0/stock_picking_import",
    "author": "ALBA Software, Camptocamp, Odoo Community Association (OCA)",
    # see https://odoo-community.org/page/maintainer-role for a description of the maintainer role and responsibilities
    "maintainers": ["rmorant"],
    "license": "AGPL-3",
    "depends": [
        "stock",
        # OCA/edi
        "base_business_document_import",
        # OCA/server-tools
        "onchange_helper",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/stock_picking_import_view.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
}
