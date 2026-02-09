import { useToast } from '../components/Toast';
import './ValidationPage.css';

const FIELDS = [
  { field: 'Invoice Number', value: 'INV-2024-0312', status: 'valid' },
  { field: 'Vendor Name', value: 'Acme Corp.', status: 'valid' },
  { field: 'Invoice Date', value: '2024-03-15', status: 'valid' },
  { field: 'Total Amount', value: '$14,580.00', status: 'warning' },
  { field: 'PO Number', value: 'PO-XX-MISSING', status: 'invalid' },
];

export default function ValidationPage() {
  const toast = useToast();

  const handleAction = () => {
    toast('Coming soon — validation engine not yet connected', 'info');
  };

  return (
    <div>
      <h1 className="validation__title">Data Validation</h1>
      <div className="placeholder-banner">
        Preview layout — validation engine will be connected in a future phase.
      </div>

      <div className="validation__table-wrap">
        <table className="validation__table">
          <thead>
            <tr>
              <th>Field Name</th>
              <th>Extracted Value</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {FIELDS.map((row) => (
              <tr
                key={row.field}
                className={row.status === 'invalid' ? 'validation__row--invalid' : ''}
              >
                <td>{row.field}</td>
                <td>{row.value}</td>
                <td>
                  <span className={`validation__status validation__status--${row.status}`}>
                    {row.status}
                  </span>
                </td>
                <td>
                  <button className="validation__action-btn" onClick={handleAction}>
                    Edit
                  </button>
                  <button className="validation__action-btn" onClick={handleAction}>
                    Flag
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="validation__footer">
        <button className="validation__footer-btn validation__footer-btn--reject" onClick={handleAction}>
          Reject
        </button>
        <button className="validation__footer-btn validation__footer-btn--proceed" onClick={handleAction}>
          Proceed to Review
        </button>
      </div>
    </div>
  );
}
