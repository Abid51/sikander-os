import { useState } from 'react';
import { api, authToken } from './api';

type Props = {
  onAuthenticated: () => void;
};

export default function LoginGate({ onAuthenticated }: Props) {
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setError(null);
    const t = token.trim();
    if (!t) {
      setError('Token required.');
      return;
    }
    setLoading(true);
    try {
      const ok = await api.verifyToken(t);
      if (!ok) {
        setError('Invalid token. Check IGRIS_API_TOKEN on the server.');
        return;
      }
      authToken.set(t);
      onAuthenticated();
    } catch {
      setError('Could not reach the API. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-overlay">
      <div className="login-card">
        <div className="login-header">
          <div className="login-orb" />
          <h2>IGRIS Access Gate</h2>
          <p>Enter your API token to unlock the command console.</p>
        </div>

        <form className="login-form" onSubmit={submit}>
          <label>
            <span>API Token</span>
            <input
              type="password"
              autoFocus
              placeholder="Paste IGRIS_API_TOKEN"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              disabled={loading}
            />
          </label>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" disabled={loading || !token.trim()}>
            {loading ? 'Verifying…' : 'Unlock'}
          </button>
        </form>

        <p className="login-hint">
          Auth is enabled because <code>IGRIS_API_TOKEN</code> is set on the
          backend. To disable, unset the env var and restart the API.
        </p>
      </div>
    </div>
  );
}
