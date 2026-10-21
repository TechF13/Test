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
