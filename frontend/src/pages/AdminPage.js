import { useState, useEffect } from 'react';
import { refreshSuppliers, listUsers, createUser, updateUser, deactivateUser, activateUser } from '../api/client';
import { useToast } from '../components/Toast';
import './AdminPage.css';

const ROLES = ['admin', 'reviewer', 'enterprise_user'];

function RolePill({ role }) {
  return <span className={`role-pill role-pill--${role}`}>{role.replace(/_/g, ' ')}</span>;
}

export default function AdminPage() {
  const toast = useToast();

  const [refreshing, setRefreshing]   = useState(false);
  const [refreshResult, setRefResult] = useState(null);

  const [users, setUsers]             = useState([]);
  const [loadingUsers, setLoadingU]   = useState(true);
  const [showAdd, setShowAdd]         = useState(false);
  const [newUser, setNewUser]         = useState({ email:'', password:'', name:'', role:'enterprise_user' });

  useEffect(() => { loadUsers(); }, []); // eslint-disable-line

  const loadUsers = async () => {
    setLoadingU(true);
    try { setUsers(await listUsers()); }
    catch (err) { toast(err.message, 'error'); }
    finally { setLoadingU(false); }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    if (!newUser.email || !newUser.password || !newUser.name) { toast('All fields required', 'error'); return; }
    try {
      await createUser(newUser.email, newUser.password, newUser.name, newUser.role);
      toast('User created successfully', 'success');
      setShowAdd(false);
      setNewUser({ email:'', password:'', name:'', role:'enterprise_user' });
      await loadUsers();
    } catch (err) { toast(err.message, 'error'); }
  };

  const handleToggle = async (userId, active) => {
    try {
      active ? await deactivateUser(userId) : await activateUser(userId);
      toast(active ? 'User deactivated' : 'User activated', 'success');
      await loadUsers();
    } catch (err) { toast(err.message, 'error'); }
  };

  const handleEditRole = async (userId, currentRole) => {
    const others = ROLES.filter(r => r !== currentRole);
    const newRole = window.prompt(`Current role: ${currentRole}\nNew role (${others.join(', ')}):`);
    if (!newRole) return;
    if (!ROLES.includes(newRole)) { toast('Invalid role', 'error'); return; }
    try { await updateUser(userId, null, newRole); toast('Role updated', 'success'); await loadUsers(); }
    catch (err) { toast(err.message, 'error'); }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const d = await refreshSuppliers();
      setRefResult(d);
      toast(`Refreshed — ${d.suppliers_updated} supplier(s) updated`, 'success');
    } catch (err) { toast(err.message, 'error'); }
    finally { setRefreshing(false); }
  };

  const set = (k) => (e) => setNewUser(prev => ({ ...prev, [k]: e.target.value }));

  return (
    <div className="page-wrap">
      <div className="page-hd">
        <h1 className="page-title">Administration</h1>
      </div>

      {/* ── Supplier analytics ── */}
      <div className="admin-section">
        <div className="admin-section-hd">
          <div>
            <div className="admin-section-title">Supplier Analytics</div>
            <div className="admin-section-desc">Recompute supplier metrics and risk scores from all processed documents.</div>
          </div>
          <button className="btn btn-ghost" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? <><span className="spinner" /> Refreshing…</> : '↻ Refresh Metrics'}
          </button>
        </div>

        {refreshResult && (
          <div className="refresh-result">
            <div className="refresh-stat">Suppliers updated: <strong>{refreshResult.suppliers_updated}</strong></div>
            <div className="refresh-stat">Risk scores computed: <strong>{refreshResult.risk_scores_computed}</strong></div>
            {refreshResult.suppliers?.length > 0 && (
              <div className="table-wrap" style={{ marginTop: 14 }}>
                <table className="table">
                  <thead>
                    <tr><th>Supplier</th><th>Documents</th><th>Avg Confidence</th><th>Risk Score</th><th>Method</th></tr>
                  </thead>
                  <tbody>
                    {refreshResult.suppliers.map(s => (
                      <tr key={s.supplier_name}>
                        <td>{s.supplier_name}</td>
                        <td>{s.total_documents}</td>
                        <td>{s.avg_confidence ? `${(s.avg_confidence*100).toFixed(1)}%` : 'N/A'}</td>
                        <td>{s.risk_score}</td>
                        <td><span className="mono">{s.method}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── User management ── */}
      <div className="admin-section">
        <div className="admin-section-hd">
          <div>
            <div className="admin-section-title">User Management</div>
            <div className="admin-section-desc">Manage platform accounts, roles, and access.</div>
          </div>
          <button className="btn btn-primary" onClick={() => setShowAdd(v => !v)}>
            {showAdd ? 'Cancel' : '+ Add User'}
          </button>
        </div>

        {/* Add user form */}
        {showAdd && (
          <form className="add-user-form" onSubmit={handleAddUser}>
            <div className="field">
              <label className="field-label">Full Name</label>
              <input className="field-input" type="text" placeholder="Jane Smith" value={newUser.name} onChange={set('name')} required />
            </div>
            <div className="field">
              <label className="field-label">Email</label>
              <input className="field-input" type="email" placeholder="jane@company.com" value={newUser.email} onChange={set('email')} required />
            </div>
            <div className="field">
              <label className="field-label">Password</label>
              <input className="field-input" type="password" placeholder="••••••••" value={newUser.password} onChange={set('password')} required />
            </div>
            <div className="field">
              <label className="field-label">Role</label>
              <select className="field-input" value={newUser.role} onChange={set('role')}>
                <option value="enterprise_user">Enterprise User</option>
                <option value="reviewer">Reviewer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="add-user-form__footer">
              <button type="submit" className="btn btn-primary">Create User</button>
              <button type="button" className="btn btn-ghost" onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </form>
        )}

        {/* Users table */}
        {loadingUsers ? (
          <div className="val-loading"><span className="spinner" /> Loading users…</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr><td colSpan={5} style={{ textAlign:'center', padding:'28px', color:'var(--text-3)' }}>No users found</td></tr>
                ) : users.map(u => (
                  <tr key={u.id}>
                    <td style={{ fontWeight:600, color:'var(--text-1)' }}>{u.name}</td>
                    <td>{u.email}</td>
                    <td><RolePill role={u.role} /></td>
                    <td>
                      <span className={u.is_active ? 'status-active' : 'status-inactive'}>
                        {u.is_active ? '● Active' : '○ Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="tbl-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => handleEditRole(u.id, u.role)}>Edit Role</button>
                        <button
                          className={`btn btn-sm ${u.is_active ? 'btn-danger' : 'btn-success'}`}
                          onClick={() => handleToggle(u.id, u.is_active)}
                        >
                          {u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
