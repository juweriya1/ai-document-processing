import { useEffect, useState } from 'react';
import { getBIConfig } from '../api/client';
import './PowerBIEmbed.css';

export default function PowerBIEmbed({ height = 720 }) {
  const [cfg, setCfg] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    getBIConfig()
      .then(setCfg)
      .catch((e) => setErr(e.message || 'Failed to load BI config'));
  }, []);

  if (err) {
    return (
      <div className="bi-embed__fallback">
        <div className="bi-embed__fallback-title">Could not reach Executive BI</div>
        <div className="bi-embed__fallback-desc">{err}</div>
      </div>
    );
  }

  if (!cfg) {
    return (
      <div className="bi-embed__loading">
        <div className="spinner" />
        <span>Loading Executive BI dashboard…</span>
      </div>
    );
  }

  if (!cfg.power_bi_embed_url) {
    return (
      <div className="bi-embed__fallback">
        <div className="bi-embed__fallback-title">Executive BI not yet configured</div>
        <div className="bi-embed__fallback-desc">
          Publish <code>docs/powerbi/fyp_dashboard.pbix</code> to Power BI Service
          via <strong>File → Embed report → Publish to web (public)</strong>,
          copy the embed URL, and set <code>POWER_BI_PUBLIC_URL</code> in the backend
          <code>.env</code>. The dashboard will appear here once the variable is set.
        </div>
        <div className="bi-embed__fallback-hint">
          See <code>docs/powerbi/README.md</code> for the full publish flow.
        </div>
      </div>
    );
  }

  return (
    <div className="bi-embed">
      <iframe
        title="Executive BI Dashboard"
        src={cfg.power_bi_embed_url}
        allowFullScreen
        style={{ width: '100%', height, border: 0, borderRadius: 12 }}
      />
      <div className="bi-embed__footer">
        <span>Last refreshed: {cfg.last_refreshed_at || 'on demand'}</span>
        <span>·</span>
        <span>Refresh cadence: {cfg.refresh_cadence}</span>
      </div>
    </div>
  );
}
