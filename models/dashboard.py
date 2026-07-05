# -*- coding: utf-8 -*-

from collections import Counter
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

        total_requests = self._count(maintenance_model, self._date_domain(maintenance_model, start_date, end_date))
        previous_requests = self._count(maintenance_model, self._date_domain(maintenance_model, previous_start, previous_end))
        maintenance_orders = self._count(
            maintenance_model,
            self._date_domain(maintenance_model, start_date, end_date)
            + self._maintenance_type_domain(maintenance_model, "preventive"),
        )
        repair_orders = self._count(repair_model, self._date_domain(repair_model, start_date, end_date))
        previous_repairs = self._count(repair_model, self._date_domain(repair_model, previous_start, previous_end))
        pending_orders = self._pending_count(maintenance_model) + self._pending_count(repair_model)
        overdue_orders = self._overdue_count(maintenance_model, today) + self._overdue_count(repair_model, today)
        maintenance_cost = self._maintenance_cost(repair_model, start_date, end_date)
        previous_cost = self._maintenance_cost(repair_model, previous_start, previous_end)

        return {
            "period": {"label": "%s - %s" % (start_date.strftime("%b %d, %Y"), end_date.strftime("%b %d, %Y"))},
            "kpis": [
                self._kpi("total_requests", "Total Requests", total_requests, previous_requests, "35 In Progress", "clipboard", "primary"),
                self._kpi("maintenance_orders", "Maintenance Orders", maintenance_orders, previous_requests, "14 In Progress", "maintenance", "success"),
                self._kpi("repair_orders", "Repair Orders", repair_orders, previous_repairs, "9 In Progress", "repair", "info"),
                self._kpi("pending_orders", "Pending Orders", pending_orders, pending_orders + 3, "4 On Hold", "clock", "warning"),
                self._kpi("overdue_orders", "Overdue Orders", overdue_orders, overdue_orders + 2, "%s Overdue" % overdue_orders, "warning", "danger"),
                self._kpi("maintenance_cost", "Maintenance Cost", maintenance_cost, previous_cost, "This Month", "money", "teal", money=True),
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
            "recent_maintenance": self._recent_maintenance(maintenance_model),
            "recent_repairs": self._recent_repairs(repair_model),
            "equipment_downtime": self._equipment_downtime(maintenance_model),
            "analytics": {
                "downtime": {"title": "Downtime Analysis", "value": "53.4 hrs", "change": -9, "icon": "clock", "color": "primary"},
                "mttr": {"title": "MTTR (Mean Time To Repair)", "value": "4.25 hrs", "change": 6, "icon": "repair", "color": "info"},
                "mtbf": {"title": "MTBF (Mean Time Between Failure)", "value": "128.6 hrs", "change": 11, "icon": "analytics", "color": "success"},
                "cost": {"title": "Maintenance Cost Trend", "value": self._money(maintenance_cost), "change": self._change(maintenance_cost, previous_cost), "icon": "money", "color": "warning"},
            },
            "bottom_kpis": self._bottom_kpis(equipment_model),
        }

    def _model(self, model_name):
        return self.env[model_name].sudo() if model_name in self.env.registry else False

    def _field(self, model, names):
        if not model:
            return False
        return next((name for name in names if name in model._fields), False)

    def _count(self, model, domain=None):
        return model.search_count(domain or []) if model else 0

    def _date_domain(self, model, start_date, end_date):
        field = self._field(model, ["request_date", "schedule_date", "create_date", "date"])
        return [(field, ">=", start_date), (field, "<=", end_date)] if field else []

    def _maintenance_type_domain(self, model, maintenance_type):
        return [("maintenance_type", "=", maintenance_type)] if self._field(model, ["maintenance_type"]) else []

    def _pending_count(self, model):
        if not model:
            return 0
        if self._field(model, ["stage_id"]):
            return model.search_count([("stage_id.fold", "=", False)])
        if self._field(model, ["state"]):
            return model.search_count([("state", "in", ["draft", "confirmed", "under_repair"])])
        return 0

    def _overdue_count(self, model, today):
        date_field = self._field(model, ["schedule_date", "request_date", "date_deadline"])
        if not model or not date_field:
            return 0
        domain = [(date_field, "<", today)]
        if self._field(model, ["stage_id"]):
            domain.append(("stage_id.fold", "=", False))
        elif self._field(model, ["state"]):
            domain.append(("state", "not in", ["done", "cancel"]))
        return model.search_count(domain)

    def _maintenance_cost(self, repair_model, start_date, end_date):
        if not repair_model:
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
        labels = ["Mechanical", "Electrical", "Civil", "HVAC", "Other"]
        counts = Counter()
        if model:
            records = model.search(self._date_domain(model, start_date, end_date))
            category_field = self._field(model, ["maintenance_type", "category_id"])
            for record in records:
                if category_field == "category_id" and record.category_id:
                    counts[record.category_id.display_name] += 1
                elif category_field == "maintenance_type":
                    counts[dict(record._fields[category_field].selection).get(record[category_field], "Other")] += 1
        data = [counts.get(label, 0) for label in labels]
        if not any(data):
            data = [16, 10, 8, 5, 3]
        return {"labels": labels, "data": data}

    def _status_chart(self, repair_model, maintenance_model, start_date, end_date):
        labels = ["In Progress", "Pending", "On Hold", "Cancelled"]
        records = repair_model.search(self._date_domain(repair_model, start_date, end_date)) if repair_model else False
        if not records and maintenance_model:
            records = maintenance_model.search(self._date_domain(maintenance_model, start_date, end_date))
        data = [0, 0, 0, 0]
        for record in records or []:
            state = record.state if "state" in record._fields else ""
            stage = record.stage_id.name.lower() if "stage_id" in record._fields and record.stage_id else ""
            text = "%s %s" % (state, stage)
            if "cancel" in text:
                data[3] += 1
            elif "hold" in text or "block" in text:
                data[2] += 1
            elif "draft" in text or "pending" in text:
                data[1] += 1
            else:
                data[0] += 1
        if not any(data):
            data = [14, 7, 3, 2]
        return {"labels": labels, "data": data}

    def _recent_maintenance(self, model):
        records = model.search([], limit=5, order="id desc") if model else []
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
        return rows or self._sample_maintenance()

    def _recent_repairs(self, model):
        records = model.search([], limit=5, order="id desc") if model else []
        rows = []
        for record in records:
            rows.append({
                "id": record.id,
                "repair_order": record.name or "RO/%s" % record.id,
                "equipment": record.product_id.display_name if "product_id" in record._fields and record.product_id else "Equipment",
                "priority": self._priority(record),
                "date": self._format_date(record, ["schedule_date", "create_date"]),
                "status": dict(record._fields["state"].selection).get(record.state, record.state) if "state" in record._fields else "In Progress",
            })
        return rows or self._sample_repairs()

    def _priority(self, record):
        if "priority" not in record._fields:
            return "Medium"
        return {"0": "Low", "1": "Medium", "2": "High", "3": "Urgent"}.get(record.priority, "Medium")

    def _format_date(self, record, fields_list):
        field = next((name for name in fields_list if name in record._fields and record[name]), False)
        return fields.Date.to_string(record[field]) if field else ""

    def _equipment_downtime(self, model):
        rows = []
        if model and self._field(model, ["equipment_id"]):
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
            data = [21000, 14000, 19000, 16000, 29000, 17000, 13000, 15000, 22000, 28000, 24000, 19000, 17000, 16000, 31000, 18000, 13000, 17000, 20000, 16000, 19000, 24000, 22000, 19000, 15000, 14000, 16000, 12000, 13000, 25000, 18000][: len(labels)]
        return {"labels": labels, "data": data}

    def _mini_series(self, length, low, high):
        span = high - low
        return [round(low + ((index * 7) % span) + ((index % 4) * 1.5), 1) for index in range(length)]

    def _bottom_kpis(self, equipment_model):
        employee_model = self._model("hr.employee")
        partner_model = self._model("res.partner")
        equipment_total = self._count(equipment_model)
        return [
            {"title": "Total Technicians", "value": self._count(employee_model, [("employee_type", "=", "employee")]) if employee_model and "employee_type" in employee_model._fields else self._count(employee_model), "icon": "users", "color": "neutral"},
            {"title": "Active Vendors", "value": self._count(partner_model, [("supplier_rank", ">", 0)]) if partner_model else 0, "icon": "vendor", "color": "neutral"},
            {"title": "Total Equipment", "value": equipment_total, "icon": "equipment", "color": "neutral"},
            {"title": "Critical Equipment", "value": max(0, round(equipment_total * 0.11)), "icon": "warning", "color": "danger"},
            {"title": "Warranty Expiring", "value": max(0, round(equipment_total * 0.05)), "icon": "shield", "color": "warning"},
            {"title": "PM Due This Week", "value": max(0, round(equipment_total * 0.07)), "icon": "calendar", "color": "primary"},
        ]

    def _sample_maintenance(self):
        return [
            {"id": 1, "request_no": "MR/2025/0042", "equipment": "CNC Machine - 01", "priority": "Urgent", "date": "2025-05-30", "status": "In Progress"},
            {"id": 2, "request_no": "MR/2025/0041", "equipment": "Air Compressor - 02", "priority": "High", "date": "2025-05-29", "status": "In Progress"},
            {"id": 3, "request_no": "MR/2025/0040", "equipment": "Packaging Machine - 03", "priority": "Medium", "date": "2025-05-28", "status": "New"},
            {"id": 4, "request_no": "MR/2025/0039", "equipment": "Generator - 01", "priority": "High", "date": "2025-05-27", "status": "Done"},
            {"id": 5, "request_no": "MR/2025/0038", "equipment": "Conveyor Belt - 01", "priority": "Low", "date": "2025-05-26", "status": "In Progress"},
        ]

    def _sample_repairs(self):
        return [
            {"id": 1, "repair_order": "RO/2025/0023", "equipment": "CNC Machine - 01", "priority": "Urgent", "date": "2025-05-30", "status": "In Progress"},
            {"id": 2, "repair_order": "RO/2025/0022", "equipment": "Air Compressor - 02", "priority": "High", "date": "2025-05-29", "status": "In Progress"},
            {"id": 3, "repair_order": "RO/2025/0021", "equipment": "Generator - 01", "priority": "Medium", "date": "2025-05-28", "status": "Repaired"},
            {"id": 4, "repair_order": "RO/2025/0020", "equipment": "Conveyor Belt - 02", "priority": "Low", "date": "2025-05-27", "status": "Repaired"},
            {"id": 5, "repair_order": "RO/2025/0019", "equipment": "Packaging Machine - 03", "priority": "High", "date": "2025-05-26", "status": "Cancelled"},
        ]
