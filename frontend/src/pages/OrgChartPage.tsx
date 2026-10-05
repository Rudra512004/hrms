import React, { useState, useEffect, useMemo } from 'react';
import {
  Network,
  Users,
  ChevronDown,
  ChevronRight,
  Search,
  Building2,
  Briefcase,
  AlertCircle,
  Loader2,
  Maximize2,
  Minimize2,
  RefreshCw,
} from 'lucide-react';
import { Card } from '../components/Card';
import { organizationService, type Organization, type OrgChartNode } from '../services/organization';

interface OrgNodeProps {
  node: OrgChartNode;
  collapsedMap: Record<number, boolean>;
  onToggle: (id: number) => void;
  searchQuery: string;
}

const OrgNodeComponent: React.FC<OrgNodeProps> = ({
  node,
  collapsedMap,
  onToggle,
  searchQuery,
}) => {
  const isCollapsed = Boolean(collapsedMap[node.id]);
  const hasChildren = node.children && node.children.length > 0;

  const matchesSearch = useMemo(() => {
    if (!searchQuery.trim()) return false;
    const q = searchQuery.toLowerCase();
    return (
      node.name.toLowerCase().includes(q) ||
      (node.designation && node.designation.toLowerCase().includes(q)) ||
      (node.department && node.department.toLowerCase().includes(q)) ||
      node.email.toLowerCase().includes(q)
    );
  }, [node, searchQuery]);

  const initials = useMemo(() => {
    const parts = node.name.split(' ');
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return node.name.substring(0, 2).toUpperCase();
  }, [node.name]);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        position: 'relative',
        padding: '0 8px',
      }}
    >
      {/* Node Card */}
      <div
        style={{
          width: 250,
          background: matchesSearch
            ? 'var(--color-primary-light, rgba(2, 132, 199, 0.12))'
            : 'var(--surface-control-bg, var(--color-bg-card, #ffffff))',
          border: matchesSearch
            ? '2px solid var(--color-primary, #0284c7)'
            : '1px solid var(--color-border, #e2e8f0)',
          borderRadius: 'var(--radius-lg, 12px)',
          boxShadow: matchesSearch
            ? '0 4px 14px var(--color-primary-glow, rgba(2, 132, 199, 0.25))'
            : '0 2px 8px rgba(0, 0, 0, 0.05)',
          padding: '14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          transition: 'all 0.2s ease',
          zIndex: 2,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: '50%',
              background: 'var(--color-primary, #0284c7)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.85rem',
              flexShrink: 0,
            }}
          >
            {initials}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontWeight: 600,
                fontSize: '0.92rem',
                color: 'var(--color-text-main, #0f172a)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={node.name}
            >
              {node.name}
            </div>
            <div
              style={{
                fontSize: '0.75rem',
                color: 'var(--color-text-muted, #64748b)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={node.email}
            >
              {node.email}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginTop: '2px' }}>
          {node.designation && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '0.78rem',
                color: 'var(--color-text-sub, #334155)',
              }}
            >
              <Briefcase size={12} color="var(--color-text-muted)" />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {node.designation}
              </span>
            </div>
          )}

          {node.department && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '0.78rem',
                color: 'var(--color-text-sub, #334155)',
              }}
            >
              <Building2 size={12} color="var(--color-text-muted)" />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {node.department}
              </span>
            </div>
          )}
        </div>

        {/* Headcount pill and expand button */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: '4px',
            paddingTop: '6px',
            borderTop: '1px solid var(--color-border-subtle, rgba(0,0,0,0.06))',
          }}
        >
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 600,
              padding: '2px 7px',
              borderRadius: '6px',
              background: 'var(--color-bg-subtle, #f1f5f9)',
              color: 'var(--color-text-muted, #475569)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Users size={11} />
            {node.headcount} direct {node.total_headcount ? `· ${node.total_headcount} total` : ''}
          </span>

          {hasChildren && (
            <button
              type="button"
              onClick={() => onToggle(node.id)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--color-primary, #0284c7)',
                padding: '2px 4px',
              }}
              title={isCollapsed ? 'Expand team' : 'Collapse team'}
            >
              {isCollapsed ? (
                <>
                  <ChevronRight size={14} />
                  <span>({node.children.length})</span>
                </>
              ) : (
                <>
                  <ChevronDown size={14} />
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Children branches */}
      {hasChildren && !isCollapsed && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            width: '100%',
          }}
        >
          {/* Vertical stem down from parent */}
          <div
            style={{
              width: '2px',
              height: '24px',
              backgroundColor: 'var(--color-border, #cbd5e1)',
            }}
          />

          {/* Container for children with connecting line */}
          <div
            style={{
              display: 'flex',
              position: 'relative',
              justifyContent: 'center',
              paddingTop: '20px',
            }}
          >
            {node.children.length > 1 && (
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  left: '133px',
                  right: '133px',
                  height: '2px',
                  backgroundColor: 'var(--color-border, #cbd5e1)',
                }}
              />
            )}

            {node.children.map((child) => (
              <div
                key={child.id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  position: 'relative',
                }}
              >
                {/* Vertical stem up to connector */}
                <div
                  style={{
                    position: 'absolute',
                    top: '-20px',
                    width: '2px',
                    height: '20px',
                    backgroundColor: 'var(--color-border, #cbd5e1)',
                  }}
                />

                <OrgNodeComponent
                  node={child}
                  collapsedMap={collapsedMap}
                  onToggle={onToggle}
                  searchQuery={searchQuery}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const OrgChartPage: React.FC = () => {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null);
  const [treeRoots, setTreeRoots] = useState<OrgChartNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [collapsedMap, setCollapsedMap] = useState<Record<number, boolean>>({});
  const [searchQuery, setSearchQuery] = useState('');

  // 1. Fetch available organizations for dynamic tenant resolution
  useEffect(() => {
    organizationService
      .listOrganizations()
      .then((orgs) => {
        const list = Array.isArray(orgs) ? orgs : [];
        setOrganizations(list);
        if (list.length > 0) {
          setSelectedOrgId(list[0].id);
        } else {
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to load organizations for org chart:', err);
        setError('Unable to load organization information.');
        setLoading(false);
      });
  }, []);

  // 2. Fetch org chart whenever selected organization changes
  const fetchOrgChart = () => {
    if (!selectedOrgId) return;
    setLoading(true);
    setError(null);
    organizationService
      .getOrgChart(selectedOrgId)
      .then((roots) => {
        setTreeRoots(Array.isArray(roots) ? roots : []);
      })
      .catch((err) => {
        console.error('Failed to fetch org chart:', err);
        setError(err?.message || 'Unable to load organization chart hierarchy.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    if (selectedOrgId) {
      fetchOrgChart();
    }
  }, [selectedOrgId]);

  const handleToggleNode = (id: number) => {
    setCollapsedMap((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleExpandAll = () => {
    setCollapsedMap({});
  };

  const handleCollapseAll = () => {
    const map: Record<number, boolean> = {};
    const traverse = (nodes: OrgChartNode[]) => {
      nodes.forEach((n) => {
        if (n.children && n.children.length > 0) {
          map[n.id] = true;
          traverse(n.children);
        }
      });
    };
    traverse(treeRoots);
    setCollapsedMap(map);
  };

  // Compute total nodes across all trees
  const totalEmployees = useMemo(() => {
    let count = 0;
    const traverse = (nodes: OrgChartNode[]) => {
      count += nodes.length;
      nodes.forEach((n) => {
        if (n.children) traverse(n.children);
      });
    };
    traverse(treeRoots);
    return count;
  }, [treeRoots]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 'var(--spacing-md)',
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: 'var(--font-size-2xl)',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <Network size={26} color="var(--color-primary)" />
            Organization Chart
          </h1>
          <p className="text-muted" style={{ margin: '4px 0 0 0' }}>
            Interactive reporting hierarchy and team headcount breakdown.
          </p>
        </div>

        {/* Org Selector & Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {organizations.length > 1 && (
            <select
              aria-label="Select Organization"
              value={selectedOrgId || ''}
              onChange={(e) => setSelectedOrgId(Number(e.target.value))}
              className="input-neumorphic"
              style={{ minWidth: 200, height: 38 }}
            >
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
          )}

          <button
            className="btn btn-secondary"
            onClick={handleExpandAll}
            type="button"
            title="Expand all nodes"
          >
            <Maximize2 size={15} /> Expand All
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleCollapseAll}
            type="button"
            title="Collapse all nodes"
          >
            <Minimize2 size={15} /> Collapse All
          </button>
          <button
            className="btn btn-secondary"
            onClick={fetchOrgChart}
            type="button"
            title="Refresh chart"
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {/* Search and summary strip */}
      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ position: 'relative', flex: 1, minWidth: 240, maxWidth: 400 }}>
            <Search
              size={16}
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--color-text-muted)',
              }}
            />
            <input
              type="text"
              placeholder="Search by name, role, department..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-neumorphic"
              style={{ paddingLeft: '36px', width: '100%', height: 38 }}
            />
          </div>

          <div style={{ display: 'flex', gap: '16px', fontSize: '0.88rem' }}>
            <span style={{ color: 'var(--color-text-muted)' }}>
              Total Members: <strong style={{ color: 'var(--color-text-main)' }}>{totalEmployees}</strong>
            </span>
            <span style={{ color: 'var(--color-text-muted)' }}>
              Root Leaders: <strong style={{ color: 'var(--color-text-main)' }}>{treeRoots.length}</strong>
            </span>
          </div>
        </div>
      </Card>

      {/* Error state */}
      {error && (
        <Card>
          <div
            style={{
              padding: '24px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              color: 'var(--color-status-danger)',
            }}
          >
            <AlertCircle size={22} />
            <span style={{ flex: 1 }}>{error}</span>
            <button className="btn btn-secondary" onClick={fetchOrgChart} type="button">
              Retry
            </button>
          </div>
        </Card>
      )}

      {/* Loading state */}
      {loading && !error && (
        <Card>
          <div style={{ padding: '64px', textAlign: 'center' }}>
            <Loader2 size={36} className="animate-spin" color="var(--color-primary)" />
            <p className="text-muted" style={{ marginTop: '12px' }}>
              Building organizational hierarchy...
            </p>
          </div>
        </Card>
      )}

      {/* Empty state */}
      {!loading && !error && treeRoots.length === 0 && (
        <Card>
          <div style={{ padding: '48px', textAlign: 'center' }}>
            <Network size={42} color="var(--color-text-muted)" style={{ margin: '0 auto 12px' }} />
            <h3 style={{ margin: 0, fontSize: '1.15rem' }}>No Organization Hierarchy Found</h3>
            <p className="text-muted" style={{ maxWidth: 440, margin: '8px auto 0' }}>
              Active employees and their reporting managers have not yet been established for this organization.
            </p>
          </div>
        </Card>
      )}

      {/* Tree visualization scroll container */}
      {!loading && !error && treeRoots.length > 0 && (
        <div
          style={{
            overflowX: 'auto',
            overflowY: 'visible',
            padding: '24px 16px',
            backgroundColor: 'var(--surface-control-bg, var(--color-bg-subtle, #f8fafc))',
            borderRadius: 'var(--radius-xl, 16px)',
            border: '1px solid var(--color-border, #e2e8f0)',
            minHeight: '480px',
            display: 'flex',
            justifyContent: treeRoots.length === 1 ? 'center' : 'flex-start',
            gap: '40px',
          }}
        >
          {treeRoots.map((root) => (
            <OrgNodeComponent
              key={root.id}
              node={root}
              collapsedMap={collapsedMap}
              onToggle={handleToggleNode}
              searchQuery={searchQuery}
            />
          ))}
        </div>
      )}
    </div>
  );
};
