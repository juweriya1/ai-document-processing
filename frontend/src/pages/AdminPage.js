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

  const handleAction = () => {
    toast('Coming soon — admin management not yet connected', 'info');
  };

  return (
    <div>
      <h1 className="admin__title">User Administration</h1>
      <div className="placeholder-banner">
        Preview layout — admin management will be connected in a future phase.
      </div>

      <div className="admin__actions">
        <button className="admin__add-btn" onClick={handleAction}>
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
            {USERS.map((user) => (
              <tr key={user.email}>
                <td>{user.name}</td>
                <td>{user.email}</td>
                <td>
                  <span className={`admin__role-pill admin__role-pill--${user.role}`}>
                    {user.role.replace('_', ' ')}
                  </span>
                </td>
                <td>
                  <span className={user.status === 'active' ? 'admin__status-active' : 'admin__status-inactive'}>
                    {user.status}
                  </span>
                </td>
                <td>
                  <button className="admin__action-btn" onClick={handleAction}>Edit</button>
                  <button className="admin__action-btn admin__action-btn--danger" onClick={handleAction}>
                    {user.status === 'active' ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
