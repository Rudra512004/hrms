import React, { useState, useEffect } from 'react';
import type { EmployeeAlertPreference } from '../../services/workHealthAlerts';
import { workHealthAlertsService } from '../../services/workHealthAlerts';
import { PageHeader } from '../../components/PageHeader';

export const MyAlertPreferencesPage: React.FC = () => {
    const [preferences, setPreferences] = useState<EmployeeAlertPreference[]>([]);
    
    useEffect(() => {
        loadPreferences();
    }, []);

    const loadPreferences = async () => {
        try {
            const res = await workHealthAlertsService.getPreferences();
            setPreferences(res.data);
        } catch (e) {
            console.error(e);
        }
    };

    const handleUpdate = async (id: number, data: Partial<EmployeeAlertPreference>) => {
        try {
            await workHealthAlertsService.updatePreference(id, data);
            loadPreferences();
        } catch (e) {
            alert('Failed to update. Check boundaries.');
        }
    }

    return (
        <div className="p-6 max-w-7xl mx-auto">
            <PageHeader title="My Work Health Alerts" subtitle="Configure your personal alert boundaries within organization limits" />
            
            <div className="bg-white rounded-lg shadow mt-6 p-6 space-y-4">
                {preferences.map(pref => (
                    <div key={pref.id} className="border p-4 rounded-md flex items-center justify-between">
                        <div>
                            <h3 className="text-lg font-medium">{pref.rule_name}</h3>
                            <p className="text-sm text-gray-500">
                                Default: {pref.rule_default_value} {pref.rule_unit} 
                                {pref.employee_customization_allowed ? ` (Allowed Range: ${pref.rule_minimum_value} - ${pref.rule_maximum_value})` : ' (Customization disabled)'}
                            </p>
                        </div>
                        {pref.employee_customization_allowed && (
                            <div className="flex items-center space-x-4">
                                <input 
                                    type="number" 
                                    className="border rounded px-2 py-1 w-24"
                                    placeholder={String(pref.rule_default_value)}
                                    value={pref.custom_value || ''}
                                    onChange={e => handleUpdate(pref.id, { custom_value: e.target.value ? Number(e.target.value) : null })}
                                    min={pref.rule_minimum_value}
                                    max={pref.rule_maximum_value}
                                />
                                <span className="text-sm text-gray-500">{pref.rule_unit}</span>
                            </div>
                        )}
                    </div>
                ))}
                {preferences.length === 0 && <p className="text-gray-500">No active alerts configured by your organization.</p>}
            </div>
        </div>
    );
};
