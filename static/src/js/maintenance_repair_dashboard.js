/** @odoo-module **/

import {registry} from "@web/core/registry";
import {Component, onMounted, onWillStart, onWillUnmount, useRef, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

const COLORS = {
    primary: "#4F46E5",
    success: "#22C55E",
    warning: "#F59E0B",
    danger: "#EF4444",
    info: "#06B6D4",
    blue: "#0EA5E9",
    slate: "#64748B",
};

class KioKpiCard extends Component {
    static template = "kio_maintenance_repair_dashboard.KpiCard";
    static props = {kpi: Object, onOpen: Function};

    iconClass(icon) {
        return {
            clipboard: "fa-list-alt",
            maintenance: "fa-check-square-o",
            repair: "fa-wrench",
            clock: "fa-clock",
            warning: "fa-exclamation-triangle",
            money: "fa-money",
        }[icon] || "fa-line-chart";
    }
}

class KioBottomKpi extends Component {
    static template = "kio_maintenance_repair_dashboard.BottomKpi";
    static props = {item: Object};

    iconClass(icon) {
        return {
            users: "fa-users",
            vendor: "fa-building",
            equipment: "fa-industry",
            warning: "fa-exclamation-triangle",
            shield: "fa-shield",
            calendar: "fa-calendar",
        }[icon] || "fa-bar-chart";
    }
}

export class MaintenanceRepairDashboard extends Component {
    static template = "kio_maintenance_repair_dashboard.MaintenanceRepairDashboard";
    static components = {KioKpiCard, KioBottomKpi};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.user = useService("user");
        this.state = useState({loading: true, data: null, query: ""});
        this.charts = [];

        this.openKpi = this.openKpi.bind(this);
        this.openMaintenance = this.openMaintenance.bind(this);
        this.openRepair = this.openRepair.bind(this);
        this.openSection = this.openSection.bind(this);

        this.trendChart = useRef("trendChart");
        this.categoryChart = useRef("categoryChart");
        this.statusChart = useRef("statusChart");
        this.downtimeChart = useRef("downtimeChart");
        this.mttrChart = useRef("mttrChart");
        this.mtbfChart = useRef("mtbfChart");
        this.costChart = useRef("costChart");

        onWillStart(async () => {
            await this.loadData();
        });
        onMounted(() => this.renderCharts());
        onWillUnmount(() => this.destroyCharts());
    }

    async loadData() {
        this.state.loading = true;
        this.state.data = await this.orm.call("kio.maintenance.repair.dashboard", "get_dashboard_data", []);
        this.state.loading = false;
    }

    get companyName() {
        return this.user?.context?.allowed_company_ids ? "My Company" : "My Company";
    }

    get userName() {
        return this.user?.name || "Mitchell Admin";
    }

    async openKpi(kpi) {
        const actions = {
            maintenance_orders: {
                name: "Maintenance Orders",
                res_model: "maintenance.request",
                view_mode: "kanban,tree,form",
                views: [[false, "kanban"], [false, "tree"], [false, "form"]],
            },
            repair_orders: {
                name: "Repair Orders",
                res_model: "repair.order",
                view_mode: "tree,form",
                views: [[false, "tree"], [false, "form"]],
            },
        };
        const action = actions[kpi.key];
        if (!action) {
            this.notification.add(`${kpi.title} drill-down is ready to configure.`, {type: "info"});
            return;
        }
        try {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: action.name,
                res_model: action.res_model,
                view_mode: action.view_mode,
                views: action.views,
                target: "current",
            });
        } catch {
            this.notification.add(`Unable to open ${action.name}.`, {type: "danger"});
        }
    }

    openMaintenance(row) {
        if (!row.id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "maintenance.request",
            res_id: row.id,
            views: [[false, "form"]],
            target: "current"
        });
    }

    openRepair(row) {
        if (!row.id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "repair.order",
            res_id: row.id,
            views: [[false, "form"]],
            target: "current"
        });
    }

    async openSection(name) {
        const sections = {
            "Maintenance Requests": {
                title: "Recent Maintenance Requests",
                res_model: "maintenance.request",
                domain: this.state.data.recent_maintenance_domain || [],
                view_mode: "kanban,tree,form",
                views: [[false, "kanban"], [false, "tree"], [false, "form"]],
            },
            "Repair Orders": {
                title: "Recent Repair Orders",
                res_model: "repair.order",
                domain: this.state.data.recent_repairs_domain || [],
                view_mode: "tree,form",
                views: [[false, "tree"], [false, "form"]],
            },
        };
        const section = sections[name];
        if (!section) {
            this.notification.add(`${name} drill-down is ready to configure.`, {type: "info"});
            return;
        }
        try {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: section.title,
                res_model: section.res_model,
                domain: section.domain,
                view_mode: section.view_mode,
                views: section.views,
                target: "current",
            });
        } catch {
            this.notification.add(`Unable to open ${section.title}.`, {type: "danger"});
        }
    }

    priorityClass(value) {
        return `kio-pill kio-priority-${String(value || "medium").toLowerCase()}`;
    }

    statusClass(value) {
        const status = String(value || "new").toLowerCase().replace(/\s+/g, "-");
        return `kio-pill kio-status-${status}`;
    }

    iconClass(icon) {
        return {
            clock: "fa-clock",
            repair: "fa-wrench",
            analytics: "fa-line-chart",
            money: "fa-bar-chart",
        }[icon] || "fa-line-chart";
    }

    destroyCharts() {
        for (const chart of this.charts) {
            chart.destroy();
        }
        this.charts = [];
    }

    renderCharts() {
        if (!window.Chart || !this.state.data) {
            return;
        }
        this.destroyCharts();
        const data = this.state.data;
        const grid = "rgba(148, 163, 184, 0.18)";
        const font = {family: "Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"};

        this.charts.push(new Chart(this.trendChart.el, {
            type: "line",
            data: {
                labels: data.charts.requests_trend.labels,
                datasets: [
                    this.lineDataset("Maintenance Requests", data.charts.requests_trend.maintenance, COLORS.primary),
                    this.lineDataset("Repair Orders", data.charts.requests_trend.repairs, "#0875E1"),
                ],
            },
            options: this.axisOptions(grid, font),
        }));

        this.charts.push(new Chart(
            this.categoryChart.el,
            this.doughnutConfig(
                data.charts.category,
                [COLORS.primary, "#0875E1", COLORS.success, "#F97316", "#94A3B8"],
                [this.doughnutCenterTextPlugin("Total Requests")]
            )
        ));
        this.charts.push(new Chart(this.statusChart.el, this.doughnutConfig(
            data.charts.status,
            ["#0875E1", "#F97316", "#FBBF24", "#22C55E", "#94A3B8"],
            [this.doughnutCenterTextPlugin("Total Orders")]
        )));
        this.charts.push(new Chart(this.downtimeChart.el, this.miniLineConfig(data.charts.downtime, COLORS.primary, true)));
        this.charts.push(new Chart(this.mttrChart.el, this.miniLineConfig(data.charts.mttr, "#0875E1", false)));
        this.charts.push(new Chart(this.mtbfChart.el, this.miniLineConfig(data.charts.mtbf, COLORS.success, false)));
        this.charts.push(new Chart(this.costChart.el, {
            type: "bar",
            data: {
                labels: data.charts.cost.labels,
                datasets: [{
                    data: data.charts.cost.data,
                    backgroundColor: "rgba(124, 58, 237, 0.72)",
                    borderRadius: 5,
                    maxBarThickness: 12
                }]
            },
            options: this.axisOptions(grid, font, false),
        }));
    }

    lineDataset(label, values, color) {
        return {
            label,
            data: values,
            borderColor: color,
            backgroundColor: `${color}1A`,
            borderWidth: 3,
            pointRadius: 2,
            pointHoverRadius: 5,
            fill: true,
            tension: 0.42,
        };
    }

    axisOptions(grid, font, legend = true) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: {duration: 850, easing: "easeOutQuart"},
            interaction: {intersect: false, mode: "index"},
            plugins: {
                legend: {
                    display: legend,
                    position: "top",
                    labels: {usePointStyle: true, boxWidth: 8, color: "#0F172A", font}
                }
            },
            scales: {
                x: {grid: {display: false}, ticks: {color: "#334155", maxTicksLimit: 8, font}},
                y: {beginAtZero: true, grid: {color: grid}, ticks: {color: "#334155", font}},
            },
        };
    }

    doughnutConfig(source, colors, plugins = []) {
        return {
            type: "doughnut",
            data: {
                labels: source.labels,
                datasets: [{data: source.data, backgroundColor: colors, borderWidth: 0, hoverOffset: 8}]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "58%",
                animation: {animateRotate: true, duration: 900},
                plugins: {
                    legend: {
                        position: "right",
                        labels: {usePointStyle: true, boxWidth: 8, color: "#0F172A", padding: 18}
                    }
                },
            },
            plugins,
        };
    }

    doughnutCenterTextPlugin(title) {
        return {
            id: `kioDoughnutCenterText${title.replace(/\s+/g, "")}`,
            afterDraw(chart) {
                const dataset = chart.data.datasets[0]?.data || [];
                const total = dataset.reduce((sum, value) => sum + Number(value || 0), 0);
                const {ctx, chartArea} = chart;

                if (!chartArea) {
                    return;
                }

                const centerX = (chartArea.left + chartArea.right) / 2;
                const centerY = (chartArea.top + chartArea.bottom) / 2;

                ctx.save();
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillStyle = "#64748B";
                ctx.font = "700 12px Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
                ctx.fillText(title, centerX, centerY - 10);
                ctx.fillStyle = "#0F172A";
                ctx.font = "850 24px Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
                ctx.fillText(String(total), centerX, centerY + 16);
                ctx.restore();
            },
        };
    }

    miniLineConfig(values, color, fill) {
        return {
            type: "line",
            data: {
                labels: values.map((_, index) => index + 1),
                datasets: [{
                    data: values,
                    borderColor: color,
                    backgroundColor: `${color}18`,
                    borderWidth: 2.5,
                    fill,
                    pointRadius: 0,
                    tension: 0.42
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {legend: {display: false}, tooltip: {enabled: false}},
                scales: {x: {display: false}, y: {display: false}},
                elements: {line: {capBezierPoints: true}}
            },
        };
    }
}

// Register the backend client-action tag used by views/dashboard_action.xml.
registry
    .category("actions")
    .add("kio_maintenance_repair_dashboard.maintenance_repair_dashboard", MaintenanceRepairDashboard);
