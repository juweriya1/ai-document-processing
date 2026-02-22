import { useState, useEffect } from 'react';
import {
  refreshSuppliers,
  listUsers,
  createUser,
  updateUser,
  deactivateUser,
  activateUser,
} from '../api/client';
import { useToast } from '../components/Toast';
import './AdminPage.css';

export default function AdminPage() {
  const toast = useToast();
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState(null);
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newUser, setNewUser] = useState({ email: '', password: '', name: '', role: 'enterprise_user' });

  useEffect(() => {
    loadUsers();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadUsers = async () => {
    setLoadingUsers(true);
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setLoadingUsers(false);
    }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    if (!newUser.email || !newUser.password || !newUser.name) {
      toast('Please fill in all required fields', 'error');
      return;
    }
    try {
      await createUser(newUser.email, newUser.password, newUser.name, newUser.role);
      toast('User created successfully', 'success');
      setShowAddForm(false);
      setNewUser({ email: '', password: '', name: '', role: 'enterprise_user' });
      await loadUsers();
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const handleToggleStatus = async (userId, currentlyActive) => {
    try {
      if (currentlyActive) {
        await deactivateUser(userId);
        toast('User deactivated', 'success');
      } else {
        await activateUser(userId);
        toast('User activated', 'success');
      }
      await loadUsers();
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const handleEditRole = async (userId, currentRole) => {
    const roles = ['admin', 'reviewer', 'enterprise_user'].filter(r => r !== currentRole);
    const newRole = window.prompt(`Current role: ${currentRole}\nEnter new role (${roles.join(', ')}):`);
    if (!newRole) return;
    if (!['admin', 'reviewer', 'enterprise_user'].includes(newRole)) {
      toast('Invalid role', 'error');
      return;
    }
    try {
      await updateUser(userId, null, newRole);
      toast('Role updated', 'success');
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

        <div className="admin__actions">
          <button className="admin__add-btn" onClick={() => setShowAddForm(!showAddForm)}>
            {showAddForm ? 'Cancel' : 'Add User'}
          </button>
        </div>

        {showAddForm && (
          <form className="admin__add-form" onSubmit={handleAddUser}>
            <input
              type="text"
              placeholder="Name"
              value={newUser.name}
              onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
              required
            />
            <input
              type="email"
              placeholder="Email"
              value={newUser.email}
              onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={newUser.password}
              onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
              required
            />
            <select
              value={newUser.role}
              onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
            >
              <option value="enterprise_user">Enterprise User</option>
              <option value="reviewer">Reviewer</option>
              <option value="admin">Admin</option>
            </select>
            <button type="submit" className="admin__add-btn">Create</button>
          </form>
        )}

        <div className="admin__table-wrap">
          {loadingUsers ? (
            <div className="admin__loading">Loading users...</div>
          ) : (
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
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td>{u.email}</td>
                    <td>
                      <span className={`admin__role-pill admin__role-pill--${u.role}`}>
                        {u.role.replace('_', ' ')}
                      </span>
                    </td>
                    <td>
                      <span className={u.is_active ? 'admin__status-active' : 'admin__status-inactive'}>
                        {u.is_active ? 'active' : 'inactive'}
                      </span>
                    </td>
                    <td>
                      <button className="admin__action-btn" onClick={() => handleEditRole(u.id, u.role)}>
                        Edit Role
                      </button>
                      <button
                        className={`admin__action-btn ${u.is_active ? 'admin__action-btn--danger' : ''}`}
                        onClick={() => handleToggleStatus(u.id, u.is_active)}
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '20px' }}>
                      No users found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
