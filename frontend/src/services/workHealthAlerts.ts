export interface AlertRule {
    id: number;
    organization: number;
    alert_type: string;
    name: string;
    description: string;
    is_enabled: boolean;
    default_value: number;
    minimum_value: number | null;
    maximum_value: number | null;
    value_unit: string;
    employee_customization_allowed: boolean;
    severity: string;
    notification_enabled: boolean;
    applicable_branches: number[];
    applicable_departments: number[];
    applicable_teams: number[];
}

export interface EmployeeAlertPreference {
    id: number;
    rule: number;
    rule_name: string;
    rule_alert_type: string;
    rule_minimum_value: number;
    rule_maximum_value: number;
    rule_default_value: number;
    rule_unit: string;
    employee_customization_allowed: boolean;
    is_enabled: boolean;
    custom_value: number | null;
}

export interface AlertInstance {
    id: number;
    employee: number;
    employee_name: string;
    rule: number;
    rule_name: string;
    severity: string;
    status: string;
    evaluated_at: string;
    metric_value_at_trigger: number;
}

const getHeaders = () => {
    const token = localStorage.getItem('auth_token');
    return {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
    };
};

export const workHealthAlertsService = {
    getRules: async (): Promise<{data: AlertRule[]}> => {
        const res = await fetch('/api/v1/work-health-alerts/rules/', { headers: getHeaders() });
        if (!res.ok) throw new Error('Failed to load rules');
        return { data: await res.json() };
    },
    
    getPreferences: async (): Promise<{data: EmployeeAlertPreference[]}> => {
        const res = await fetch('/api/v1/work-health-alerts/preferences/', { headers: getHeaders() });
        if (!res.ok) throw new Error('Failed to load preferences');
        return { data: await res.json() };
    },
    
    updatePreference: async (id: number, data: Partial<EmployeeAlertPreference>): Promise<{data: EmployeeAlertPreference}> => {
        const res = await fetch(`/api/v1/work-health-alerts/preferences/${id}/`, {
            method: 'PATCH',
            headers: getHeaders(),
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error('Failed to update preference');
        return { data: await res.json() };
    },
    
    getInstances: async (own: boolean = false): Promise<{data: AlertInstance[]}> => {
        const url = `/api/v1/work-health-alerts/instances/${own ? '?own=true' : ''}`;
        const res = await fetch(url, { headers: getHeaders() });
        if (!res.ok) throw new Error('Failed to load instances');
        return { data: await res.json() };
    },
    
    acknowledgeInstance: async (id: number): Promise<void> => {
        const res = await fetch(`/api/v1/work-health-alerts/instances/${id}/acknowledge/`, {
            method: 'POST',
            headers: getHeaders()
        });
        if (!res.ok) throw new Error('Failed to acknowledge instance');
    }
};
