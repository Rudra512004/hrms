import React, { useState, useEffect, useCallback } from 'react';
import {
  assetService,
  type Asset,
  type AssetCategory,
  type CreateAssetPayload,
} from '../../services/assets';
import { branchService, type Branch } from '../../services/branch';
import { employeeManagementService } from '../../services/employeeManagement';
import { type EmployeeProfile } from '../../services/employee';
import { Card } from '../../components/Card';
import { StatusBadge } from '../../components/StatusBadge';
import { useAuth } from '../../contexts/AuthContext';
import {
  Package,
  Plus,
  Search,
  CheckCircle,
  UserCheck,
  Wrench,
  Eye,
  UserPlus,
  CornerDownLeft,
  Edit2,
  Trash2,
  X,
  AlertCircle,
  Loader2,
  History,
  FolderPlus,
} from 'lucide-react';
import { EmptyState } from '../../components/EmptyState';

export const AssetsPage: React.FC = () => {
  const { hasPermission } = useAuth();

  const canCreate = hasPermission('asset.create');
  const canUpdate = hasPermission('asset.update');
  const canDelete = hasPermission('asset.delete');
  const canAssign = hasPermission('asset.assign');

  // Data state
  const [assets, setAssets] = useState<Asset[]>([]);
  const [categories, setCategories] = useState<AssetCategory[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterBranch, setFilterBranch] = useState<string>('');

  // Modals state
  const [showAssetModal, setShowAssetModal] = useState(false);
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [assignTargetAsset, setAssignTargetAsset] = useState<Asset | null>(null);
  const [showReturnModal, setShowReturnModal] = useState(false);
  const [returnTargetAsset, setReturnTargetAsset] = useState<Asset | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [detailAsset, setDetailAsset] = useState<Asset | null>(null);

  // Form states
  const [assetForm, setAssetForm] = useState<CreateAssetPayload>({
    asset_tag: '',
    name: '',
    category: 0,
    branch: null,
    serial_number: '',
    model_number: '',
    purchase_date: null,
    purchase_cost: null,
    warranty_expiry: null,
    notes: '',
  });

  const [categoryForm, setCategoryForm] = useState({
    name: '',
    code: '',
    description: '',
  });

  const [assignForm, setAssignForm] = useState({
    employee: 0,
    expected_return_date: '',
    condition_at_allocation: 'good',
    allocation_notes: '',
  });

  const [returnForm, setReturnForm] = useState<{
    condition_at_return: string;
    return_notes: string;
    next_status: 'available' | 'under_maintenance' | 'retired';
  }>({
    condition_at_return: 'good',
    return_notes: '',
    next_status: 'available',
  });

  const [modalSubmitting, setModalSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [assetsData, catsData, branchesData, empsData] = await Promise.all([
        assetService.getAssets({
          category: filterCategory ? parseInt(filterCategory, 10) : undefined,
          status: filterStatus || undefined,
          branch: filterBranch ? parseInt(filterBranch, 10) : undefined,
          search: searchTerm.trim() || undefined,
        }),
        assetService.getCategories(),
        branchService.getAll().catch(() => []),
        employeeManagementService.listEmployees().catch(() => []),
      ]);

      setAssets(assetsData);
      setCategories(catsData);
      setBranches(branchesData);
      // Filter out exited employees for assignment dropdown
      setEmployees(empsData.filter((e: any) => e.employment_status !== 'exited'));
    } catch (err: any) {
      setError(err.data?.detail || 'Failed to load asset management data.');
    } finally {
      setLoading(false);
    }
  }, [filterCategory, filterStatus, filterBranch, searchTerm]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Metric stats
  const totalAssets = assets.length;
  const availableCount = assets.filter((a) => a.status === 'available').length;
  const assignedCount = assets.filter((a) => a.status === 'assigned').length;
  const maintenanceCount = assets.filter((a) => a.status === 'under_maintenance').length;

  // Open Add / Edit Asset Modal
  const openAssetModal = (asset?: Asset) => {
    setModalError(null);
    if (asset) {
      setEditingAsset(asset);
      setAssetForm({
        asset_tag: asset.asset_tag,
        name: asset.name,
        category: asset.category,
        branch: asset.branch,
        serial_number: asset.serial_number || '',
        model_number: asset.model_number || '',
        purchase_date: asset.purchase_date || null,
        purchase_cost: asset.purchase_cost || null,
        warranty_expiry: asset.warranty_expiry || null,
        notes: asset.notes || '',
      });
    } else {
      setEditingAsset(null);
      setAssetForm({
        asset_tag: '',
        name: '',
        category: categories.length > 0 ? categories[0].id : 0,
        branch: null,
        serial_number: '',
        model_number: '',
        purchase_date: null,
        purchase_cost: null,
        warranty_expiry: null,
        notes: '',
      });
    }
    setShowAssetModal(true);
  };

  const handleAssetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assetForm.category) {
      setModalError('Please select an asset category.');
      return;
    }
    setModalSubmitting(true);
    setModalError(null);
    try {
      if (editingAsset) {
        await assetService.updateAsset(editingAsset.id, assetForm);
      } else {
        await assetService.createAsset(assetForm);
      }
      setShowAssetModal(false);
      fetchData();
    } catch (err: any) {
      const msg =
        err.data?.detail ||
        (err.data?.asset_tag && err.data.asset_tag[0]) ||
        'Failed to save asset.';
      setModalError(msg);
    } finally {
      setModalSubmitting(false);
    }
  };

  // Open Category Modal
  const openCategoryModal = () => {
    setModalError(null);
    setCategoryForm({ name: '', code: '', description: '' });
    setShowCategoryModal(true);
  };

  const handleCategorySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalSubmitting(true);
    setModalError(null);
    try {
      await assetService.createCategory(categoryForm);
      setShowCategoryModal(false);
      fetchData();
    } catch (err: any) {
      const msg =
        err.data?.detail ||
        (err.data?.name && err.data.name[0]) ||
        (err.data?.code && err.data.code[0]) ||
        'Failed to create category.';
      setModalError(msg);
    } finally {
      setModalSubmitting(false);
    }
  };

  // Open Assign Modal
  const openAssignModal = (asset: Asset) => {
    setModalError(null);
    setAssignTargetAsset(asset);
    setAssignForm({
      employee: employees.length > 0 ? employees[0].id : 0,
      expected_return_date: '',
      condition_at_allocation: 'good',
      allocation_notes: '',
    });
    setShowAssignModal(true);
  };

  const handleAssignSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignTargetAsset || !assignForm.employee) {
      setModalError('Please select an active employee.');
      return;
    }
    setModalSubmitting(true);
    setModalError(null);
    try {
      await assetService.assignAsset(assignTargetAsset.id, {
        employee: assignForm.employee,
        expected_return_date: assignForm.expected_return_date || null,
        condition_at_allocation: assignForm.condition_at_allocation,
        allocation_notes: assignForm.allocation_notes,
      });
      setShowAssignModal(false);
      fetchData();
    } catch (err: any) {
      setModalError(err.data?.detail || 'Failed to assign asset.');
    } finally {
      setModalSubmitting(false);
    }
  };

  // Open Return Modal
  const openReturnModal = (asset: Asset) => {
    setModalError(null);
    setReturnTargetAsset(asset);
    setReturnForm({
      condition_at_return: 'good',
      return_notes: '',
      next_status: 'available',
    });
    setShowReturnModal(true);
  };

  const handleReturnSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!returnTargetAsset) return;
    setModalSubmitting(true);
    setModalError(null);
    try {
      await assetService.returnAsset(returnTargetAsset.id, returnForm);
      setShowReturnModal(false);
      fetchData();
    } catch (err: any) {
      setModalError(err.data?.detail || 'Failed to process asset return.');
    } finally {
      setModalSubmitting(false);
    }
  };

  // Open Details Modal
  const openDetailModal = async (asset: Asset) => {
    setShowDetailModal(true);
    try {
      const fullAsset = await assetService.getAsset(asset.id);
      setDetailAsset(fullAsset);
    } catch {
      setDetailAsset(asset);
    }
  };

  // Delete Asset
  const handleDeleteAsset = async (asset: Asset) => {
    if (asset.status === 'assigned') {
      alert('Cannot delete an asset that is currently assigned to an employee.');
      return;
    }
    if (!window.confirm(`Are you sure you want to permanently delete asset "${asset.asset_tag}" (${asset.name})?`)) {
      return;
    }
    try {
      await assetService.deleteAsset(asset.id);
      fetchData();
    } catch (err: any) {
      alert(err.data?.detail || 'Failed to delete asset.');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text-main)' }}>
            Asset Management
          </h1>
          <p style={{ margin: '4px 0 0 0', color: 'var(--color-text-muted)', fontSize: '0.95rem' }}>
            Track company equipment inventory, manage employee custody, and record returns.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          {canCreate && (
            <>
              <button className="btn btn-secondary" onClick={openCategoryModal} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <FolderPlus size={16} /> Add Category
              </button>
              <button className="btn btn-primary" onClick={() => openAssetModal()} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Plus size={16} /> Add Asset
              </button>
            </>
          )}
        </div>
      </div>

      {/* Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--spacing-md)' }}>
        <Card style={{ padding: 'var(--spacing-lg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: 44, height: 44, borderRadius: 'var(--radius-md)', backgroundColor: 'var(--color-primary-light, #e0f2fe)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-primary)' }}>
              <Package size={22} />
            </div>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'block' }}>Total Assets</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 700 }}>{totalAssets}</span>
            </div>
          </div>
        </Card>

        <Card style={{ padding: 'var(--spacing-lg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: 44, height: 44, borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(34, 197, 94, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#16a34a' }}>
              <CheckCircle size={22} />
            </div>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'block' }}>Available</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#16a34a' }}>{availableCount}</span>
            </div>
          </div>
        </Card>

        <Card style={{ padding: 'var(--spacing-lg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: 44, height: 44, borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(59, 130, 246, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#2563eb' }}>
              <UserCheck size={22} />
            </div>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'block' }}>Assigned</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#2563eb' }}>{assignedCount}</span>
            </div>
          </div>
        </Card>

        <Card style={{ padding: 'var(--spacing-lg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: 44, height: 44, borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(234, 179, 8, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ca8a04' }}>
              <Wrench size={22} />
            </div>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'block' }}>Under Maintenance</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ca8a04' }}>{maintenanceCount}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Filter Toolbar */}
      <Card style={{ padding: 'var(--spacing-md)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={16} color="var(--color-text-muted)" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              placeholder="Search tag, name, serial..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input"
              style={{ paddingLeft: '32px', width: '100%' }}
            />
          </div>

          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} className="input" style={{ width: '100%' }}>
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="input" style={{ width: '100%' }}>
            <option value="">All Statuses</option>
            <option value="available">Available</option>
            <option value="assigned">Assigned</option>
            <option value="under_maintenance">Under Maintenance</option>
            <option value="retired">Retired</option>
            <option value="lost">Lost</option>
          </select>

          <select value={filterBranch} onChange={(e) => setFilterBranch(e.target.value)} className="input" style={{ width: '100%' }}>
            <option value="">All Branches</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        </div>
      </Card>

      {/* Asset Table Card */}
      <Card noPadding>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px' }}>
            <Loader2 className="animate-spin text-muted" size={40} />
          </div>
        ) : error ? (
          <div style={{ padding: 'var(--spacing-xl)', textAlign: 'center' }}>
            <AlertCircle size={36} color="var(--color-danger, #ef4444)" style={{ marginBottom: '8px' }} />
            <p style={{ color: 'var(--color-danger, #ef4444)', margin: 0 }}>{error}</p>
          </div>
        ) : assets.length === 0 ? (
          <EmptyState
            title="No Assets Found"
            description="No assets match the selected filters. Add a new asset to begin tracking company equipment."
            icon={Package}
            action={
              canCreate ? (
                <button className="btn btn-primary" onClick={() => openAssetModal()} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <Plus size={16} /> Add First Asset
                </button>
              ) : undefined
            }
          />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg-subtle, #f8fafc)', color: 'var(--color-text-muted)' }}>
                  <th style={{ padding: '14px 16px', fontWeight: 600 }}>Asset Tag</th>
                  <th style={{ padding: '14px 16px', fontWeight: 600 }}>Name & Model</th>
                  <th style={{ padding: '14px 16px', fontWeight: 600 }}>Category</th>
                  <th style={{ padding: '14px 16px', fontWeight: 600 }}>Branch</th>
                  <th style={{ padding: '14px 16px', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '14px 16px', fontWeight: 600 }}>Assigned Custodian</th>
                  <th style={{ padding: '14px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {assets.map((asset) => (
                  <tr key={asset.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ padding: '14px 16px', fontWeight: 600, color: 'var(--color-primary)' }}>
                      <span style={{ backgroundColor: 'var(--color-primary-light, #e0f2fe)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.85rem' }}>
                        {asset.asset_tag}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ fontWeight: 500 }}>{asset.name}</div>
                      {asset.model_number && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                          Model: {asset.model_number}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px', color: 'var(--color-text-muted)' }}>
                      {asset.category_name}
                    </td>
                    <td style={{ padding: '14px 16px', color: 'var(--color-text-muted)' }}>
                      {asset.branch_name || '—'}
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <StatusBadge status={asset.status as any} />
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      {asset.current_assignment ? (
                        <div>
                          <span style={{ fontWeight: 500 }}>{asset.current_assignment.employee_name}</span>
                          <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                            {asset.current_assignment.employee_code} &bull; since {asset.current_assignment.allocated_at}
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>Unassigned</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', alignItems: 'center' }}>
                        <button className="btn btn-ghost" onClick={() => openDetailModal(asset)} title="View Specs & History" style={{ padding: '6px' }}>
                          <Eye size={16} />
                        </button>

                        {canAssign && asset.status === 'available' && (
                          <button className="btn btn-ghost" onClick={() => openAssignModal(asset)} title="Assign to Employee" style={{ padding: '6px', color: 'var(--color-primary)' }}>
                            <UserPlus size={16} />
                          </button>
                        )}

                        {canAssign && asset.status === 'assigned' && (
                          <button className="btn btn-ghost" onClick={() => openReturnModal(asset)} title="Return Asset" style={{ padding: '6px', color: '#16a34a' }}>
                            <CornerDownLeft size={16} />
                          </button>
                        )}

                        {canUpdate && (
                          <button className="btn btn-ghost" onClick={() => openAssetModal(asset)} title="Edit Asset" style={{ padding: '6px' }}>
                            <Edit2 size={16} />
                          </button>
                        )}

                        {canDelete && asset.status !== 'assigned' && (
                          <button className="btn btn-ghost" onClick={() => handleDeleteAsset(asset)} title="Delete Asset" style={{ padding: '6px', color: 'var(--color-danger, #ef4444)' }}>
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ─── ADD / EDIT ASSET MODAL ────────────────────────────────────────── */}
      {showAssetModal && (
        <div style={modalOverlayStyle}>
          <div style={modalCardStyle}>
            <div style={modalHeaderStyle}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>
                {editingAsset ? 'Edit Asset' : 'Add New Asset'}
              </h3>
              <button className="btn btn-ghost" onClick={() => setShowAssetModal(false)} disabled={modalSubmitting} style={{ padding: '4px' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAssetSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {modalError && (
                <div style={modalErrorStyle}>
                  <AlertCircle size={16} />
                  <span>{modalError}</span>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={labelStyle}>Asset Tag *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. AST-001"
                    value={assetForm.asset_tag}
                    onChange={(e) => setAssetForm({ ...assetForm, asset_tag: e.target.value })}
                    disabled={modalSubmitting || !!editingAsset}
                    className="input"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Category *</label>
                  <select
                    value={assetForm.category}
                    onChange={(e) => setAssetForm({ ...assetForm, category: parseInt(e.target.value, 10) })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                    required
                  >
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label style={labelStyle}>Asset Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. MacBook Pro 16 M3"
                  value={assetForm.name}
                  onChange={(e) => setAssetForm({ ...assetForm, name: e.target.value })}
                  disabled={modalSubmitting}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={labelStyle}>Serial Number</label>
                  <input
                    type="text"
                    placeholder="e.g. C02G12345"
                    value={assetForm.serial_number || ''}
                    onChange={(e) => setAssetForm({ ...assetForm, serial_number: e.target.value })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Model Number</label>
                  <input
                    type="text"
                    placeholder="e.g. A2485"
                    value={assetForm.model_number || ''}
                    onChange={(e) => setAssetForm({ ...assetForm, model_number: e.target.value })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={labelStyle}>Branch Location</label>
                  <select
                    value={assetForm.branch || ''}
                    onChange={(e) => setAssetForm({ ...assetForm, branch: e.target.value ? parseInt(e.target.value, 10) : null })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                  >
                    <option value="">No Branch / Global</option>
                    {branches.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Purchase Cost</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="e.g. 2499.00"
                    value={assetForm.purchase_cost || ''}
                    onChange={(e) => setAssetForm({ ...assetForm, purchase_cost: e.target.value || null })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              <div>
                <label style={labelStyle}>Notes / Description</label>
                <textarea
                  placeholder="Hardware specifications or special remarks"
                  value={assetForm.notes || ''}
                  onChange={(e) => setAssetForm({ ...assetForm, notes: e.target.value })}
                  disabled={modalSubmitting}
                  className="input"
                  rows={2}
                  style={{ width: '100%', resize: 'vertical' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowAssetModal(false)} disabled={modalSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={modalSubmitting}>
                  {modalSubmitting ? <Loader2 className="animate-spin" size={16} /> : (editingAsset ? 'Save Changes' : 'Create Asset')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── ADD CATEGORY MODAL ────────────────────────────────────────────── */}
      {showCategoryModal && (
        <div style={modalOverlayStyle}>
          <div style={{ ...modalCardStyle, maxWidth: '440px' }}>
            <div style={modalHeaderStyle}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>Add Asset Category</h3>
              <button className="btn btn-ghost" onClick={() => setShowCategoryModal(false)} disabled={modalSubmitting} style={{ padding: '4px' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCategorySubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {modalError && (
                <div style={modalErrorStyle}>
                  <AlertCircle size={16} />
                  <span>{modalError}</span>
                </div>
              )}

              <div>
                <label style={labelStyle}>Category Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Laptops, Monitors, Keycards"
                  value={categoryForm.name}
                  onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
                  disabled={modalSubmitting}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={labelStyle}>Code / Prefix *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. LAPTOP, MON, KEY"
                  value={categoryForm.code}
                  onChange={(e) => setCategoryForm({ ...categoryForm, code: e.target.value.toUpperCase() })}
                  disabled={modalSubmitting}
                  className="input"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={labelStyle}>Description (Optional)</label>
                <textarea
                  placeholder="Details regarding this classification"
                  value={categoryForm.description}
                  onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })}
                  disabled={modalSubmitting}
                  className="input"
                  rows={2}
                  style={{ width: '100%', resize: 'vertical' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowCategoryModal(false)} disabled={modalSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={modalSubmitting}>
                  {modalSubmitting ? <Loader2 className="animate-spin" size={16} /> : 'Create Category'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── ASSIGN ASSET MODAL ────────────────────────────────────────────── */}
      {showAssignModal && assignTargetAsset && (
        <div style={modalOverlayStyle}>
          <div style={{ ...modalCardStyle, maxWidth: '480px' }}>
            <div style={modalHeaderStyle}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>Assign Asset to Employee</h3>
              <button className="btn btn-ghost" onClick={() => setShowAssignModal(false)} disabled={modalSubmitting} style={{ padding: '4px' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAssignSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {modalError && (
                <div style={modalErrorStyle}>
                  <AlertCircle size={16} />
                  <span>{modalError}</span>
                </div>
              )}

              <div style={{ backgroundColor: 'var(--color-bg-subtle, #f8fafc)', padding: '12px', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'block' }}>Target Asset</span>
                <span style={{ fontWeight: 600 }}>{assignTargetAsset.asset_tag} &bull; {assignTargetAsset.name}</span>
              </div>

              <div>
                <label style={labelStyle}>Assign to Employee *</label>
                <select
                  value={assignForm.employee}
                  onChange={(e) => setAssignForm({ ...assignForm, employee: parseInt(e.target.value, 10) })}
                  disabled={modalSubmitting}
                  className="input"
                  style={{ width: '100%' }}
                  required
                >
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.first_name} {emp.last_name} ({emp.employee_code})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={labelStyle}>Condition at Allocation</label>
                  <select
                    value={assignForm.condition_at_allocation}
                    onChange={(e) => setAssignForm({ ...assignForm, condition_at_allocation: e.target.value })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                  >
                    <option value="new">Brand New</option>
                    <option value="excellent">Excellent</option>
                    <option value="good">Good</option>
                    <option value="fair">Fair</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Expected Return Date</label>
                  <input
                    type="date"
                    value={assignForm.expected_return_date}
                    onChange={(e) => setAssignForm({ ...assignForm, expected_return_date: e.target.value })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              <div>
                <label style={labelStyle}>Allocation Notes</label>
                <textarea
                  placeholder="Optional remarks regarding this handover"
                  value={assignForm.allocation_notes}
                  onChange={(e) => setAssignForm({ ...assignForm, allocation_notes: e.target.value })}
                  disabled={modalSubmitting}
                  className="input"
                  rows={2}
                  style={{ width: '100%', resize: 'vertical' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowAssignModal(false)} disabled={modalSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={modalSubmitting || !assignForm.employee}>
                  {modalSubmitting ? <Loader2 className="animate-spin" size={16} /> : 'Confirm Assignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── RETURN ASSET MODAL ────────────────────────────────────────────── */}
      {showReturnModal && returnTargetAsset && (
        <div style={modalOverlayStyle}>
          <div style={{ ...modalCardStyle, maxWidth: '480px' }}>
            <div style={modalHeaderStyle}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>Process Asset Return</h3>
              <button className="btn btn-ghost" onClick={() => setShowReturnModal(false)} disabled={modalSubmitting} style={{ padding: '4px' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleReturnSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {modalError && (
                <div style={modalErrorStyle}>
                  <AlertCircle size={16} />
                  <span>{modalError}</span>
                </div>
              )}

              <div style={{ backgroundColor: 'var(--color-bg-subtle, #f8fafc)', padding: '12px', borderRadius: 'var(--radius-md)' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', display: 'block' }}>Returning Asset</span>
                <span style={{ fontWeight: 600 }}>{returnTargetAsset.asset_tag} &bull; {returnTargetAsset.name}</span>
                {returnTargetAsset.current_assignment && (
                  <span style={{ display: 'block', fontSize: '0.85rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                    Current Custodian: {returnTargetAsset.current_assignment.employee_name}
                  </span>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={labelStyle}>Condition at Return</label>
                  <select
                    value={returnForm.condition_at_return}
                    onChange={(e) => setReturnForm({ ...returnForm, condition_at_return: e.target.value })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                  >
                    <option value="good">Good / Working</option>
                    <option value="damaged">Damaged / Faulty</option>
                    <option value="scratched">Minor Wear / Scratched</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Next Asset Status</label>
                  <select
                    value={returnForm.next_status}
                    onChange={(e) => setReturnForm({ ...returnForm, next_status: e.target.value as any })}
                    disabled={modalSubmitting}
                    className="input"
                    style={{ width: '100%' }}
                  >
                    <option value="available">Available for Reassignment</option>
                    <option value="under_maintenance">Under Maintenance</option>
                    <option value="retired">Retired / Decommissioned</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={labelStyle}>Return Notes</label>
                <textarea
                  placeholder="Notes on hardware condition or reason for status change"
                  value={returnForm.return_notes}
                  onChange={(e) => setReturnForm({ ...returnForm, return_notes: e.target.value })}
                  disabled={modalSubmitting}
                  className="input"
                  rows={2}
                  style={{ width: '100%', resize: 'vertical' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowReturnModal(false)} disabled={modalSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={modalSubmitting}>
                  {modalSubmitting ? <Loader2 className="animate-spin" size={16} /> : 'Complete Return'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── ASSET DETAIL & HISTORY DRAWER/MODAL ──────────────────────────── */}
      {showDetailModal && detailAsset && (
        <div style={modalOverlayStyle}>
          <div style={{ ...modalCardStyle, maxWidth: '640px' }}>
            <div style={modalHeaderStyle}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>{detailAsset.name}</h3>
                <span style={{ fontSize: '0.85rem', color: 'var(--color-primary)', fontWeight: 600 }}>{detailAsset.asset_tag}</span>
              </div>
              <button className="btn btn-ghost" onClick={() => setShowDetailModal(false)} style={{ padding: '4px' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '18px', maxHeight: '75vh', overflowY: 'auto' }}>
              {/* Specs Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
                <div style={detailBoxStyle}>
                  <span style={detailLabelStyle}>Category</span>
                  <span style={detailValueStyle}>{detailAsset.category_name}</span>
                </div>
                <div style={detailBoxStyle}>
                  <span style={detailLabelStyle}>Status</span>
                  <StatusBadge status={detailAsset.status as any} />
                </div>
                <div style={detailBoxStyle}>
                  <span style={detailLabelStyle}>Branch</span>
                  <span style={detailValueStyle}>{detailAsset.branch_name || '—'}</span>
                </div>
                <div style={detailBoxStyle}>
                  <span style={detailLabelStyle}>Serial Number</span>
                  <span style={detailValueStyle}>{detailAsset.serial_number || '—'}</span>
                </div>
                <div style={detailBoxStyle}>
                  <span style={detailLabelStyle}>Model Number</span>
                  <span style={detailValueStyle}>{detailAsset.model_number || '—'}</span>
                </div>
                <div style={detailBoxStyle}>
                  <span style={detailLabelStyle}>Cost</span>
                  <span style={detailValueStyle}>{detailAsset.purchase_cost ? `₹${detailAsset.purchase_cost}` : '—'}</span>
                </div>
              </div>

              {/* Assignment History */}
              <div>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <History size={16} /> Custody & Assignment History
                </h4>

                {!detailAsset.assignment_history || detailAsset.assignment_history.length === 0 ? (
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', margin: 0 }}>
                    No assignment records found for this asset.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {detailAsset.assignment_history.map((hist) => (
                      <div key={hist.id} style={{ border: '1px solid var(--color-border)', padding: '10px 14px', borderRadius: 'var(--radius-md)', fontSize: '0.85rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 600 }}>{hist.employee_name} ({hist.employee_code})</span>
                          <span style={{ fontSize: '0.75rem', padding: '2px 6px', borderRadius: '4px', backgroundColor: hist.is_active ? '#dcfce7' : 'var(--color-bg-subtle, #f1f5f9)', color: hist.is_active ? '#166534' : 'var(--color-text-muted)' }}>
                            {hist.is_active ? 'Currently Active' : 'Returned'}
                          </span>
                        </div>
                        <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                          Allocated: {hist.allocated_at} &bull; Condition: {hist.condition_at_allocation}
                          {hist.returned_at && ` &bull; Returned: ${hist.returned_at} (${hist.condition_at_return || 'good'})`}
                        </div>
                        {hist.allocation_notes && (
                          <div style={{ marginTop: '4px', fontSize: '0.8rem', fontStyle: 'italic' }}>
                            "{hist.allocation_notes}"
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const modalOverlayStyle: React.CSSProperties = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'rgba(0, 0, 0, 0.5)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  padding: '16px',
};

const modalCardStyle: React.CSSProperties = {
  backgroundColor: 'var(--color-bg-surface, #ffffff)',
  borderRadius: 'var(--radius-lg, 12px)',
  maxWidth: '560px',
  width: '100%',
  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
  overflow: 'hidden',
};

const modalHeaderStyle: React.CSSProperties = {
  padding: '16px 20px',
  borderBottom: '1px solid var(--color-border)',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

const modalErrorStyle: React.CSSProperties = {
  padding: '10px 14px',
  backgroundColor: 'rgba(239, 68, 68, 0.1)',
  borderRadius: 'var(--radius-md, 8px)',
  color: 'var(--color-danger, #ef4444)',
  fontSize: '0.85rem',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.825rem',
  fontWeight: 500,
  marginBottom: '5px',
};

const detailBoxStyle: React.CSSProperties = {
  backgroundColor: 'var(--color-bg-subtle, #f8fafc)',
  padding: '10px 12px',
  borderRadius: 'var(--radius-md, 8px)',
};

const detailLabelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.75rem',
  color: 'var(--color-text-muted)',
  marginBottom: '2px',
};

const detailValueStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: '0.9rem',
};
