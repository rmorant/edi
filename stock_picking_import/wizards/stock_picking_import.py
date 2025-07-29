# Copyright 2023 ALBA Software
# @author: Rafa Morant <rmorant@albasoft.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import mimetypes
from base64 import b64decode, b64encode

from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import config
import logging

logger = logging.getLogger(__name__)


class StockPickingImport(models.TransientModel):
    _name = "stock.picking.import"
    _description = "Stock Picking Import"

    def default_get(self, fields):
        defaults = super().default_get(fields)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model == "stock.picking.type" and active_id:
            picking_type_id = active_id
        else:
            # TODO: search by user company
            picking_type_id = self.env.ref("stock.picking_type_in")

        defaults["picking_type_id"] = picking_type_id
        return defaults

    picking_type_id = fields.Many2one(
        string="Operation Type",
        comodel_name="stock.picking.type",
        required=True,
    )
    file = fields.Binary(
        string="Returns file",
        required=True,
        help="Upload a Returns file.",
    )
    filename = fields.Char(string="Filename")
    import_type = fields.Selection(
        string="Import file type",
        selection=[("csv", "CSV/XLS/ODT")],
        required=True,
    )
    doc_type = fields.Selection(
        string="Document Type",
        selection=[
            ("asn", "Advanced Shiping Notification"),
            # ("rasn", "Return Advanced Shiping Notification"),
        ],
        readonly=True,
    )
    partner_id = fields.Many2one(string="Partner", comodel_name="res.partner")

    @property
    def _bdio(self):
        return self.env["business.document.import"]

    @api.onchange("file")
    def file_change(self):
        if not self.filename or not self.file:
            self.doc_type = False
            return

        doc_type = self.parse_file(
            b64decode(self.file), self.filename, detect_doc_type=True
        )
        if doc_type is None:
            return {"warning": self._unsupported_file_msg(self.filename)}
        self.doc_type = doc_type

    @api.model
    def parse_picking(self, file, filename, partner=False):
        parsed_picking = self.parse_file(file, filename)
        logger.debug("Import Picking parsed: %s", parsed_picking)
        defaults = (
            ("attachments", {}),
            ("chatter_msg", []),
        )
        for key, val in defaults:
            parsed_picking.setdefault(key, val)
        parsed_picking["attachments"][filename] = b64encode(file)
        if (
            parsed_picking.get("company")
            and not config["test_enable"]
            and not self._context.get("edi_skip_company_check")
        ):
            self.env["business.document.import"]._check_company(
                parsed_picking["company"], parsed_picking["chatter_msg"]
            )
        return parsed_picking

    def _unsupported_file_msg(self, filename):
        return {
            "title": _("Unsupported file format"),
            "message": _(
                "This file '%s' is not recognised. "
                "Please check the file and it's extension."
            )
            % filename,
        }

    def _get_supported_types(self):
        # Define the supported types dictionary
        supported_types = {
            "txt": ("text/plain"),
            "csv": (
                # "text/plain"
                "text/csv",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.oasis.opendocument.spreadsheet",
            )
            # Do not supported yet
            # "xml": ("application/xml", "text/xml"),
            # "pdf": ("application/pdf"),
        }
        return supported_types

    def parse_file(self, filecontent, filename, detect_doc_type=False):
        assert filename, "Missing filename"
        assert filecontent, "Missing file content"
        filetype = mimetypes.guess_type(filename)
        mimetype = filetype[0]
        supported_types = self._get_supported_types()
        if self.import_type not in supported_types:
            raise UserError(_("Please select a valid import type before importing!"))

        # Check if the detected MIME type is supported for the selected import type
        if mimetype not in supported_types[self.import_type]:
            raise UserError(
                _(
                    "This file '%(filename)s' is not recognized as a %(type)s file. "
                    "Please check the file and its extension.",
                    filename=filename,
                    type=self.import_type.upper(),
                )
            )
        if hasattr(self, "parse_%s_picking" % self.import_type):
            return getattr(self, "parse_%s_picking" % self.import_type)(
                filecontent, detect_doc_type=detect_doc_type
            )
        else:
            raise UserError(
                _(
                    "This Import Type is not supported. Did you install "
                    "the module to support this type?"
                )
            )

    """
    parsed_picking. 
    Seed object for 'stock.picking' dictionary creation.
    Format:
    {
      'doc_type': 'rfq' or 'order',
      'partner': {
        'vat': 'FR25499247138',
        'name': 'Camptocamp',
        'email': 'luc@camptocamp.com',
      },
      'scheduled_date': '2023-11-20',
      'date_deadline': '2023-11-27',
      'lines': [{
        'product': {
          'code': 'EA7821',
          'ean13': '2100002000003',
        },
        # should_consume_qty (Acntidad a consumir) | product_uom_qty (Demanda)
        'qty': 2.5,
        # product_uom
        'uom': {'unece_code': 'C62'},
        'price_unit': 12.42,  # without taxes
      }]
    }

    """

    @api.model
    def parse_csv_picking(self, data, detect_doc_type=False):
        if detect_doc_type:
            return self.env.context.get("default_doc_type", "asn")
        filetype = mimetypes.guess_type(self.filename)
        mimetype = filetype[0]
        imp = self.env["base_import.import"].create(
            {
                "res_model": "stock.picking",
                "file": data,
                "file_name": self.filename,
                "file_type": mimetype,
            }
        )
        options = {}
        pp = imp.parse_preview(options)
        logger.info(pp)
        parsed_picking = {}

        return parsed_picking

    def import_button(self):
        self.ensure_one()
        file_decoded = b64decode(self.file)
        parsed_picking = self.parse_picking(
            file_decoded, self.filename, self.partner_id
        )
        if not parsed_picking.get("lines"):
            raise UserError(_("This reception doesn't have any line !"))

        return self.create_picking_return_action(parsed_picking, self.filename)

    def create_picking_return_action(self, parsed_picking, filename):
        self.ensure_one()
        stock_picking = self.create_stock_picking(parsed_picking, filename)
        stock_picking.message_post(
            body=_("Created automatically via file import (%s).") % self.filename
        )
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_form")
        action.update(
            {
                "view_mode": "form,tree",
                # "views": False,
                # "view_id": False,
                "res_id": stock_picking.id,
            }
        )
        return action

    @api.model
    def create_stock_picking(self, parsed_picking, filename=None):
        spo = self.env["stock.picking"].with_context(mail_create_nosubscribe=True)
        spo_vals = self._prepare_stock_picking(parsed_picking)
        stock_picking = spo.create(spo_vals)
        self._bdio.post_create_or_update(
            parsed_picking, stock_picking, doc_filename=filename
        )
        logger.info("Stock Picking ID %d created", stock_picking.id)
        return stock_picking

    @api.model
    def create_stock_picking_ws(self, parsed_picking, filename=None):
        """Same method as create_stock_picking() but callable via JSON-RPC
        webservice. Returns an ID to avoid this error:
        TypeError: sale.order(15,) is not JSON serializable"""
        stock_picking = self.create_stock_picking(parsed_picking, filename=filename)
        return stock_picking.id

    @api.model
    def prepare_stock_picking_dict(self, parsed_picking):
        spo = self.env["stock.picking"]
        partner = self._bdio._match_partner()
        # Parsed Picking
        pp = dict()

        return pp
