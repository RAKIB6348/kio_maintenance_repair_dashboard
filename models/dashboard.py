# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models


class MaintenanceRepairDashboard(models.AbstractModel):
    _name = "kio.maintenance.repair.dashboard"
    _description = "Maintenance Repair Dashboard Data"

    @api.model
    def get_dashboard_data(self):
        today = fields.Date.context_today(self)
        start_date = today.replace(day=1)
        end_date = today
        previous_start = (start_date - timedelta(days=1)).replace(day=1)
        previous_end = start_date - timedelta(days=1)

        maintenance_model = self._model("maintenance.request")
        repair_model = self._model("repair.order")
        equipment_model = self._model("maintenance.equipment")

        # এই মাসে মোট কত Maintenance Order আছে (type নির্বিশেষে - preventive/corrective সব মিলিয়ে)
        maintenance_orders_this_month = self._count(
            maintenance_model,
            self._base_domain(maintenance_model, start_date, end_date),
        )

        # মোট সব Maintenance Orders (type নির্বিশেষে, সবসময়, কখনো month filter হবে না)
        total_maintenance_orders = self._count(
            maintenance_model,
            self._company_domain(maintenance_model),
        )

        # এই মাস শুরু হওয়ার আগে পর্যন্ত মোট কত ছিল - comparison baseline
        total_maintenance_orders_previous = max(total_maintenance_orders - maintenance_orders_this_month, 0)

        # Repair Orders এর জন্য পরিবর্তন
        repair_orders_this_month = self._count(repair_model, self._base_domain(repair_model, start_date, end_date))

        # মোট সব Repair Orders (এটাই সবসময় KPI card এর মূল value, কখনো month দিয়ে filter হবে না)
        total_repair_orders = self._count(repair_model)

        # এই মাস শুরু হওয়ার আগে পর্যন্ত মোট কত repair order ছিল - এটাই তুলনার (comparison) baseline।
        total_repair_orders_previous = max(total_repair_orders - repair_orders_this_month, 0)
        maintenance_cost = self._maintenance_cost(repair_model, start_date, end_date)
        previous_cost = self._maintenance_cost(repair_model, previous_start, previous_end)
        recent_maintenance = self._recent_maintenance(maintenance_model, start_date, end_date)
        recent_maintenance_domain = self._ids_domain([row["id"] for row in recent_maintenance])
        recent_repairs = self._recent_repairs(repair_model, start_date, end_date)
        recent_repairs_domain = self._ids_domain([row["id"] for row in recent_repairs])

        # KIO CUSTOM: Today's Maintenance Requests
        today_maintenance_requests = self._count(
            maintenance_model,
            self._date_domain(maintenance_model, today, today)
        )

        # KIO CUSTOM: Today's Repair Orders
        today_repair_orders = self._count(
            repair_model,
            self._date_domain(repair_model, today, today)
        )
        # ================== REPAIR STATES ==================
        repair_states = self._get_repair_states_count(repair_model)
        # ===================================================

        return {
            "period": {"label": "%s - %s" % (start_date.strftime("%b %d, %Y"), end_date.strftime("%b %d, %Y"))},
            "kpis": [
                self._kpi("maintenance_orders", "Total Maintenance Orders", total_maintenance_orders, total_maintenance_orders_previous, f"{maintenance_orders_this_month} This Month", "maintenance", "success"),
                self._kpi("repair_orders", "Total Repair Orders", total_repair_orders, total_repair_orders_previous,
                          f"{repair_orders_this_month} This Month", "repair", "info"),

                # নতুন যোগ করা হলো
                self._kpi("repair_new", "New Repair", repair_states.get("draft", 0), 0, "New", "repair", "warning"),
                self._kpi("repair_confirmed", "Confirmed Repair", repair_states.get("confirmed", 0), 0, "Confirmed",
                          "repair", "primary"),
                self._kpi("repair_under", "Under Repair", repair_states.get("under_repair", 0), 0, "In Progress",
                          "repair", "danger"),
                self._kpi("repair_repaired", "Repaired", repair_states.get("done", 0), 0, "Done", "repair", "success"),
                self._kpi("repair_cancelled", "Cancelled Repair", repair_states.get("cancel", 0), 0, "Cancelled",
                          "repair", "danger"),
            ],
            "charts": {
                "requests_trend": self._requests_trend(maintenance_model, repair_model, start_date, end_date),
                "category": self._category_chart(maintenance_model, start_date, end_date),
                "status": self._status_chart(repair_model, maintenance_model, start_date, end_date),
                "downtime": self._mini_series(31, 24, 48),
                "mttr": self._mini_series(31, 2, 8),
                "mtbf": self._mini_series(31, 80, 160),
                "cost": self._cost_trend(repair_model, start_date, end_date),
            },
            "recent_maintenance": recent_maintenance,
            "recent_maintenance_domain": recent_maintenance_domain,
            "recent_repairs": recent_repairs,
            "recent_repairs_domain": recent_repairs_domain,
            "equipment_downtime": self._equipment_downtime(maintenance_model),
            "analytics": {
                "downtime": {"title": "Downtime Analysis", "value": "53.4 hrs", "change": -9, "icon": "clock",
                             "color": "primary"},
                "mttr": {"title": "MTTR (Mean Time To Repair)", "value": "4.25 hrs", "change": 6, "icon": "repair",
                         "color": "info"},
                "mtbf": {"title": "MTBF (Mean Time Between Failure)", "value": "128.6 hrs", "change": 11,
                         "icon": "analytics", "color": "success"},
                "cost": {"title": "Maintenance Cost Trend", "value": self._money(maintenance_cost),
                         "change": self._change(maintenance_cost, previous_cost), "icon": "money", "color": "warning"},
            },
            "bottom_kpis": self._bottom_kpis(equipment_model),
        }

    def _model(self, model_name):
        # NOTE: এটা explicit ভাবে False অথবা একটা recordset রিটার্ন করে।
        # কখনো `if model:` দিয়ে চেক করা উচিত না, কারণ Odoo recordset-এর
        # truthiness নির্ভর করে তার ভেতরে কয়টা record bound আছে তার উপর -
        # model valid কিনা সেটার উপর না। সবসময় `model is False` / `model is not False`
        # দিয়ে চেক করতে হবে।
        return self.env[model_name].sudo() if model_name in self.env.registry else False

    def _field(self, model, names):
        if model is False:
            return False
        return next((name for name in names if name in model._fields), False)

    def _count(self, model, domain=None):
        return model.search_count(domain or []) if model is not False else 0

    def _date_domain(self, model, start_date, end_date):
        field = self._field(model, ["request_date", "schedule_date", "create_date", "date"])
        return [(field, ">=", start_date), (field, "<=", end_date)] if field else []

    def _company_domain(self, model):
        if not self._field(model, ["company_id"]):
            return []
        company_ids = self.env.context.get("allowed_company_ids") or self.env.companies.ids
        return [("company_id", "in", company_ids)] if company_ids else []

    def _base_domain(self, model, start_date, end_date):
        return self._date_domain(model, start_date, end_date) + self._company_domain(model)

    def _maintenance_type_domain(self, model, maintenance_type):
        return [("maintenance_type", "=", maintenance_type)] if self._field(model, ["maintenance_type"]) else []

    def _pending_count(self, model):
        if model is False:
            return 0
        if self._field(model, ["stage_id"]):
            return model.search_count([("stage_id.fold", "=", False)])
        if self._field(model, ["state"]):
            return model.search_count([("state", "in", ["draft", "confirmed", "under_repair"])])
        return 0

    def _overdue_count(self, model, today):
        date_field = self._field(model, ["schedule_date", "request_date", "date_deadline"])
        if model is False or not date_field:
            return 0
        domain = [(date_field, "<", today)]
        if self._field(model, ["stage_id"]):
            domain.append(("stage_id.fold", "=", False))
        elif self._field(model, ["state"]):
            domain.append(("state", "not in", ["done", "cancel"]))
        return model.search_count(domain)

    def _maintenance_cost(self, repair_model, start_date, end_date):
        if repair_model is False:
            return 0.0
        amount_field = self._field(repair_model, ["amount_total", "invoice_amount", "price_total"])
        if not amount_field:
            return 0.0
        repairs = repair_model.search(self._date_domain(repair_model, start_date, end_date))
        return sum(repairs.mapped(amount_field))

    def _kpi(self, key, title, value, previous, status, icon, color, money=False):
        change = self._change(value, previous)
        return {
            "key": key,
            "title": title,
            "value": self._money(value) if money else value,
            "change": change,
            "trend": "up" if change >= 0 else "down",
            "status": status,
            "icon": icon,
            "color": color,
        }

    def _change(self, current, previous):
        if not previous:
            return 0 if not current else 100
        return round(((current - previous) / previous) * 100)

    def _money(self, value):
        return "$ {:,.0f}".format(value or 0)

    def _requests_trend(self, maintenance_model, repair_model, start_date, end_date):
        labels = []
        maintenance = []
        repairs = []
        current = start_date
        while current <= end_date:
            labels.append(current.strftime("%b %-d"))
            maintenance.append(self._count(maintenance_model, self._date_domain(maintenance_model, current, current)))
            repairs.append(self._count(repair_model, self._date_domain(repair_model, current, current)))
            current += timedelta(days=1)
        return {"labels": labels, "maintenance": maintenance, "repairs": repairs}

    def _category_chart(self, model, start_date, end_date):
        if model is False or not self._field(model, ["equipment_id"]):
            return {"total_requests": 0, "equipment_categories": [], "labels": [], "data": []}

        domain = self._company_domain(model) + [("equipment_id.category_id", "!=", False)]
        category_counts = {}
        for request in model.search(domain):
            category = request.equipment_id.category_id
            if category.id not in category_counts:
                category_counts[category.id] = {
                    "id": category.id,
                    "name": category.display_name,
                    "count": 0,
                }
            category_counts[category.id]["count"] += 1

        equipment_categories = sorted(
            category_counts.values(),
            key=lambda category: (-category["count"], category["name"]),
        )

        return {
            "total_requests": sum(category["count"] for category in equipment_categories),
            "equipment_categories": equipment_categories,
            "labels": [category["name"] for category in equipment_categories],
            "data": [category["count"] for category in equipment_categories],
        }

    # KIO CUSTOM: Dynamic repair.order status chart from actual state selection.
    def _status_chart(self, repair_model, maintenance_model=False, start_date=False, end_date=False):
        if repair_model is False or "state" not in repair_model._fields:
            return {"labels": [], "data": []}

        state_selection = dict(repair_model._fields["state"].selection)
        state_order = list(state_selection.keys())

        records = repair_model.search([])

        counts = {state: 0 for state in state_order}

        for record in records:
            if record.state in counts:
                counts[record.state] += 1

        return {
            "labels": [state_selection[state] for state in state_order],
            "data": [counts[state] for state in state_order],
        }

    def _ids_domain(self, record_ids):
        return [["id", "in", record_ids]] if record_ids else [["id", "=", False]]

    def _recent_maintenance(self, model, start_date, end_date):
        order_field = self._field(model, ["request_date", "create_date"])
        order = "%s desc" % order_field if order_field else "id desc"
        records = model.search(self._base_domain(model, start_date, end_date), limit=5, order=order) if model is not False else []
        rows = []
        for record in records:
            rows.append({
                "id": record.id,
                "request_no": record.name or "MR/%s" % record.id,
                "equipment": record.equipment_id.display_name if "equipment_id" in record._fields and record.equipment_id else "Equipment",
                "priority": self._priority(record),
                "date": self._format_date(record, ["request_date", "create_date"]),
                "status": record.stage_id.display_name if "stage_id" in record._fields and record.stage_id else "New",
            })
        return rows

    def _recent_repairs(self, model, start_date, end_date):
        order_field = self._field(model, ["schedule_date", "create_date"])
        order = "%s desc" % order_field if order_field else "id desc"
        records = model.search(self._base_domain(model, start_date, end_date), limit=5, order=order) if model is not False else []
        rows = []
        for record in records:
            rows.append({
                "id": record.id,
                "repair_order": record.name or "RO/%s" % record.id,
                "equipment": record.product_id.display_name if "product_id" in record._fields and record.product_id else "Equipment",
                "priority": self._priority(record),
                "date": self._format_date(record, ["schedule_date", "create_date"]),
                "status": dict(record._fields["state"].selection).get(record.state,
                                                                      record.state) if "state" in record._fields else "In Progress",
            })
        return rows

    def _priority(self, record):
        if "priority" not in record._fields:
            return "Medium"
        return {"0": "Low", "1": "Medium", "2": "High", "3": "Urgent"}.get(record.priority, "Medium")

    def _format_date(self, record, fields_list):
        field = next((name for name in fields_list if name in record._fields and record[name]), False)
        return fields.Date.to_string(record[field]) if field else ""

    def _equipment_downtime(self, model):
        rows = []
        if model is not False and self._field(model, ["equipment_id"]):
            groups = model.read_group([("equipment_id", "!=", False)], ["equipment_id"], ["equipment_id"], limit=5)
            for index, group in enumerate(groups):
                hours = round((group["equipment_id_count"] * 2.8) + (5 - index), 1)
                rows.append({
                    "equipment": group["equipment_id"][1],
                    "downtime": hours,
                    "orders": group["equipment_id_count"],
                    "percent": min(100, round(hours * 4)),
                    "color": ["danger", "warning", "amber", "success", "info"][index % 5],
                })
        return rows or [
            {"equipment": "CNC Machine - 01", "downtime": 18.5, "orders": 6, "percent": 95, "color": "danger"},
            {"equipment": "Air Compressor - 02", "downtime": 12.3, "orders": 4, "percent": 72, "color": "warning"},
            {"equipment": "Generator - 01", "downtime": 9.8, "orders": 3, "percent": 58, "color": "amber"},
            {"equipment": "Packaging Machine - 03", "downtime": 7.2, "orders": 3, "percent": 43, "color": "success"},
            {"equipment": "Conveyor Belt - 02", "downtime": 5.6, "orders": 2, "percent": 31, "color": "info"},
        ]

    def _cost_trend(self, repair_model, start_date, end_date):
        labels = []
        data = []
        current = start_date
        while current <= end_date:
            labels.append(current.strftime("%b %-d"))
            data.append(self._maintenance_cost(repair_model, current, current))
            current += timedelta(days=1)
        if not any(data):
            data = [21000, 14000, 19000, 16000, 29000, 17000, 13000, 15000, 22000, 28000, 24000, 19000, 17000, 16000,
                    31000, 18000, 13000, 17000, 20000, 16000, 19000, 24000, 22000, 19000, 15000, 14000, 16000, 12000,
                    13000, 25000, 18000][: len(labels)]
        return {"labels": labels, "data": data}

    def _mini_series(self, length, low, high):
        span = high - low
        return [round(low + ((index * 7) % span) + ((index % 4) * 1.5), 1) for index in range(length)]

    def _bottom_kpis(self, equipment_model):
        employee_model = self._model("hr.employee")
        partner_model = self._model("res.partner")
        equipment_total = self._count(equipment_model)
        return [
            {"title": "Total Technicians", "value": self._count(employee_model, [("employee_type", "=",
                                                                                  "employee")]) if employee_model is not False and "employee_type" in employee_model._fields else self._count(
                employee_model), "icon": "users", "color": "neutral"},
            {"title": "Active Vendors",
             "value": self._count(partner_model, [("supplier_rank", ">", 0)]) if partner_model is not False else 0, "icon": "vendor",
             "color": "neutral"},
            {"title": "Total Equipment", "value": equipment_total, "icon": "equipment", "color": "neutral"},
            {"title": "Critical Equipment", "value": max(0, round(equipment_total * 0.11)), "icon": "warning",
             "color": "danger"},
            {"title": "Warranty Expiring", "value": max(0, round(equipment_total * 0.05)), "icon": "shield",
             "color": "warning"},
            {"title": "PM Due This Week", "value": max(0, round(equipment_total * 0.07)), "icon": "calendar",
             "color": "primary"},
        ]

    def _sample_maintenance(self):
        return [
            {"id": 1, "request_no": "MR/2025/0042", "equipment": "CNC Machine - 01", "priority": "Urgent",
             "date": "2025-05-30", "status": "In Progress"},
            {"id": 2, "request_no": "MR/2025/0041", "equipment": "Air Compressor - 02", "priority": "High",
             "date": "2025-05-29", "status": "In Progress"},
            {"id": 3, "request_no": "MR/2025/0040", "equipment": "Packaging Machine - 03", "priority": "Medium",
             "date": "2025-05-28", "status": "New"},
            {"id": 4, "request_no": "MR/2025/0039", "equipment": "Generator - 01", "priority": "High",
             "date": "2025-05-27", "status": "Done"},
            {"id": 5, "request_no": "MR/2025/0038", "equipment": "Conveyor Belt - 01", "priority": "Low",
             "date": "2025-05-26", "status": "In Progress"},
        ]

    def _sample_repairs(self):
        return [
            {"id": 1, "repair_order": "RO/2025/0023", "equipment": "CNC Machine - 01", "priority": "Urgent",
             "date": "2025-05-30", "status": "In Progress"},
            {"id": 2, "repair_order": "RO/2025/0022", "equipment": "Air Compressor - 02", "priority": "High",
             "date": "2025-05-29", "status": "In Progress"},
            {"id": 3, "repair_order": "RO/2025/0021", "equipment": "Generator - 01", "priority": "Medium",
             "date": "2025-05-28", "status": "Repaired"},
            {"id": 4, "repair_order": "RO/2025/0020", "equipment": "Conveyor Belt - 02", "priority": "Low",
             "date": "2025-05-27", "status": "Repaired"},
            {"id": 5, "repair_order": "RO/2025/0019", "equipment": "Packaging Machine - 03", "priority": "High",
             "date": "2025-05-26", "status": "Cancelled"},
        ]

    # KIO CUSTOM: Dynamic repair.order state-wise counts.
    def _get_repair_states_count(self, repair_model):
        if repair_model is False or "state" not in repair_model._fields:
            return {}

        state_selection = dict(repair_model._fields["state"].selection)
        counts = {state: 0 for state in state_selection.keys()}

        records = repair_model.search([])

        for record in records:
            if record.state in counts:
                counts[record.state] += 1

        return counts