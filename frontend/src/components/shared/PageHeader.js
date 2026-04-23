import React from 'react';
import './PageHeader.css';

export default function PageHeader({ title, subtitle, actions, badge }) {
  return (
    <div className="page-header">
      <div className="page-header-left">
        <div className="page-header-title-row">
          <h1 className="page-header-title">{title}</h1>
          {badge && <span className={`badge badge-${badge.type || 'default'}`}>{badge.text}</span>}
        </div>
        {subtitle && <p className="page-header-subtitle">{subtitle}</p>}
      </div>
      {actions && (
        <div className="page-header-actions">
          {actions}
        </div>
      )}
    </div>
  );
}
