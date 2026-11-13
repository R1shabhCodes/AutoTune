import React from 'react';
import { 
  LayoutDashboard, 
  Layers, 
  PlayCircle, 
  CheckCircle2, 
  History, 
  Sliders, 
  ShieldCheck, 
  Settings, 
  Terminal,
  PanelLeftClose,
  PanelLeftOpen
} from 'lucide-react';

const NAV_GROUPS = [
  {
    title: 'Workspace',
    items: [
      { id: 'overview', label: 'Overview', icon: LayoutDashboard },
      { id: 'applications', label: 'Applications', icon: Layers },
      { id: 'evaluations', label: 'Evaluations', icon: CheckCircle2 },
    ]
  },
  {
    title: 'Optimization',
    items: [
      { id: 'experiments', label: 'Experiments', icon: PlayCircle },
      { id: 'trials', label: 'Trial history', icon: History },
      { id: 'optimization', label: 'Engine configuration', icon: Sliders },
    ]
  },
  {
    title: 'Governance',
    items: [
      { id: 'promotions', label: 'Promotions & diffs', icon: ShieldCheck },
      { id: 'settings', label: 'Settings', icon: Settings },
    ]
  }
];

export default function Sidebar({ activePage, setActivePage, isCollapsed, onToggleCollapse }) {
  return (
    <aside
      aria-label="Application navigation"
      style={{
        width: isCollapsed ? '58px' : '220px',
        background: 'var(--color-paper-3)',
        borderRight: 'var(--rule-hair) solid var(--color-rule)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width var(--dur-short) var(--ease-out)',
        userSelect: 'none',
        flexShrink: 0,
        height: '100vh',
        overflowY: 'auto',
        overflowX: 'hidden'
      }}
    >
      {/* Brand & Workspace Identity */}
      <div
        style={{
          height: '56px',
          display: 'flex',
          alignItems: 'center',
          padding: isCollapsed ? '0 var(--space-xs)' : '0 var(--space-sm)',
          borderBottom: 'var(--rule-hair) solid var(--color-rule)',
          gap: 'var(--space-xs)',
          justifyContent: isCollapsed ? 'center' : 'flex-start'
        }}
      >
        <div
          style={{
            width: '26px',
            height: '26px',
            borderRadius: 'var(--radius-pill)',
            background: 'var(--color-accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-accent-ink)',
            flexShrink: 0
          }}
          title="AutoTune 2.0 Console"
        >
          <Terminal size={14} />
        </div>

        {!isCollapsed && (
          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <span style={{ fontWeight: 500, fontSize: 'var(--text-sm)', color: 'var(--color-ink)', lineHeight: 1.15 }}>
              AutoTune
            </span>
            <span style={{ fontSize: '11px', color: 'var(--color-cool)', fontFamily: 'var(--font-outlier)', fontVariantNumeric: 'tabular-nums' }}>
              v2.0 Console
            </span>
          </div>
        )}

        {onToggleCollapse && !isCollapsed && (
          <button
            onClick={onToggleCollapse}
            aria-label="Collapse navigation sidebar"
            title="Collapse sidebar"
            className="sidebar-toggle-btn"
            style={{ marginLeft: 'auto' }}
          >
            <PanelLeftClose size={15} />
          </button>
        )}
      </div>

      {/* Nav List Partitioned into Groups */}
      <nav 
        style={{ 
          flex: 1, 
          padding: 'var(--space-xs) var(--space-2xs)', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: 'var(--space-xs)' 
        }}
      >
        {NAV_GROUPS.map((group) => (
          <div key={group.title} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {!isCollapsed && (
              <span
                style={{
                  fontSize: '11px',
                  color: 'var(--color-muted)',
                  fontWeight: 500,
                  padding: '4px 10px 2px 10px',
                  lineHeight: 1.2
                }}
              >
                {group.title}
              </span>
            )}
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = activePage === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActivePage(item.id)}
                  title={isCollapsed ? item.label : undefined}
                  aria-current={isActive ? 'page' : undefined}
                  className={`sidebar-nav-btn ${isActive ? 'active' : ''} ${isCollapsed ? 'collapsed' : ''}`}
                >
                  <Icon 
                    size={15} 
                    style={{ 
                      color: isActive ? 'var(--color-cool)' : 'var(--color-muted)', 
                      flexShrink: 0 
                    }} 
                  />
                  {!isCollapsed && <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.label}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer System Status & Expand Toggle */}
      <div 
        style={{ 
          padding: isCollapsed ? 'var(--space-xs) 0' : 'var(--space-xs) var(--space-sm)', 
          borderTop: 'var(--rule-hair) solid var(--color-rule)', 
          fontSize: '11px', 
          color: 'var(--color-muted)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: isCollapsed ? 'center' : 'space-between'
        }}
      >
        {isCollapsed ? (
          onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              aria-label="Expand navigation sidebar"
              title="Expand sidebar"
              className="sidebar-toggle-btn"
            >
              <PanelLeftOpen size={15} />
            </button>
          )
        ) : (
          <>
            <span style={{ fontFamily: 'var(--font-outlier)' }}>RAG Workbench</span>
            <span style={{ color: 'var(--color-cool)', fontSize: '10px' }}>Active</span>
          </>
        )}
      </div>
    </aside>
  );
}
