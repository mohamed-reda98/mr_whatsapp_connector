/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const POLL_MS = 4000;

export class MrWhatsAppQrWidget extends Component {
    static template = "mr_whatsapp_connector.QrWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.state = useState({
            status: this.props.record.data[this.props.name] || "unknown",
            phone: this.props.record.data.whatsapp_status_phone || "",
            qr: null,
            error: null,
            loading: true,
        });
        this._timer = null;

        onWillStart(async () => {
            await this.refresh();
        });
        this._timer = setInterval(() => this.refresh(), POLL_MS);
        onWillUnmount(() => {
            if (this._timer) {
                clearInterval(this._timer);
                this._timer = null;
            }
        });
    }

    async refresh() {
        try {
            const status = await rpc("/mr_whatsapp/status", {});
            this.state.status = status.state || "unknown";
            this.state.phone = status.phone || "";
            this.state.error = status.error || null;
            if (this.state.status === "qr" || this.state.status === "qr_code") {
                const qrResp = await rpc("/mr_whatsapp/qr", {});
                this.state.qr = qrResp.qr || null;
            } else {
                this.state.qr = null;
            }
        } catch (e) {
            this.state.error = (e && e.message) || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    get statusBadgeClass() {
        const map = {
            ready: "bg-success",
            authenticated: "bg-success",
            qr: "bg-warning",
            qr_code: "bg-warning",
            initializing: "bg-info",
            disconnected: "bg-danger",
            auth_failure: "bg-danger",
            error: "bg-danger",
            unknown: "bg-secondary",
        };
        return map[this.state.status] || "bg-secondary";
    }

    get statusLabel() {
        const map = {
            ready: "Connected",
            authenticated: "Authenticated",
            qr: "Scan QR",
            qr_code: "Scan QR",
            initializing: "Starting…",
            disconnected: "Disconnected",
            auth_failure: "Auth Failed",
            error: "Sidecar Unreachable",
            unknown: "Unknown",
        };
        return map[this.state.status] || this.state.status;
    }
}

export const mrWhatsAppQrField = {
    component: MrWhatsAppQrWidget,
    displayName: "WhatsApp QR / Status",
    supportedTypes: ["char"],
};

registry.category("fields").add("mr_whatsapp_qr", mrWhatsAppQrField);
