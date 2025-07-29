# Copyright 2023 ALBA Software (Rafa Morant <rmorant@albasoft.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)

from odoo.tests.common import Form

from .common import TestCommon


class SomethingCase(TestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parsed_picking = {}
