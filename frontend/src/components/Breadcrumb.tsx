import React from 'react';
import { ChevronRight } from 'lucide-react';
import { useLocation, Link } from 'react-router-dom';

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 'var(--spacing-lg)',
  },
  title: {
    margin: 0,
    fontSize: '1.5rem',
    fontWeight: 600,
    color: 'var(--color-text-main)',
  },
  breadcrumb: {
    display: 'flex',
    alignItems: 'center',
    fontSize: '0.85rem',
    color: 'var(--color-text-muted)',
    listStyle: 'none',
    margin: 0,
    padding: 0,
  },
  item: {
    display: 'flex',
    alignItems: 'center',
  },
  link: {
    color: 'var(--color-text-muted)',
    textDecoration: 'none',
  },
  active: {
    color: 'var(--color-text-main)',
    fontWeight: 500,
  },
  separator: {
    margin: '0 var(--spacing-sm)',
    display: 'flex',
    alignItems: 'center',
  }
};

export const Breadcrumb: React.FC = () => {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter((x) => x);
  
  // Format path to Title Case
  const formatText = (text: string) => {
    return text.charAt(0).toUpperCase() + text.slice(1).replace(/-/g, ' ');
  };

  const currentTitle = pathnames.length > 0 ? formatText(pathnames[pathnames.length - 1]) : 'Dashboard';

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>{currentTitle}</h2>
      
      <ol style={styles.breadcrumb}>
        <li style={styles.item}>
          <Link to="/dashboard" style={styles.link}>Home</Link>
        </li>
        
        {pathnames.map((value, index) => {
          const last = index === pathnames.length - 1;
          const to = `/${pathnames.slice(0, index + 1).join('/')}`;

          return (
            <li key={to} style={styles.item}>
              <span style={styles.separator}>
                <ChevronRight size={14} />
              </span>
              {last ? (
                <span style={styles.active}>{formatText(value)}</span>
              ) : (
                <Link to={to} style={styles.link}>
                  {formatText(value)}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
};
