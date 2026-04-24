import { useEffect, useState } from 'react';
import {
  getWidgetCatalog,
  getWidgetPreferences,
  saveWidgetPreferences,
} from '../api/client';
import { useToast } from './Toast';
import './WidgetPickerDrawer.css';

export default function WidgetPickerDrawer({ open, onClose, onSaved }) {
  const toast = useToast();
  const [catalog, setCatalog] = useState([]);
  const [enabled, setEnabled] = useState([]);
  const [order, setOrder]     = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    Promise.all([getWidgetCatalog(), getWidgetPreferences()])
      .then(([cat, pref]) => {
        setCatalog(cat || []);
        setEnabled(pref?.enabled || []);
        setOrder(pref?.order || []);
      })
      .catch((e) => toast(e.message, 'error'))
      .finally(() => setLoading(false));
  }, [open, toast]);

  const toggle = (key) =>
    setEnabled((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );

  const move = (key, dir) => {
    setOrder((prev) => {
      const idx = prev.indexOf(key);
      if (idx === -1) return prev;
      const next = [...prev];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      const layout = await saveWidgetPreferences({ enabled, order });
      toast('Dashboard layout saved', 'success');
      onSaved?.(layout);
      onClose();
    } catch (e) {
      toast(e.message || 'Could not save layout', 'error');
    } finally {
      setSaving(false);
    }
  };

  const grouped = catalog.reduce((acc, w) => {
    (acc[w.category] = acc[w.category] || []).push(w);
    return acc;
  }, {});

  // Render widgets per category in catalog order, so position of checkboxes is stable
  const categoriesInOrder = Object.keys(grouped);

  if (!open) return null;

  return (
    <div className="wpd__overlay" onClick={onClose}>
      <aside
        className="wpd"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Configure dashboard widgets"
      >
        <header className="wpd__header">
          <div>
            <div className="wpd__title">Configure Dashboard</div>
            <div className="wpd__sub">Toggle widgets and adjust order. Changes save per user.</div>
          </div>
          <button className="wpd__close" onClick={onClose} aria-label="Close">✕</button>
        </header>

        <div className="wpd__body">
          {loading ? (
            <div className="wpd__loading"><div className="spinner" /> Loading widget catalog…</div>
          ) : catalog.length === 0 ? (
            <div className="wpd__empty">No widgets available for your role.</div>
          ) : (
            categoriesInOrder.map((cat) => (
              <section className="wpd__section" key={cat}>
                <div className="wpd__section-title">{cat}</div>
                {grouped[cat].map((w) => {
                  const isOn = enabled.includes(w.key);
                  const pos  = order.indexOf(w.key);
                  return (
                    <div className={`wpd__row${isOn ? ' wpd__row--on' : ''}`} key={w.key}>
                      <label className="wpd__check">
                        <input
                          type="checkbox"
                          checked={isOn}
                          onChange={() => toggle(w.key)}
                        />
                        <span className="wpd__check-box" aria-hidden />
                      </label>
                      <div className="wpd__row-text">
                        <div className="wpd__row-title">{w.title}</div>
                        <div className="wpd__row-key">{w.key}</div>
                      </div>
                      <div className="wpd__row-order">
                        <button
                          className="wpd__order-btn"
                          onClick={() => move(w.key, -1)}
                          disabled={pos <= 0}
                          aria-label="Move up"
                        >↑</button>
                        <button
                          className="wpd__order-btn"
                          onClick={() => move(w.key, +1)}
                          disabled={pos === -1 || pos >= order.length - 1}
                          aria-label="Move down"
                        >↓</button>
                      </div>
                    </div>
                  );
                })}
              </section>
            ))
          )}
        </div>

        <footer className="wpd__footer">
          <button
            className="btn btn--primary"
            onClick={save}
            disabled={saving || loading}
          >
            {saving ? 'Saving…' : 'Save layout'}
          </button>
          <button className="btn btn--ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
        </footer>
      </aside>
    </div>
  );
}
