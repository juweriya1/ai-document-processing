import { useState, useEffect } from 'react';
import {
  refreshSuppliers, listUsers, createUser, updateUser,
  deactivateUser, activateUser,
} from '../api/client';
import { useToast } from '../components/Toast';
import './AdminPage.css';

const BLANK_USER = { email: '', password: '', name: '', role: 'enterprise_user' };

export default function AdminPage() {
  const toast = useToast();
  const [tab, setTab]                   = useState('users');
  const [refreshing, setRefreshing]     = useState(false);
  const [refreshResult, setRefreshResult] = useState(null);
  const [users, setUsers]               = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [showAddForm, setShowAddForm]   = useState(false);
  const [newUser, setNewUser]           = useState(BLANK_USER);
  const [editingRole, setEditingRole]   = useState(null);
  const [editRoleVal, setEditRoleVal]   = useState('');

  useEffect(() => { loadUsers(); }, []); // eslint-disable-line

  const loadUsers = async () => {
    setLoadingUsers(true);
    try { setUsers(await listUsers()); }
    catch (err) { toast(err.message, 'error'); }
    finally { setLoadingUsers(false); }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    if (!newUser.email || !newUser.password || !newUser.name) {
      toast('Please fill in all required fields', 'error');
      return;
    }
    try {
      await createUser(newUser.email, newUser.password, newUser.name, newUser.role);
      toast('User created', 'success');
      setShowAddForm(false);
      setNewUser(BLANK_USER);
      await loadUsers();
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const handleToggleStatus = async (userId, active) => {
    try {
      if (active) await deactivateUser(userId);
      else        await activateUser(userId);
      toast(`User ${active ? 'deactivated' : 'activated'}`, 'success');
      await loadUsers();
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const handleStartEditRole = (u) => {
    setEditingRole(u.id);
    setEditRoleVal(u.role);
  };

  const handleSaveRole = async (userId) => {
    try {
      await updateUser(userId, null, editRoleVal);
      toast('Role updated', 'success');
      setEditingRole(null);
      await loadUsers();
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const handleRefreshSuppliers = async () => {
    setRefreshing(true);
    try {
      const data = await refreshSuppliers();
      setRefreshResult(data);
      toast(`${data.suppliers_updated} supplier(s) updated`, 'success');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1 className="page-title">Administration</h1>
        <p className="page-subtitle">Manage users, roles, and platform data</p>
      </div>

      {/* Tabs */}
      <div className="admin__tabs">
        <button
          className={`admin__tab${tab === 'users' ? ' admin__tab--active' : ''}`}
          onClick={() => setTab('users')}
        >
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><circle cx="7" cy="7" r="3.5" stroke="currentColor" strokeWidth="1.5"/><circle cx="14" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.5"/><path d="M1 17c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M14 11c2 0 4 1.3 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          Users
        </button>
        <button
          className={`admin__tab${tab === 'suppliers' ? ' admin__tab--active' : ''}`}
          onClick={() => setTab('suppliers')}
        >
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><path d="M2 14l4-4 3 3 4-5 5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
          Supplier Analytics
        </button>
      </div>

      {/* Users tab */}
      {tab === 'users' && (
        <div className="admin__section">
          <div className="admin__section-header">
            <div>
              <div className="admin__section-title">User Management</div>
              <div className="admin__section-desc">{users.length} registered user(s)</div>
            </div>
            <button
              className={`btn ${showAddForm ? 'btn--ghost' : 'btn--primary'}`}
              onClick={() => setShowAddForm(!showAddForm)}
            >
              {showAddForm
                ? 'Cancel'
                : <><svg width="13" height="13" viewBox="0 0 20 20" fill="none"><path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg> Add User</>
              }
            </button>
          </div>

          {/* Add user form */}
          {showAddForm && (
            <form className="admin__add-form" onSubmit={handleAddUser}>
              <div>
                <label className="form-label">Full Name</label>
                <input
                  className="form-input"
                  type="text"
                  placeholder="Jane Smith"
                  value={newUser.name}
                  onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="form-label">Email</label>
                <input
                  className="form-input"
                  type="email"
                  placeholder="jane@company.com"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="form-label">Password</label>
                <input
                  className="form-input"
                  type="password"
                  placeholder="••••••••"
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="form-label">Role</label>
                <select
                  className="form-select"
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                >
                  <option value="enterprise_user">Enterprise User</option>
                  <option value="reviewer">Reviewer</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
              <div className="admin__add-form-actions">
                <button type="submit" className="btn btn--primary">Create User</button>
                <button type="button" className="btn btn--ghost" onClick={() => { setShowAddForm(false); setNewUser(BLANK_USER); }}>
                  Cancel
                </button>
              </div>
            </form>
          )}

          {/* Users table */}
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
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
                {loadingUsers
                  ? Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      {[120, 180, 90, 70, 100].map((w, j) => (
                        <td key={j}><div className="skeleton" style={{ height: 14, width: w, borderRadius: 4 }} /></td>
                      ))}
                    </tr>
                  ))
                  : users.length === 0
                  ? (
                    <tr>
                      <td colSpan={5}>
                        <div className="empty-state" style={{ padding: 'var(--sp-8)' }}>
                          <div className="empty-state__title">No users found</div>
                        </div>
                      </td>
                    </tr>
                  )
                  : users.map((u, idx) => (
                    <tr key={u.id} className="animate-fade-in" style={{ animationDelay: `${idx * 20}ms` }}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
                          <div style={{
                            width: 28, height: 28, borderRadius: '50%',
                            background: 'var(--accent-dim)', border: '1px solid var(--border)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 11, fontWeight: 700, color: 'var(--accent)', flexShrink: 0,
                          }}>
                            {u.name?.[0]?.toUpperCase() || '?'}
                          </div>
                          <span style={{ fontWeight: 500, color: 'var(--text-1)' }}>{u.name}</span>
                        </div>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-3)' }}>{u.email}</td>
                      <td>
                        {editingRole === u.id ? (
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                            <select
                              className="admin__role-select"
                              value={editRoleVal}
                              onChange={(e) => setEditRoleVal(e.target.value)}
                              autoFocus
                            >
                              <option value="enterprise_user">enterprise_user</option>
                              <option value="reviewer">reviewer</option>
                              <option value="admin">admin</option>
                            </select>
                            <button className="btn btn--success btn--sm" onClick={() => handleSaveRole(u.id)}>Save</button>
                            <button className="btn btn--ghost btn--sm" onClick={() => setEditingRole(null)}>✕</button>
                          </div>
                        ) : (
                          <span
                            className={`role-pill role-pill--${u.role}`}
                            style={{ cursor: 'pointer' }}
                            onClick={() => handleStartEditRole(u)}
                            title="Click to edit role"
                          >
                            {u.role.replace('_',' ')}
                          </span>
                        )}
                      </td>
                      <td>
                        <span className="status-dot status-dot--" style={{}} />
                        <span className={`status-dot status-dot--${u.is_active ? 'active' : 'inactive'}`} />
                        <span style={{ fontSize: 12, color: u.is_active ? 'var(--success)' : 'var(--text-5)' }}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td>
                        <button
                          className={`btn btn--sm ${u.is_active ? 'btn--danger' : 'btn--success'}`}
                          onClick={() => handleToggleStatus(u.id, u.is_active)}
                        >
                          {u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>
                  ))
                }
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Suppliers tab */}
      {tab === 'suppliers' && (
        <div className="admin__section">
          <div className="admin__section-header">
            <div>
              <div className="admin__section-title">Supplier Metrics Refresh</div>
              <div className="admin__section-desc">
                Recompute supplier risk scores from all processed documents
              </div>
            </div>
            <button
              className="btn btn--primary"
              onClick={handleRefreshSuppliers}
              disabled={refreshing}
            >
              {refreshing
                ? <><div className="spinner" style={{ width:14, height:14, borderWidth:2 }} /> Refreshing…</>
                : <>
                    <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><path d="M18 10a8 8 0 11-8-8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M14 2l4 0 0 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    Refresh Metrics
                  </>
              }
            </button>
          </div>

          <div className="admin__section-body">
            {!refreshResult ? (
              <div className="empty-state">
                <svg className="empty-state__icon" viewBox="0 0 24 24" fill="none"><path d="M21 12a9 9 0 11-9-9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                <div className="empty-state__title">No refresh yet</div>
                <div className="empty-state__desc">
                  Click "Refresh Metrics" to recompute supplier risk scores from all processed documents
                </div>
              </div>
            ) : (
              <>
                <div className="admin__refresh-result">
                  <div className="admin__refresh-stats">
                    <div className="admin__refresh-stat">
                      <strong>{refreshResult.suppliers_updated}</strong>
                      <span>Suppliers updated</span>
                    </div>
                    <div className="admin__refresh-stat">
                      <strong>{refreshResult.risk_scores_computed}</strong>
                      <span>Risk scores computed</span>
                    </div>
                  </div>
                </div>

                {refreshResult.suppliers?.length > 0 && (
                  <div style={{ marginTop: 'var(--sp-5)', overflowX: 'auto' }}>
                    <table className="data-table">
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
                            <td style={{ fontWeight: 500, color: 'var(--text-1)' }}>{s.supplier_name}</td>
                            <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{s.total_documents}</td>
                            <td>
                              {s.avg_confidence
                                ? <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{(s.avg_confidence * 100).toFixed(1)}%</span>
                                : '—'
                              }
                            </td>
                            <td>
                              <span style={{
                                fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700,
                                color: s.risk_score >= 70 ? 'var(--error)' : s.risk_score >= 40 ? 'var(--warning)' : 'var(--success)',
                              }}>
                                {s.risk_score ?? '—'}
                              </span>
                            </td>
                            <td>
                              <span className="badge badge--muted">{s.method}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
