import { useState } from 'react';
import { refreshSuppliers } from '../api/client';
import { useToast } from '../components/Toast';
import './AdminPage.css';

const USERS = [
  { name: 'Fatima Naeem', email: 'fatima@idp.com', role: 'admin', status: 'active' },
  { name: 'Maheen Rizwan', email: 'maheen@idp.com', role: 'reviewer', status: 'active' },
  { name: 'Juweriya Nasir', email: 'juweriya@idp.com', role: 'reviewer', status: 'active' },
  { name: 'Ali Khan', email: 'ali@enterprise.com', role: 'enterprise_user', status: 'active' },
  { name: 'Sara Ahmed', email: 'sara@enterprise.com', role: 'enterprise_user', status: 'inactive' },
];

export default function AdminPage() {
  const toast = useToast();
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState(null);

  const handleUserAction = () => {
    toast('Coming soon — user management not yet connected', 'info');
  };

  const handleRefreshSuppliers = async () => {
    setRefreshing(true);
    try {
      const data = await refreshSuppliers();
      setRefreshResult(data);
      toast(`Supplier metrics refreshed: ${data.suppliers_updated} supplier(s) updated`, 'success');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div>
      <h1 className="admin__title">Administration</h1>

      <div className="admin__section">
        <h2 className="admin__section-title">Supplier Analytics</h2>
        <p className="admin__section-desc">
          Recompute supplier metrics and risk scores from all processed documents.
        </p>
        <button
          className="admin__add-btn"
          onClick={handleRefreshSuppliers}
          disabled={refreshing}
        >
          {refreshing ? 'Refreshing...' : 'Refresh Supplier Metrics'}
        </button>
        {refreshResult && (
          <div className="admin__refresh-result">
            <div className="admin__refresh-stat">
              Suppliers updated: <strong>{refreshResult.suppliers_updated}</strong>
            </div>
            <div className="admin__refresh-stat">
              Risk scores computed: <strong>{refreshResult.risk_scores_computed}</strong>
            </div>
            {refreshResult.suppliers?.length > 0 && (
              <table className="admin__table" style={{ marginTop: 12 }}>
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th>Documents</th>
                    <th>Avg Confidence</th>
                    <th>Risk Score</th>
                    <th>Method</th>
                  </tr>
                </thead>
                <tbody>
                  {refreshResult.suppliers.map((s) => (
                    <tr key={s.supplier_name}>
                      <td>{s.supplier_name}</td>
                      <td>{s.total_documents}</td>
                      <td>{s.avg_confidence ? `${(s.avg_confidence * 100).toFixed(1)}%` : 'N/A'}</td>
                      <td>{s.risk_score}</td>
                      <td>{s.method}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      <div className="admin__section">
        <h2 className="admin__section-title">User Management</h2>
        <div className="placeholder-banner">
          User management API not yet available. Displaying placeholder data.
        </div>

        <div className="admin__actions">
          <button className="admin__add-btn" onClick={handleUserAction}>
            Add User
          </button>
        </div>

        <div className="admin__table-wrap">
          <table className="admin__table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {USERS.map((u) => (
                <tr key={u.email}>
                  <td>{u.name}</td>
                  <td>{u.email}</td>
                  <td>
                    <span className={`admin__role-pill admin__role-pill--${u.role}`}>
                      {u.role.replace('_', ' ')}
                    </span>
                  </td>
                  <td>
                    <span className={u.status === 'active' ? 'admin__status-active' : 'admin__status-inactive'}>
                      {u.status}
                    </span>
                  </td>
                  <td>
                    <button className="admin__action-btn" onClick={handleUserAction}>Edit</button>
                    <button className="admin__action-btn admin__action-btn--danger" onClick={handleUserAction}>
                      {u.status === 'active' ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
