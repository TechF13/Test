import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

export class PoliticalDashboard extends Component {
    static template = "political_office.Dashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, hover: null });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call("political.dashboard", "get_dashboard_data", []);
    }

    get kpis() {
        return [
            { key: "open_requests", label: _t("Open Requests"), icon: "fa-bullhorn" },
            { key: "overdue_requests", label: _t("Overdue Requests"), icon: "fa-clock-o", alert: true },
            { key: "today_events", label: _t("Today's Events"), icon: "fa-calendar" },
            { key: "open_motions", label: _t("Open Motions"), icon: "fa-university" },
            { key: "new_news", label: _t("New Articles (24 hours)"), icon: "fa-newspaper-o" },
            { key: "negative_news", label: _t("Negative Articles (7 days)"), icon: "fa-thumbs-o-down", alert: true },
            { key: "action_news", label: _t("Articles Awaiting Action"), icon: "fa-flag", alert: true },
        ];
    }

    get trendMax() {
        return Math.max(1, ...this.state.data.trend.days.map((day) => day.total));
    }

    segmentHeight(count) {
        return `${(100 * count) / this.trendMax}%`;
    }

    zoneWidth(count) {
        const max = Math.max(1, ...this.state.data.zones.map((zone) => zone.count));
        return `${(100 * count) / max}%`;
    }

    sentimentTotal(key) {
        return this.state.data.trend.days.reduce((sum, day) => sum + day[key], 0);
    }

    async openKpi(key) {
        const action = await this.orm.call("political.dashboard", "open_kpi", [key]);
        this.action.doAction(action);
    }

    openRecord(resModel, resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
        });
    }

    openXmlAction(xmlId) {
        this.action.doAction(xmlId);
    }
}

registry.category("actions").add("political_office.dashboard", PoliticalDashboard);
