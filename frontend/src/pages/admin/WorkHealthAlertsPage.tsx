import React, { useState, useEffect } from 'react';
import type { AlertRule } from '../../services/workHealthAlerts';
import { workHealthAlertsService } from '../../services/workHealthAlerts';
import { PageHeader } from '../../components/PageHeader';

export const WorkHealthAlertsPage: React.FC = () => {
    const [rules, setRules] = useState<AlertRule[]>([]);
    
    useEffect(() => {
        loadRules();
    }, []);

    const loadRules = async () => {
        try {
            const res = await workHealthAlertsService.getRules();
            setRules(res.data);
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="p-6 max-w-7xl mx-auto">
            <PageHeader title="Work Health Alerts Configuration" subtitle="Manage organization-level work health and pattern rules" />
            
            <div className="bg-white rounded-lg shadow mt-6 p-6">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rule</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Default</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bounds</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {rules.map(rule => (
                            <tr key={rule.id}>
                                <td className="px-6 py-4">
                                    <div className="text-sm font-medium text-gray-900">{rule.name}</div>
                                    <div className="text-sm text-gray-500">{rule.alert_type}</div>
                                </td>
                                <td className="px-6 py-4 text-sm text-gray-500">
                                    {rule.default_value} {rule.value_unit}
                                </td>
                                <td className="px-6 py-4 text-sm text-gray-500">
                                    {rule.minimum_value || 'None'} - {rule.maximum_value || 'None'}
                                </td>
                                <td className="px-6 py-4 text-sm">
                                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${rule.is_enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                                        {rule.is_enabled ? 'Active' : 'Disabled'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                        {rules.length === 0 && (
                            <tr>
                                <td colSpan={4} className="px-6 py-4 text-center text-sm text-gray-500">No rules configured.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
