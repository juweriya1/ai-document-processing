import { createContext, useContext, useReducer, useEffect, useCallback } from 'react';

/**
 * DocumentContext caches enough state across page navigation that the user
 * doesn't lose their place. Specifically:
 *
 *   - lastProcessing: most recent processing result. ProcessingPage writes
 *     it on success; the same page re-renders it if the user navigates back.
 *   - recentDocId: most recent single-document upload. Drives pre-fill of
 *     doc-ID inputs on Validation/Review when no URL param is supplied.
 *   - recentBatch: { batchId, documentIds } from the most recent batch
 *     upload. Drives the per-doc selector on Validation/Review for
 *     batch-context users.
 *
 * Persisted in localStorage (keyed by user — wiped at logout). Storage
 * is a "best effort" cache, not a source of truth: the backend is always
 * the authority. We only persist what the user would want to recover
 * across an accidental tab close.
 */

const STORAGE_KEY = 'idp_documents_cache';
const DocumentContext = createContext(null);

const initialState = {
  lastProcessing: null,    // { documentId, result, updatedAt }
  recentDocId: null,        // string
  recentBatch: null,        // { batchId, documentIds: string[], updatedAt }
};

function documentsReducer(state, action) {
  switch (action.type) {
    case 'HYDRATE':
      return { ...initialState, ...action.payload };
    case 'SET_PROCESSING_RESULT':
      return {
        ...state,
        lastProcessing: {
          documentId: action.payload.documentId,
          result: action.payload.result,
          updatedAt: new Date().toISOString(),
        },
        recentDocId: action.payload.documentId,
      };
    case 'CLEAR_PROCESSING_RESULT':
      return { ...state, lastProcessing: null };
    case 'SET_RECENT_DOC_ID':
      return { ...state, recentDocId: action.payload };
    case 'SET_RECENT_BATCH':
      return {
        ...state,
        recentBatch: {
          batchId: action.payload.batchId,
          documentIds: action.payload.documentIds || [],
          updatedAt: new Date().toISOString(),
        },
      };
    case 'CLEAR_ALL':
      return { ...initialState };
    default:
      return state;
  }
}

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveToStorage(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage may be full or disabled — fail silently; nothing breaks.
  }
}

export function DocumentProvider({ children }) {
  const [state, dispatch] = useReducer(documentsReducer, initialState);

  // Hydrate once on mount. If the user logs in/out, the AuthContext takes
  // care of clearing — see clearAll() below, called from Navbar logout.
  useEffect(() => {
    const cached = loadFromStorage();
    if (cached) {
      dispatch({ type: 'HYDRATE', payload: cached });
    }
  }, []);

  // Mirror state to localStorage on every change. Tiny payloads — no perf
  // concern.
  useEffect(() => {
    saveToStorage(state);
  }, [state]);

  const setProcessingResult = useCallback((documentId, result) => {
    dispatch({
      type: 'SET_PROCESSING_RESULT',
      payload: { documentId, result },
    });
  }, []);

  const clearProcessingResult = useCallback(() => {
    dispatch({ type: 'CLEAR_PROCESSING_RESULT' });
  }, []);

  const setRecentDocId = useCallback((documentId) => {
    dispatch({ type: 'SET_RECENT_DOC_ID', payload: documentId });
  }, []);

  const setRecentBatch = useCallback((batchId, documentIds) => {
    dispatch({
      type: 'SET_RECENT_BATCH',
      payload: { batchId, documentIds },
    });
  }, []);

  const clearAll = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    dispatch({ type: 'CLEAR_ALL' });
  }, []);

  return (
    <DocumentContext.Provider
      value={{
        ...state,
        setProcessingResult,
        clearProcessingResult,
        setRecentDocId,
        setRecentBatch,
        clearAll,
      }}
    >
      {children}
    </DocumentContext.Provider>
  );
}

export function useDocuments() {
  const context = useContext(DocumentContext);
  if (!context) {
    throw new Error('useDocuments must be used within a DocumentProvider');
  }
  return context;
}
