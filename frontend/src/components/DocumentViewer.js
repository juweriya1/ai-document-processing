import { useEffect, useRef, useState } from 'react';
import { getDocumentFileUrl } from '../api/client';
import './DocumentViewer.css';

/**
 * Renders a PDF in an iframe or an image inline. Fetches as a blob (with
 * the JWT in an Authorization header rather than the URL) so the bytes
 * never appear in browser history or referrer headers. Cleans up the
 * blob URL on unmount and on documentId change to avoid leaks.
 *
 * Originally lived inside ReviewPage; extracted here so the new
 * Documents list can reuse the exact same viewer behavior.
 */
export default function DocumentViewer({ documentId, filename, height }) {
  const [blobUrl, setBlobUrl] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const blobUrlRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    if (!documentId) {
      setBlobUrl(null);
      setErrorMsg(null);
      return undefined;
    }
    setErrorMsg(null);
    (async () => {
      try {
        const fileUrl = getDocumentFileUrl(documentId);
        const token = localStorage.getItem('idp_token');
        const response = await fetch(fileUrl, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!response.ok) {
          if (!cancelled) setErrorMsg('Document file not available');
          return;
        }
        const blob = await response.blob();
        if (cancelled) return;
        if (blobUrlRef.current) {
          URL.revokeObjectURL(blobUrlRef.current);
        }
        const url = URL.createObjectURL(blob);
        blobUrlRef.current = url;
        setBlobUrl(url);
      } catch {
        if (!cancelled) setErrorMsg('Failed to load document');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  useEffect(() => {
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, []);

  const isPdf = (filename || '').toLowerCase().endsWith('.pdf');
  const style = height ? { height } : undefined;

  if (errorMsg) {
    return <div className="docviewer docviewer--empty" style={style}>{errorMsg}</div>;
  }
  if (!blobUrl) {
    return <div className="docviewer docviewer--empty" style={style}>Loading document…</div>;
  }
  return (
    <div className="docviewer" style={style}>
      {isPdf ? (
        <iframe className="docviewer__frame" src={blobUrl} title="Document Preview" />
      ) : (
        <img className="docviewer__img" src={blobUrl} alt="Document Preview" />
      )}
    </div>
  );
}
