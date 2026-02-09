import { createContext, useContext, useReducer, useEffect, useCallback } from 'react';
import { login as apiLogin, register as apiRegister } from '../api/client';

const AuthContext = createContext(null);

const initialState = {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
};

function authReducer(state, action) {
  switch (action.type) {
    case 'LOGIN_SUCCESS':
      return {
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
        isLoading: false,
      };
    case 'LOGOUT':
      return { ...initialState, isLoading: false };
    case 'RESTORE_SESSION':
      return {
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
        isLoading: false,
      };
    case 'LOADED':
      return { ...state, isLoading: false };
    default:
      return state;
  }
}

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  useEffect(() => {
    const token = localStorage.getItem('idp_token');
    const userJson = localStorage.getItem('idp_user');
    if (token && userJson) {
      try {
        const user = JSON.parse(userJson);
        dispatch({ type: 'RESTORE_SESSION', payload: { user, token } });
      } catch {
        localStorage.removeItem('idp_token');
        localStorage.removeItem('idp_user');
        dispatch({ type: 'LOADED' });
      }
    } else {
      dispatch({ type: 'LOADED' });
    }
  }, []);

  const loginAction = useCallback(async (email, password) => {
    const data = await apiLogin(email, password);
    localStorage.setItem('idp_token', data.accessToken);
    localStorage.setItem('idp_user', JSON.stringify(data.user));
    dispatch({
      type: 'LOGIN_SUCCESS',
      payload: { user: data.user, token: data.accessToken },
    });
  }, []);

  const registerAction = useCallback(async (email, password, name, role) => {
    await apiRegister(email, password, name, role);
    await loginAction(email, password);
  }, [loginAction]);

  const logout = useCallback(() => {
    localStorage.removeItem('idp_token');
    localStorage.removeItem('idp_user');
    dispatch({ type: 'LOGOUT' });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, loginAction, registerAction, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
